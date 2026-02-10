#!/usr/bin/env python3
import os
import re
import subprocess
import numpy as np
from itertools import product
from statistics import stdev
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.colors as mcolors


colors = list(mcolors.TABLEAU_COLORS.keys())
labels = ["cIRQa w/ DIM", "Default IRQa w/ DIM"]
hds = ["p1_airq", "p1_dirq"]
our_patch="1"
c_state=1
num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64,  68, 72, 76, 80, 84, 88,92, 96,  ]#100, 112, 128]
num_apps_short = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64,  68, 72, 76, 80, 84, 88,92, 96,  ]

flowsize = [64]
iodepth = [1]
dim = [1]
pin = [1]
permute = [1]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 1, 2, 4]


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
    
    plt.figure(figsize=(8, 8*0.618))

    for i_hd, hd in enumerate(hds):
        combination_results = []
        combination_results_dim = []
        combination_results_dimoff = []

        combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores)
        for n, f, i, d, p, perm, h, s, core in combinations:
            comb_lats = []
            comb_lats_99 = []
            comb_lats_999 = []
            comb_throughput = []

            for run in runs:
                result_dir = f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}"
                latency_log = os.path.join(f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}", "latency.log")
                thpt_log = os.path.join(f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}", "linux_latency")

                print(latency_log)

                if not os.path.exists(os.path.join(result_dir, "netperf-0_thpt.log")):
                    print(f"Skipping missing dir {result_dir}")
                    continue

                if not os.path.exists(latency_log):
                    print(f"Skipping missing dir {result_dir}")
                    continue

                with open(latency_log, "r") as run_lat_log:
                    lats = run_lat_log.readline().split()
                    comb_lats.append(float(lats[0]))
                    comb_lats_99.append(float(lats[1]))
                    comb_lats_999.append(float(lats[2]))
                    
                with open(thpt_log, "r") as run_thpt_log:
                    _ = run_thpt_log.readline()
                    comb_throughput.append(float(run_thpt_log.readline().split()[0]))

            # Average over runs
            lat = tuple(comb_lats)
            lat_99 = tuple(comb_lats_99)
            lat_999 = tuple(comb_lats_999)
            avg_throughput = sum(comb_throughput) / len(comb_throughput)
            
            combination_results.append((avg_throughput, lat, lat_99, lat_999, n*core))

        combination_results.sort(key=lambda x: x[4])

        print(f"Results for {hd}:" + str(combination_results))

        # Plot throughput vs latency (p999)
        throughputs = [res[0]/1e6 for res in combination_results]
        latencies_999 = [res[3] for res in combination_results]

        for thpt, samples in zip(throughputs, latencies_999):
            xs = np.full(len(samples), thpt)
            plt.scatter(xs, samples, s=2, alpha=1, edgecolors='none', label=None, color=colors[i_hd], zorder=2)

        # for thpt, samples in zip(throughputs_dimoff, latencies_999_dimoff):
        #     xs = np.full(len(samples), thpt)
        #     plt.scatter(xs, samples, s=1, alpha=0.3, edgecolors='none', label=None, color='orange', zorder=2)

        x = np.array(throughputs)
        means_999 = [np.mean(lat) for lat in latencies_999]
        plt.plot(x, means_999, marker='o', linestyle='-', linewidth=1, label=labels[i_hd])

        # x_dimoff = np.array(throughputs_dimoff[0:len(num_apps_short)])
        # means_999_dimoff = [np.mean(lat) for lat in latencies_999_dimoff[0:len(num_apps_short)]]
        # plt.plot(x_dimoff, means_999_dimoff, marker='o', linestyle='-', linewidth=1, label='w/o DIM')
        # print(x, means_999)
        for i, n_app in enumerate(num_apps_short):
            plt.text(x[i], means_999[i], str(n_app), fontsize=6, verticalalignment='bottom', horizontalalignment='right')
        
        # for i, n_app in enumerate(num_apps_short):
        #     plt.text(x_dimoff[i], means_999_dimoff[i], str(n_app), fontsize=6, verticalalignment='bottom', horizontalalignment='right')

    plt.legend(frameon=False)
    plt.xlabel('Throughput (mIOPS)')
    plt.ylabel('P99.9 Latency ($\mu$s)')
    plt.grid(True, linestyle='--', alpha=0.2)
    plt.ylim(0, 8000)
    plt.xlim(0, 0.4)
    plt.tight_layout()
    plt.show()
    # plt.savefig(f'./results/{hd}_{our_patch}.pdf', dpi=300)

if __name__ == "__main__":
    main()