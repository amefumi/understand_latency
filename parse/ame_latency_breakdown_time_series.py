#!/usr/bin/env python3
import os
import re
import sys
import argparse
from typing import List, Dict, Any
import matplotlib.pyplot as plt
import csv

CATEGORIES = [
    'rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app',
    'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue', 'tx_xmit', 'full'
]

# Compile regex once
LINE_RE = re.compile(
    r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -- "
    r"hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) napi: ([0-9]+) gro: ([0-9]+) "
    r"ip: ([0-9]+) tcp: ([0-9]+) read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) "
    r"wakeup: ([0-9]+) data copy: ([0-9]+) return: ([0-9]+) -- tx -- "
    r"alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) tcp: ([0-9]+) "
    r"ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+).*"
)

def parse_args():
    p = argparse.ArgumentParser(description="Parse latency breakdown logs and plot per-stage time series.")
    p.add_argument("--input", help="path to input log file (default: latencies-1000-server.log)", default=None)
    p.add_argument("--outdir", default="plots", help="Directory to write PNGs/CSV (default: plots/)")
    p.add_argument("--name", default="latency", help="Base name for output files (default: latency)")
    return p.parse_args()

def robust_percentile(sorted_vals: List[int], q: float) -> int:
    # Percentile with rounding consistent with your original code:
    # index = round(q * len(v)) - 1, clamped to [0, len-1]
    # Assumes sorted_vals is already sorted ascending.
    n = len(sorted_vals)
    if n == 0:
        return 0
    idx = int(round(q * n) - 1)
    if idx < 0: idx = 0
    if idx >= n: idx = n - 1
    return sorted_vals[idx]

def main():
    args = parse_args()
    log_path = args.input

    if not os.path.isfile(log_path):
        print(f"error: file not found: {log_path}")
        sys.exit(1)

    # Read lines
    with open(log_path, "r") as fh:
        lines = fh.readlines()

    # Extract timestamp fields in absolute time order (no port map, no sorting)
    samples: List[Dict[str, int]] = []

    rx_ts_hw_start = -1
    first_line = True

    for line in lines:
        m = LINE_RE.match(line)
        if not m:
            continue
        # Map all capture groups to int
        fields = list(map(int, m.groups()))
        # Expect 23 numbers in your original code's groups
        if len(fields) != 23:
            continue
        
        if first_line:
            first_line = False
            continue  # Skip first line as in your original code

        # Unpack named fields for readability (indexes aligned to your original code)
        # [0]=src_port, [1]=dst_port
        src_port = fields[0]; dst_port = fields[1]
        rx_hw = fields[2]; rx_alloc = fields[3]; rx_irq = fields[4]; rx_napi = fields[5]
        rx_gro = fields[6]; rx_ip = fields[7]; rx_tcp = fields[8]; rx_read = fields[9]
        rx_sleep = fields[10]; rx_ready = fields[11]; rx_wake_up = fields[12]
        rx_data_copy = fields[13]; rx_return = fields[14]
        tx_alloc = fields[15]; tx_write = fields[16]; tx_data_copy = fields[17]
        tx_tcp = fields[18]; tx_ip = fields[19]; tx_queue = fields[20]
        tx_xmit = fields[21]; tx_finish = fields[22]

        if rx_ts_hw_start == -1:
            rx_ts_hw_start = rx_hw

        # Align wake_up with ready as in your original code
        if rx_ready > rx_wake_up:
            rx_wake_up = rx_ready

        # Derive per-stage durations (ns) — same equations as your original
        sample = {
            'rx_ts_hw':     rx_hw - rx_ts_hw_start,
            'rx_irq':       rx_alloc    - rx_hw,
            'rx_napi':      rx_gro      - rx_alloc,
            'rx_ip':        rx_tcp      - rx_gro,
            'rx_tcp':       rx_ready    - rx_tcp,
            'rx_sched':     rx_data_copy - rx_ready,
            'rx_data_copy': rx_return   - rx_data_copy,
            'app':          tx_write    - rx_return,
            'tx_data_copy': tx_tcp      - tx_write,
            'tx_tcp':       tx_ip       - tx_tcp,
            'tx_ip':        tx_queue    - tx_ip,
            'tx_queue':     tx_xmit     - tx_queue,
            'tx_xmit':      tx_finish   - tx_xmit,
            'full':         tx_finish   - rx_hw,
        }
        samples.append(sample)

    if not samples:
        print("No samples parsed. Check your regex and log format.")
        sys.exit(2)

    # Compute summary stats
    # Prepare per-category vectors
    per_cat: Dict[str, List[int]] = {c: [] for c in CATEGORIES}
    for s in samples:
        for c in CATEGORIES:
            per_cat[c].append(int(s[c]))

    rx_ts_hw_list = []
    for s in samples:
        rx_ts_hw_list.append(int(s['rx_ts_hw']/1000))  # Convert to us for summary

    # Plot time series per category (index vs ns)
    os.makedirs(args.outdir, exist_ok=True)
    total_samples = len(samples)
    
    # Sample 300 points evenly in total samples for plotting
    step = max(1, total_samples // 400)
    sampled_indices = list(range(0, total_samples, step))
    print(f"Plotting {len(sampled_indices)} points out of {total_samples} total samples.")
    
    plt.figure(figsize=(10, 6))
    plt.xlabel("Time since first packet (us)")
    plt.ylabel(f"Time (ns)")
    plt.title(f"Time series of latency breakdown (sampled {len(sampled_indices)} points)")
    for c in CATEGORIES:
        y = [per_cat[c][i] for i in sampled_indices]
        x = [rx_ts_hw_list[i] for i in sampled_indices]
        # plt.plot(x, y, color='C'+str(CATEGORIES.index(c)), marker='o', markersize=2, linestyle='-', label=c)
        # if tx_*, use triangle marker, else circle
        marker = '^' if c.startswith('tx_') else 'o'
        plt.plot(x, y, color='C'+str(CATEGORIES.index(c)), marker=marker, markersize=2, linestyle='-', label=c)

    plt.legend(markerscale=5)
    plt.yscale('log')
    plt.savefig(os.path.join(args.outdir, f"{args.name}_time_series.pdf"))


if __name__ == '__main__':
    main()

