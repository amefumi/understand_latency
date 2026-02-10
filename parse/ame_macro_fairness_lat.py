#!/usr/bin/env python3
import os
import re
import subprocess
import numpy as np
from itertools import product
from statistics import stdev
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# hd="p1_dirq"
# our_patch="1"
# c_state=1
# num_apps = [64 ]#44, 48, 52, 56, 60, 64, 68, 72, 76, 80]
# 8 is lost
# num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64,  68, 72, 76, 80,   100, 112, 128]

# num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64,  68, 72, 76, 80, 84, 88, 92, 96,]

# flowsize = [64]
# iodepth = [1]
# dim = [0, 1]
# pin = [1]
# permute = [1]
# hrtick = [0]
# sched = [0]
# cores = [1]
# runs = [0, 1, 2, 3, 4]


hd="p1_airq"
our_patch="imbalanced2"
c_state=1

num_apps = [32]
flowsize = [64]
iodepth = [1]
dim = [0, 1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [16]
runs = [0, 1]

colors = ['blue', 'orange', 'green', 'red', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']

def main():
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores)
    
    combination_results_dim = [[] for i in range(len(num_apps))] # a two dimension list of tuples (runs, average_throughput, throughput_0, throughput_1, ..., throughput_n)
    combination_results_dimoff = [[] for i in range(len(num_apps))]  # a two dimension list of tuples (runs, average_throughput, throughput_0, throughput_1, ..., throughput_n)
    # A single result = tuple(throughput, avg_latency, p99latency, p999latency)

    # Get performance for each experiment
    for n, f, i, d, p, perm, h, s, core in combinations:
        comb_lat_999 = []

        for run in runs:
            n_apps = n
            run_lat_999 = []

            result_dir = f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}"
            if not os.path.exists(os.path.join(result_dir, "netperf-0_thpt.log")):
                print(f"Skipping missing dir {result_dir}")
                continue

            for i_thread in range(n_apps):
                thread_netperf_log_path = os.path.join(result_dir, f"netperf-{i_thread}_thpt.log")
                with open(thread_netperf_log_path, "r") as thread_netperf_log:
                    line = thread_netperf_log.readline()
                    params = line.split()
                    run_lat_999.append(float(params[4]))
            comb_lat_999.append(tuple([run] + run_lat_999))
        
        if d == 1:
            combination_results_dim[num_apps.index(n)] += comb_lat_999
        else:
            combination_results_dimoff[num_apps.index(n)] += comb_lat_999

    print(combination_results_dim, combination_results_dimoff)

    plt.figure(figsize=(8, 8*0.5))

    x_base = np.array(range(1, len(num_apps)+1))
    x_labels = [str(n) for n in num_apps]
    plt.xticks(x_base, x_labels)

    # draw all throughput_i points
    for i in range(len(num_apps)):
        for j in range(len(combination_results_dim[i])):
            x = x_base[i] - (combination_results_dim[i][j][0]+0.5) * (0.4/len(runs))
            plt.scatter([ x ] * (len(combination_results_dim[i][j]) - 1), combination_results_dim[i][j][1:], color=colors[j], s=1)

    # plt.text(len(num_apps)-10, 0.03, 'left: w/ DIM; right: w/o DIM', color='black', fontsize=10)
    # plt.scatter([len(num_apps)+10], [0], color='blue', s=5, label='w/ DIM')

    # # draw all throughput_i points
    # for i in range(len(num_apps)):
    #     for j in range(len(combination_results_dimoff[i])):
    #         x = x_base[i] + (combination_results_dimoff[i][j][0]+0.5) * (0.4/len(runs))
    #         plt.scatter([ x ] * (len(combination_results_dimoff[i][j]) - 2), combination_results_dimoff[i][j][2:], color=colors[j+5], s=1)

    # plt.scatter([len(num_apps)+10], [0], color='red', s=5, label='w/o DIM')

    plt.xlabel('Number of Threads')
    plt.ylabel('P99.9 Latency (us)')
    plt.grid(True, linestyle='--', alpha=0.7)
    # plt.legend()
    plt.yscale('log', base=10)
    plt.ylim(1e2, 1e3)
    plt.xlim(0, len(num_apps)+1)
    plt.tight_layout()
    plt.show()
    # plt.savefig(f'./results/{hd}_{our_patch}.pdf', dpi=300)

if __name__ == "__main__":
    main()
