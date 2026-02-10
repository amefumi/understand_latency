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

hd="dc_airq"
our_patch="imbalanced2"
c_state=3
num_apps = [16, 32, 64]
flowsize = [64]
iodepth = [1]
dim = [0, 1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [16]
runs = [0, 1]
# Testing DIM disabled parameters
# timeout = [90]
# pkt_threshold = [28]
breakdown = False


def get_latency(log_path):
    with open(log_path, "r") as log:
        lines = log.readlines()
        return int(lines[0].split()[2])


def get_throughput(log_path):
    with open(log_path, "r") as log:
        lines = log.readlines()
        return float(lines[-1].split()[0])


def get_thread_latency999(log_path):
    with open(log_path, "r") as log:
        lines = log.readlines()
        return int(lines[0].split()[4])


def get_thread_throughput(log_path):
    with open(log_path, "r") as log:
        lines = log.readlines()
        return float(lines[0].split()[5])


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

        latency = get_latency(os.path.join(result_dir, "latency.log"))
        throughput = get_throughput(os.path.join(result_dir, "linux_latency"))

        server_thread_vruntime = [[] for _ in range(n)]
        server_rq_vruntime = []

        last_client_vruntime = None
        client_thread_vruntime_first = []
        client_thread_vruntime_last = []
        client_thread_vruntime_delta = []
        client_rq_vruntime = []

        next_all = False
        next_rq = False
        activated = False

        with open(client_vruntime_path, "r") as client_vruntime_log:
            lines = client_vruntime_log.readlines()
            for line in lines:
                items = line.split()
                if "All-thread IDs:" in line:
                    if items[-1] in client_cpus:
                        activated = True
                        next_all = True
                        next_rq = False
                        continue
                    else:
                        activated = False
                elif next_all:
                    next_all = False
                    last_client_vruntime = [int(items[-1-i]) for i in range(n)]
                    if len(client_thread_vruntime_first) == 0:
                        client_thread_vruntime_first = last_client_vruntime
                elif "Runqueue thread IDs" in line:
                    if items[-1] in client_cpus or activated: # if there is no thread in the rq, but the "All-thread IDs" line shows the results belong to the session, we still need to record an empty rq
                        next_rq = True
                        next_all = False
                        continue
                elif next_rq:
                    next_rq = False
                    client_rq_vruntime.append([int(items[i]) for i in range(9, len(items))] if (len(items) > 9) else [])
            client_thread_vruntime_last = last_client_vruntime
            client_thread_vruntime_delta = [client_thread_vruntime_last[i] - client_thread_vruntime_first[i] for i in range(n)]
            client_thread_vruntime_delta.reverse()

        next_all = False
        next_rq = False
        activated = False

        with open(server_vruntime_path, "r") as server_vruntime_log:
            lines = server_vruntime_log.readlines()
            for line in lines:
                items = line.split()
                if "All-thread IDs:" in line:
                    if items[-1] in server_cpus:
                        activated = True
                        next_all = True
                        next_rq = False
                        continue
                    else:
                        activated = False
                elif next_all:
                    next_all = False
                    vruntime_line = [int(items[-1-i]) for i in range(n)]
                    vruntime_line_normed = norm_vruntime(vruntime_line)
                    vruntime_line_normed.reverse()
                    for i in range(n):
                        server_thread_vruntime[i].append(vruntime_line_normed[i])
                elif "Runqueue thread IDs" in line:
                    if items[-1] in server_cpus or activated: # if there is no thread in the rq, but the "All-thread IDs" line shows the results belong to the session, we still need to record an empty rq
                        next_rq = True
                        next_all = False
                        continue
                elif next_rq:
                    next_rq = False
                    server_rq_vruntime.append([int(items[i]) for i in range(9, len(items))] if (len(items) > 9) else [])

        client_rq_sizes = [len(rq) for rq in client_rq_vruntime]
        server_rq_sizes = [len(rq) for rq in server_rq_vruntime]

        threads_latency999 = []
        threads_throughput = []
        threads = np.arange(n)

        for i in range(n):
            thread_log_path = os.path.join(result_dir, f"netperf-{i}_thpt.log")
            threads_latency999.append(get_thread_latency999(thread_log_path))
            threads_throughput.append(get_thread_throughput(thread_log_path)/1e6)

        # delta vruntime in client side
        plt.figure(figsize=(5, 5*0.618))
        plt.plot(norm_vruntime(client_thread_vruntime_delta))
        plt.ylim(0, max(norm_vruntime(client_thread_vruntime_delta))*1.1)
        plt.xlabel("thread index")
        plt.ylabel("delta vruntime")
        plt.tight_layout()
        plt.savefig(f'./results/{hd}_{our_patch}_{c_state}_{n}_{io}_{d}_{run}_client_absvrun.pdf')
        plt.close()

        plt.figure(figsize=(5, 5*0.618))
        plt.plot(server_rq_sizes, label="server")
        plt.plot(client_rq_sizes, label="client")
        plt.legend()
        plt.xlabel("time (s)")
        plt.ylabel("runqueue threads")
        plt.ylim(0, n)
        plt.tight_layout()
        plt.savefig(f'./results/{hd}_{our_patch}_{c_state}_{n}_{io}_{d}_{run}_all_runqueue.pdf')
        plt.close()

        plt.figure(figsize=(5, 5*0.618))
        for i in range(n):
            plt.plot(server_thread_vruntime[i], label=f"thread {i}")
        plt.yscale("log")
        plt.xlabel("time (s)")
        plt.ylabel("delta vruntime")
        plt.tight_layout()
        plt.savefig(f'./results/{hd}_{our_patch}_{c_state}_{n}_{io}_{d}_{run}_server_vruntime.pdf')
        plt.close()

        fig, ax1 = plt.subplots(figsize=(5, 5 * 0.618))
        ax1.set_xlabel('Thread index')

        ax1.set_ylabel('Latency (µs)', color='tab:blue')
        ax1.plot(threads, threads_latency999, marker='o', color='tab:blue', label='Latency (99.9%)')
        ax1.tick_params(axis='y', labelcolor='tab:blue')

        ax2 = ax1.twinx()
        ax2.set_ylabel('Throughput (MIOPS)', color='tab:red')
        ax2.plot(threads, threads_throughput, marker='s', linestyle='--', color='tab:red', label='Throughput')
        ax2.tick_params(axis='y', labelcolor='tab:red')
        fig.tight_layout()
        fig.text(0.2, 0.6, f"Throughput: {throughput/1e6:.4f} MIOPS\nP999 Latency: {latency:.1f} µs", fontsize=13, bbox=dict(facecolor='white', alpha=0.7, edgecolor='gray', boxstyle='round'))
        plt.savefig(f'./results/{hd}_{our_patch}_{c_state}_{n}_{io}_{d}_{run}_summary.pdf')
        plt.close() 

plt.show()

if __name__ == "__main__":
    main()