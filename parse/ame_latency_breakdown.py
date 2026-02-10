#!/usr/bin/env python3
import os
import re
import subprocess
import numpy as np
from itertools import product
from statistics import stdev
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


hd="accirqoff"
our_patch="1"
c_state=1
num_apps = [1]
flowsize = [64]
iodepth = [1]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [1]
runs = [2]

categories = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue', 'tx_xmit']


def read_latency_breakdown(breakdown_parsed_path):
    """
    Read latency breakdown from ame_latency_breakdown.log
        port    rx_irq  rx_napi rx_ip   rx_tcp  rx_sched        rx_data_copy    app     tx_data_copy    tx_tcp  tx_ip   tx_queue        tx_xmit full
        0       78760.241       251.848 33030.535       1278.994        150096.262      1026.797        2987.536        1668.059        619.721 500.381 455.105 529.896 271205.375
        port    rx_irq  rx_napi rx_ip   rx_tcp  rx_sched        rx_data_copy    app     tx_data_copy    tx_tcp  tx_ip   tx_queue        tx_xmit full
        0       380094  1657    113214  7863    479048  10237   21821   12318   3197    3033    2396    2135    759796
        port    rx_irq  rx_napi rx_ip   rx_tcp  rx_sched        rx_data_copy    app     tx_data_copy    tx_tcp  tx_ip   tx_queue        tx_xmit full
        0       497124  2025    134408  21603   759981  42538   105826  47732   32597   22598   4218    3390    952650
    """
    latencies = [] # avg, p99, p999 latencies for each port
    with open(breakdown_parsed_path, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith("port"):
                continue
            params = line.split()
            latencies.append((params[1], params[2], params[3], params[4], 
                              params[5], params[6], params[7], params[8], 
                              params[9], params[10], params[11], params[12], params[13]))
    return latencies


def main():
    # Generate all combinations
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores)

    for n, f, i, d, p, perm, h, s, core in combinations:
        client_breakdown_all_runs = []
        server_breakdown_all_runs = []
        for run in runs:
            result_dir = f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}"
            client_breakdown_parsed_path = os.path.join(result_dir, "linux_latency_breakdown_c")
            server_breakdown_parsed_path = os.path.join(result_dir, "linux_latency_breakdown_s")
            client_breakdown = read_latency_breakdown(client_breakdown_parsed_path)
            server_breakdown = read_latency_breakdown(server_breakdown_parsed_path)
            client_breakdown_all_runs += client_breakdown
            server_breakdown_all_runs += server_breakdown

        # Average over runs
        client_breakdown_avg = [0] * len(categories)
        server_breakdown_avg = [0] * len(categories)
        client_breakdown_p99 = [0] * len(categories)
        server_breakdown_p99 = [0] * len(categories)
        client_breakdown_p999 = [0] * len(categories)
        server_breakdown_p999 = [0] * len(categories)

        for run in range(len(runs)):
            for idx in range(len(categories)):
                # Note: `read_latency_breakdown` return a list of tuples, 
                #       where tuple has a full latency that is not included in the final result
                client_breakdown_avg[idx] += float(client_breakdown_all_runs[run*3][idx])
                server_breakdown_avg[idx] += float(server_breakdown_all_runs[run*3][idx])
                client_breakdown_p99[idx] += float(client_breakdown_all_runs[run*3+1][idx])
                server_breakdown_p99[idx] += float(server_breakdown_all_runs[run*3+1][idx])
                client_breakdown_p999[idx] += float(client_breakdown_all_runs[run*3+2][idx])
                server_breakdown_p999[idx] += float(server_breakdown_all_runs[run*3+2][idx])
        client_breakdown_avg = [round(x / len(runs), 3)/1e3 for x in client_breakdown_avg]
        server_breakdown_avg = [round(x / len(runs), 3)/1e3 for x in server_breakdown_avg]
        client_breakdown_p99 = [round(x / len(runs), 3)/1e3 for x in client_breakdown_p99]
        server_breakdown_p99 = [round(x / len(runs), 3)/1e3 for x in server_breakdown_p99]
        client_breakdown_p999 = [round(x / len(runs), 3)/1e3 for x in client_breakdown_p999]
        server_breakdown_p999 = [round(x / len(runs), 3)/1e3 for  x in server_breakdown_p999]

        # Draw the results:
        #  x-axis = {client_category (red), server_category(green)}
        #  y-axis = latency (us)
        #  legend = {avg, p999(as bar)}
        x = np.arange(len(categories))  # the label locations
        width = 0.25  # the width of the bars
        fig, ax = plt.subplots(figsize=(12, 6))
        rects1 = ax.bar(x - width/2, client_breakdown_avg, width
                        , label='Client Avg', color='red', hatch='/')
        rects2 = ax.bar(x + width/2, server_breakdown_avg, width
                        , label='Server Avg', color='green', hatch='\\')
        rects3 = ax.bar(x - width/2, client_breakdown_p999, width
                        , label='Client P99.9', color='red', alpha=0.3)
        rects4 = ax.bar(x + width/2, server_breakdown_p999, width
                        , label='Server P99.9', color='green', alpha=0.3)
        ax.set_ylabel('Latency (us)', fontsize=16)
        ax.set_title(f'Latency Breakdown for {n*core} Apps, {f}B Flow Size, IODepth {i}, DIM {d}, Pin {p}, Permute {perm}, HRTick {h}, Sched {s}, Cores {core}', fontsize=14)
        ax.set_xticks(x)
        ax.set_ylim((1e-1, 1e3))
        ax.set_xticklabels(categories, fontsize=12)
        ax.tick_params(axis='y', labelsize=14)
        ax.legend(fontsize=12)
        ax.set_yscale('log')
        ax.grid(True, linestyle='--', color='grey', alpha=0.7)
        for spine in ax.spines.values():
            spine.set_linewidth(2)
        plt.tight_layout()
        plt.subplots_adjust(left=0.07, right=0.95, top=0.9, bottom=0.2)
        plt.show()


if __name__ == "__main__":
    main()