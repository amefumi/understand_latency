#!/usr/bin/env python3
import os
import re
import sys
import argparse
import numpy as np
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

    rx_ts_hw_start = -1
    first_line = True

    rx_ts_hw_list = []

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

        rx_hw = fields[2]

        if rx_ts_hw_start == -1:
            rx_ts_hw_start = rx_hw

        rx_ts_hw_list.append(int((rx_hw - rx_ts_hw_start)/1000))

    rx_ts_hw_sample = rx_ts_hw_list[2000:2500]
    y = np.array(range(len(rx_ts_hw_sample)))

    plt.figure(figsize=(10, 6))
    plt.plot(rx_ts_hw_sample, y, marker='o', markersize=1, linestyle='None')
    plt.xlabel("Time since first packet (us)")
    # plt.savefig(os.path.join(args.outdir, f"{args.name}_time_series.pdf"))
    plt.show()


if __name__ == '__main__':
    main()

