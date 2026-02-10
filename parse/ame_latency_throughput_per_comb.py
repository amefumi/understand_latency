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
num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56]
flowsize = [64]
iodepth = [1]
dim = [1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 1, 2, 3, 4]


class thread_data:
    client_core = 0
    client_pid = 0
    client_port = 0
    server_core = 0
    server_pid = 0
    server_port = 0
    throughput = 0
    latency = 0
    latency_99 = 0
    latency_999 = 0


# Function to format the tick labels
def scientific_format(tick_val, pos):
    return "{:.0e}".format(tick_val)


def parse_end2end_log(exp_dir):
    """
    Parse client.log and server.log to get the mapping of client port to\\
    client core, client pid, server core, server pid.
    """
    thread_dict = {}

    client_log_path = os.path.join(exp_dir, "client.log")
    with open(client_log_path, "r") as client_log:
        lines = client_log.readlines()
        for line in lines:
            if "cpu" not in line:
                continue
            t = thread_data()
            params = line.split()
            t.client_core = int(params[2])
            t.client_pid = int(params[4])
            t.client_port = int(params[7])
            thread_dict[t.client_port] = t

    server_log_path = os.path.join(exp_dir, "server.log")
    with open(server_log_path, "r") as server_log:
        lines = server_log.readlines()
        for line in lines:
            if "core" not in line:
                continue
            params = line.split()
            t = thread_dict[int(params[7])]
            t.server_core = int(params[2])
            t.server_pid = int(params[4])
            thread_dict[t.client_port] = t

    return thread_dict


def threads_performance(thread_dict):
    n_threads = len(thread_dict)
    total_throughput = sum(t.throughput for t in thread_dict.values())
    avg_latency = sum(t.latency for t in thread_dict.values()) / n_threads
    avg_latency_99 = sum(t.latency_99 for t in thread_dict.values()) / n_threads
    avg_latency_999 = sum(t.latency_999 for t in thread_dict.values()) / n_threads
    return (total_throughput, avg_latency, avg_latency_99, avg_latency_999)


def main():
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs)
    
    combination_results = []
    # A single result = tuple(throughput, avg_latency, p99latency, p999latency)

    # Get performance for each experiment
    for n, f, i, d, p, perm, h, s, core, run in combinations:
        result_dir = f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}"
        thread_dict = parse_end2end_log(result_dir)
        for i_thread in range(n*core):
            thread_netperf_log_path = os.path.join(result_dir, f"netperf-{i_thread}_thpt.log")
            with open(thread_netperf_log_path, "r") as thread_netperf_log:
                line = thread_netperf_log.readline()
                params = line.split()
                port = int(params[1])
                latency = float(params[2])
                latency_99 = float(params[3])
                latency_999 = float(params[4])
                throughput = float(params[5])
                t = thread_dict[port]
                t.throughput = throughput
                t.latency = latency
                t.latency_99 = latency_99
                t.latency_999 = latency_999
                thread_dict[port] = t

        combination_results.append(threads_performance(thread_dict))
    
    # Draw the throughput-latency figure
    throughput_miops = [res[0]/1e6 for res in combination_results]
    avg_latency_us = [res[1] for res in combination_results]
    avg_latency_99_us = [res[2] for res in combination_results]
    avg_latency_999_us = [res[3] for res in combination_results]
    fig, ax = plt.subplots(figsize=(10, 6))
    plt.scatter(throughput_miops, avg_latency_999_us)
    ax.set_xlabel('Throughput (mIOPS)', fontsize=16)
    ax.set_ylabel('P99.9 Latency (us)', fontsize=16)
    ax.tick_params(axis='x', labelsize=14)
    ax.tick_params(axis='y', labelsize=14)
    ax.grid(True, linestyle='--', color='grey', alpha=0.7)
    for spine in ax.spines.values():
        spine.set_linewidth(2)
    plt.tight_layout()
    plt.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.1)
    plt.show()
    

if __name__ == "__main__":
    main()