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

# Define parameters
hd="p1_airq"
our_patch="nohist"
c_state=1
num_apps = [16, 32, 64, 80]
flowsize = [64]
iodepth = [1]
dim = [0, 1]
pin = [1]
permute = [1]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 1]
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


def get_thread_pid_str(log_path):
    with open(log_path, "r") as log:
        lines = log.readlines()
        return lines[0].split()[0]


def get_thread_pids(log_path):
    pids = []
    with open(log_path, "r") as log:
        lines = log.readlines()
        for line in lines:
            if "pid:" not in line:
                continue
            pids.append(line.split()[4])
    return pids


def get_thread_pids_core(log_path, core):
    pids = []
    with open(log_path, "r") as log:
        lines = log.readlines()
        for line in lines:
            if "pid:" not in line or (f"cpu: {core}" not in line and f"core: {core}" not in line):
                continue
            pids.append(line.split()[4])
    return pids


def get_client_server_pid_map(results_dir, core):
    with open(os.path.join(results_dir, "client.log"), "r") as client_log:
        lines = client_log.readlines()
        client_pids = []
        client_pid_to_port = {}
        for line in lines:
            items = line.split()
            if "pid:" not in line or f"cpu: {core}" not in line:
                continue
            pid = items[4]
            port = items[7]
            client_pid_to_port[pid] = port
            client_pids.append(pid)
    
    with open(os.path.join(results_dir, "server.log"), "r") as server_log:
        lines = server_log.readlines()
        server_pids = []
        port_to_server_pid = {}
        for line in lines:
            if "pid:" not in line or f"core: {core}" not in line:
                continue
            items = line.split()
            pid = items[4]
            port = items[7]
            port_to_server_pid[port] = pid
            server_pids.append(pid)

    client_pid_to_server_pid = {}
    for client_pid, port in client_pid_to_port.items():
        if port in port_to_server_pid:
            client_pid_to_server_pid[client_pid] = port_to_server_pid[port]
    
    return client_pid_to_server_pid


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

        client_pids = get_thread_pids_core(os.path.join(result_dir, f"client.log"), 96)
        server_pids = get_thread_pids_core(os.path.join(result_dir, f"server.log"), 96)

        client_vruntime_path = os.path.join(result_dir, "iter_thread_client.log")
        server_vruntime_path = os.path.join(result_dir, "iter_thread_server.log")

        client_thread_vruntime = [[] for _ in range(n//2)]
        server_thread_vruntime = [[] for _ in range(n//2)]
        client_rq_vruntime = []
        server_rq_vruntime = []

        next_all = False
        next_rq = False
        activated = False

        # Part 1: readout vruntime and runqueue size
        with open(client_vruntime_path, "r") as client_vruntime_log:
            lines = client_vruntime_log.readlines()
            for line in lines:
                items = line.split()
                if "All-thread IDs" in line:
                    if items[-1] in client_pids:
                        activated = True
                        next_all = True
                        next_rq = False
                        continue
                    else:
                        activated = False
                elif next_all:
                    next_all = False
                    vruntime_line = [int(items[-1-i]) for i in range(n//2)]
                    vruntime_line.reverse()
                    vruntime_line_normed = norm_vruntime(vruntime_line)
                    for i in range(n//2):
                        client_thread_vruntime[i].append(vruntime_line_normed[i])
                elif "Runqueue thread IDs" in line:
                    if items[-1] in client_pids or activated: # if there is no thread in the rq, but the "All-thread IDs" line shows the results belong to the session, we still need to record an empty rq
                        next_rq = True
                        next_all = False
                        continue
                elif next_rq:
                    next_rq = False
                    client_rq_vruntime.append([int(items[i]) for i in range(11, len(items))] if (len(items) > 11) else [])

        next_all = False
        next_rq = False
        activated = False

        with open(server_vruntime_path, "r") as server_vruntime_log:
            lines = server_vruntime_log.readlines()
            for line in lines:
                items = line.split()
                if "All-thread IDs" in line:
                    if items[-1] in server_pids:
                        activated = True
                        next_all = True
                        next_rq = False
                        continue
                    else:
                        activated = False
                elif next_all:
                    next_all = False
                    vruntime_line = [int(items[-1-i]) for i in range(n//2)]
                    vruntime_line.reverse()
                    vruntime_line_normed = norm_vruntime(vruntime_line)
                    for i in range(n//2):
                        server_thread_vruntime[i].append(vruntime_line_normed[i])
                elif "Runqueue thread IDs" in line:
                    if items[-1] in server_pids or activated: # if there is no thread in the rq, but the "All-thread IDs" line shows the results belong to the session, we still need to record an empty rq
                        next_rq = True
                        next_all = False
                        continue
                elif next_rq:
                    next_rq = False
                    server_rq_vruntime.append([int(items[i]) for i in range(11, len(items))] if (len(items) > 11) else [])

        client_rq_sizes = [len(rq) for rq in client_rq_vruntime]
        server_rq_sizes = [len(rq) for rq in server_rq_vruntime]

        # Part 3: align vruntime and runqueue size time series
        client_pid_to_server_pid = get_client_server_pid_map(result_dir, 96)
        client_pids.sort() # client_pids comes from client.log which is not sorted, but iter_thread_client.log has sorted vruntime output.
        server_pids.sort()
    
        print(client_pid_to_server_pid)
        print(client_pids, server_pids)

        mapped_server_pids = [client_pid_to_server_pid[cp] for cp in client_pids]

        reordered_server_vruntimes = []
        for client_pid in client_pids:
            target_server_pid = client_pid_to_server_pid[client_pid]
            target_index = server_pids.index(target_server_pid)
            print(client_pid, target_server_pid, target_index)
            reordered_server_vruntimes.append(server_thread_vruntime[target_index])


        # delta vruntime in client side
        plt.figure(figsize=(5, 5*0.618))
        for i in range(n//2):
            plt.plot(client_thread_vruntime[i], label=f"thread {i}")
        plt.yscale("log")
        plt.xlabel("time (s)")
        plt.ylabel("delta vruntime")
        plt.tight_layout()
        plt.savefig(f'./results/{hd}_{our_patch}_{n}_{io}_{d}_{run}_client_vruntime.pdf')
        plt.close()

        plt.figure(figsize=(5, 5*0.618))
        for i in range(n//2):
            plt.plot(server_thread_vruntime[i], label=f"thread {i}")
        plt.yscale("log")
        plt.xlabel("time (s)")
        plt.ylabel("delta vruntime")
        plt.tight_layout()
        plt.savefig(f'./results/{hd}_{our_patch}_{n}_{io}_{d}_{run}_server_vruntime.pdf')
        plt.close()

        plt.figure(figsize=(5, 5*0.618))
        plt.plot(server_rq_sizes, label="server")
        plt.plot(client_rq_sizes, label="client")
        plt.legend()
        plt.xlabel("time (s)")
        plt.ylabel("runqueue threads")
        plt.ylim(0, n)
        plt.tight_layout()
        plt.savefig(f'./results/{hd}_{our_patch}_{n}_{io}_{d}_{run}_all_runqueue.pdf')
        plt.close()

plt.show()

if __name__ == "__main__":
    main()