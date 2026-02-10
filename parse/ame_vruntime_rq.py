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
our_patch="runqueue"
c_state=1
num_apps = [16, 32, 64]
# need to run 8, 16
# num_apps = [40, 44, 48, 52, 56]
# num_apps =[84, 88]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
# iodepth = [1, 2, 4, 8, 16]
iodepth = [1, 2, 4, 8, 16]
dim = [0, 1]
pin = [1]
permute = [1]
hrtick = [0]
sched = [0]
cores = [1]
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
        client_cpus = get_thread_pids(os.path.join(result_dir, f"client.log"))
        server_cpus = get_thread_pids(os.path.join(result_dir, f"server.log"))

        client_vruntime_path = os.path.join(result_dir, "iter_thread_client.log")
        server_vruntime_path = os.path.join(result_dir, "iter_thread_server.log")

        client_rq = []
        server_rq = []

        with open(client_vruntime_path, "r") as client_vruntime_log:
            lines = client_vruntime_log.readlines()
            for line in lines:
                if "CFS thread IDs on CPU" in line:
                    sample_rq = []
                    items = line.split()
                    last_thread_id = items[-1]
                    if last_thread_id in client_cpus:
                        for i in range(12, len(items)):
                            sample_rq.append(int(items[i]))
                        client_rq.append(sample_rq)
        
        client_rq_sizes = [len(rq) for rq in client_rq]

        with open(server_vruntime_path, "r") as server_vruntime_log:
            lines = server_vruntime_log.readlines()
            for line in lines:
                if "CFS thread IDs on CPU" in line:
                    sample_rq = []
                    items = line.split()
                    last_thread_id = items[-1]
                    if last_thread_id in server_cpus:
                        for i in range(12, len(items)):
                            sample_rq.append(int(items[i]))
                        server_rq.append(sample_rq)

        server_rq_sizes = [len(rq) for rq in server_rq]

        plt.figure(figsize=(5, 5*0.618))
        plt.plot(client_rq_sizes)
        plt.ylim(0, n*core//2)
        # plt.show()
        plt.savefig(f'./results/{hd}_{our_patch}_{n*core}_{io}_{d}_client_{run}_runqueue.pdf')
        plt.close()

        plt.figure(figsize=(5, 5*0.618))
        plt.plot(server_rq_sizes)
        plt.ylim(0, n*core//2)
        # plt.show()
        plt.savefig(f'./results/{hd}_{our_patch}_{n*core}_{io}_{d}_server_{run}_runqueue.pdf')
        plt.close()

if __name__ == "__main__":
    main()