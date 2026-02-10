#!/usr/bin/env python3
import os
import re
import subprocess
import numpy as np
from itertools import product
from statistics import stdev
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import re
from typing import List
colors = plt.cm.tab20(np.linspace(0, 1, 20))

hd="p1_airq"
our_patch="imbalanced2"
c_state=1
# num_apps = [64 ]#44, 48, 52, 56, 60, 64, 68, 72, 76, 80]
# 8 is lost
# num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64,  68, 72, 76, 80, 84, 88, 92, 96]

# num_apps = [16, 32, 40, 48, 56]

num_apps = [32]
flowsize = [64]
iodepth = [1, 2, 4, 8, 16]
dim = [0, 1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [16]
runs = [0, 1]

cpu_list = [32, 96]


def get_thread_pids(log_path):
    pids = []
    with open(log_path, "r") as log:
        lines = log.readlines()
        for line in lines:
            if "pid:" not in line:
                continue
            pids.append(line.split()[4])
    return pids


def norm_vruntime(vruntime_line):
    min_vruntime = min(vruntime_line)
    normed = []
    for v in vruntime_line:
        normed.append(v - min_vruntime + 1)
        # normed.append(v + 1)
    return normed


def main():
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs)

    for n, f, io, d, p, perm, h, s, core, run in combinations:
        result_dir = f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{io}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}"
        server_cpus = get_thread_pids(os.path.join(result_dir, f"server.log"))

        server_vruntime_path = os.path.join(result_dir, "iter_thread_server.log")

        server_vruntimes = [[] for _ in range(n//2)]

        with open(server_vruntime_path, "r") as server_vruntime_log:
            lines = server_vruntime_log.readlines()
            record_next_line = False
            for line in lines:
                items = line.split()
                if record_next_line:
                    record_next_line = False
                    vruntime_line = []
                    for i in range(n//2):
                        vruntime_line.append(int(items[-i-1]))
                    vruntime_line.reverse()
                    vruntime_line_normed = norm_vruntime(vruntime_line)
                    for i in range(n//2):
                        server_vruntimes[i].append(vruntime_line_normed[i])
                    continue
                if items[-1] in server_cpus and items[-2] in server_cpus:
                    record_next_line = True

        plt.figure(figsize=(5, 5*0.618))
        for c in range(n//2):
            plt.plot(server_vruntimes[c], color=colors[c%20])
        plt.yscale('log')
        # plt.ylim(9e-1, 1e5)
        # plt.legend()
        plt.savefig(f'./results/{hd}_{our_patch}_{n}_{io}_{d}_server_{run}_reorder.pdf')
        plt.close()

if __name__ == "__main__":
    main()