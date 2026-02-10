#!/usr/bin/env python3
import os
import re
import subprocess
import numpy as np
from itertools import product
from statistics import stdev
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

hd="nh_airq"
our_patch="1"
c_state=1
# num_apps = [64 ]#44, 48, 52, 56, 60, 64, 68, 72, 76, 80]
# 8 is lost
# num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64,  68, 72, 76, 80, 84, 88, 92, 96]

num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80, 84, 88,92, 96,  ]#100, 112, 128]
num_apps_short = [1, 2, 4, 16, 32, 36, 40, 44,]# 48, 52,  56, ]# 60, ]#64, 68, 72, 76, 80, 84, 88, 92, 96, ]

flowsize = [64]
iodepth = [1]
dim = [0, 1]
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
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores)
    
    combination_results = []
    combination_results_dim = []
    combination_results_dimoff = []
    # A single result = tuple(throughput, avg_latency, p99latency, p999latency)

    # Get performance for each experiment
    for n, f, i, d, p, perm, h, s, core in combinations:
        comb_lats = []
        comb_lats_99 = []
        comb_lats_999 = []
        comb_throughput = []

        for run in runs:
            n_apps = n * core
            run_lat = []
            run_lat_99 = []
            run_lat_999 = []
            run_throughput = 0

            result_dir = f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}"
            if not os.path.exists(os.path.join(result_dir, "netperf-0_thpt.log")):
                print(f"Skipping missing dir {result_dir}")
                continue

            for i_thread in range(n_apps):
                thread_netperf_log_path = os.path.join(result_dir, f"netperf-{i_thread}_thpt.log")
                with open(thread_netperf_log_path, "r") as thread_netperf_log:
                    line = thread_netperf_log.readline()
                    params = line.split()
                    run_lat.append(float(params[2]))
                    run_lat_99.append(float(params[3])) 
                    run_lat_999.append(float(params[4]))
                    run_throughput += float(params[5])
            comb_lats += run_lat
            comb_lats_99 += run_lat_99
            comb_lats_999 += run_lat_999
            comb_throughput.append(run_throughput)
        # Average over runs
        lat = tuple(comb_lats)
        lat_99 = tuple(comb_lats_99)
        lat_999 = tuple(comb_lats_999)
        avg_throughput = sum(comb_throughput) / len(comb_throughput)
        
        combination_results.append((avg_throughput, lat, lat_99, lat_999, n*core))
        if d == 1:
            combination_results_dim.append((avg_throughput, lat, lat_99, lat_999, n*core))
        else:
            combination_results_dimoff.append((avg_throughput, lat, lat_99, lat_999, n*core))

    # Sort combination_results, combination_results_dim, and combination_results_dimoff by num_apps (the last element in the tuple)
    combination_results.sort(key=lambda x: x[4])
    combination_results_dim.sort(key=lambda x: x[4])
    combination_results_dimoff.sort(key=lambda x: x[4])

    # Plot throughput vs latency (p999)
    throughputs = [res[0]/1e6 for res in combination_results]  # 你原来的单位换算保持不变
    latencies_999 = [res[3] for res in combination_results]      # 每个元素是该点的所有样本 tuple
    throughputs_dim = [res[0]/1e6 for res in combination_results_dim]
    latencies_999_dim = [res[3] for res in combination_results_dim]
    throughputs_dimoff = [res[0]/1e6 for res in combination_results_dimoff]
    latencies_999_dimoff = [res[3] for res in combination_results_dimoff]

    x = np.array(throughputs)

    plt.figure(figsize=(5, 5*0.618))

    for thpt, samples in zip(throughputs_dim, latencies_999_dim):
        xs = np.full(len(samples), thpt)
        plt.scatter(xs, samples, s=1, alpha=0.3, edgecolors='none', label=None, color='blue', zorder=2)

    for thpt, samples in zip(throughputs_dimoff, latencies_999_dimoff):
        xs = np.full(len(samples), thpt)
        plt.scatter(xs, samples, s=1, alpha=0.3, edgecolors='none', label=None, color='orange', zorder=2)

    x_dim = np.array(throughputs_dim)
    means_999_dim = [np.mean(lat) for lat in latencies_999_dim]
    plt.plot(x_dim, means_999_dim, marker='o', linestyle='-', linewidth=1, label='w/ DIM')

    x_dimoff = np.array(throughputs_dimoff[0:len(num_apps_short)])
    means_999_dimoff = [np.mean(lat) for lat in latencies_999_dimoff[0:len(num_apps_short)]]
    plt.plot(x_dimoff, means_999_dimoff, marker='o', linestyle='-', linewidth=1, label='w/o DIM')
    
    for i, n_app in enumerate(num_apps):
        plt.text(x_dim[i], means_999_dim[i], str(n_app), fontsize=6, verticalalignment='bottom', horizontalalignment='right')
    
    for i, n_app in enumerate(num_apps_short):
        plt.text(x_dimoff[i], means_999_dimoff[i], str(n_app), fontsize=6, verticalalignment='bottom', horizontalalignment='right')
    plt.legend(frameon=False)
    plt.xlabel('Throughput (mIOPS)')
    plt.ylabel('P99.9 Latency ($\mu$s)')
    plt.grid(True, linestyle='--', alpha=0.2)
    plt.ylim(0, 10000)
    plt.xlim(0, 0.4)
    plt.tight_layout()
    plt.show()
    # plt.savefig(f'./results/{hd}_{our_patch}.pdf', dpi=300)

if __name__ == "__main__":
    main()
