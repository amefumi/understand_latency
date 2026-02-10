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
our_patch="loaded1"
c_state=1
num_apps = [64, 80]
# need to run 8, 16
# num_apps = [40, 44, 48, 52, 56]
# num_apps =[84, 88]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
# iodepth = [1, 2, 4, 8, 16]
iodepth = [1]
dim = [0, 1]
pin = [1]
permute = [1]
hrtick = [0]
sched = [0]
cores = [1]
loads = [1, 2, 5, 10]
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
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, loads, runs)

    for n, f, io, d, p, perm, h, s, core, load, run in combinations:
        result_dir = f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{io}_{d}_{p}_{perm}_{h}_{s}_{core}_{load}_{run}"
        client_cpus = get_thread_pids(os.path.join(result_dir, f"client.log"))
        server_cpus = get_thread_pids(os.path.join(result_dir, f"server.log"))

        client_vruntime_path = os.path.join(result_dir, "iter_thread_client.log")
        server_vruntime_path = os.path.join(result_dir, "iter_thread_server.log")

        client_vruntimes = [[] for _ in range(n*core//2)]
        server_vruntimes = [[] for _ in range(n*core//2)]

        with open(client_vruntime_path, "r") as client_vruntime_log:
            lines = client_vruntime_log.readlines()
            record_next_line = False
            for line in lines:
                items = line.split()
                if record_next_line:
                    record_next_line = False
                    vruntime_line = []
                    for i in range(n*core//2):
                        vruntime_line.append(int(items[-i-1]))
                    vruntime_line.reverse()
                    vruntime_line_normed = norm_vruntime(vruntime_line)
                    for i in range(n*core//2):
                        client_vruntimes[i].append(vruntime_line_normed[i])
                    continue
                if items[-1] in client_cpus and items[-2] in client_cpus:
                    record_next_line = True

        with open(server_vruntime_path, "r") as server_vruntime_log:
            lines = server_vruntime_log.readlines()
            record_next_line = False
            for line in lines:
                items = line.split()
                if record_next_line:
                    record_next_line = False
                    vruntime_line = []
                    for i in range(n*core//2):
                        vruntime_line.append(int(items[-i-1]))
                    vruntime_line.reverse()
                    vruntime_line_normed = norm_vruntime(vruntime_line)
                    for i in range(n*core//2):
                        server_vruntimes[i].append(vruntime_line_normed[i])
                    continue
                if items[-1] in server_cpus and items[-2] in server_cpus:
                    record_next_line = True

        # Adjusting the order of server's vruntime to match client's
        # client.log records client_pid -> port mapping, and server.log records port -> server_pid mapping
        with open(os.path.join(result_dir, "client.log"), "r") as client_log:
            lines = client_log.readlines()
            client_pids = []
            client_pid_to_port = {}
            for line in lines:
                items = line.split()
                if "pid:" not in line or "cpu: 96" not in line:
                    continue
                pid = items[4]
                port = items[7]
                client_pid_to_port[pid] = port
                client_pids.append(pid)
        
        with open(os.path.join(result_dir, "server.log"), "r") as server_log:
            lines = server_log.readlines()
            server_pids = []
            port_to_server_pid = {}
            for line in lines:
                if "pid:" not in line or "core: 96" not in line:
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
        
        print(client_pid_to_server_pid)

        client_pids.sort()
        server_pids.sort()

        print(client_pids, server_pids)
        mapped_server_pids = [client_pid_to_server_pid[cp] for cp in client_pids]

        # Reorder server_vruntimes according to client_vruntimes
        reordered_server_vruntimes = []
        for client_pid in client_pids:
            target_server_pid = client_pid_to_server_pid[client_pid]
            target_index = server_pids.index(target_server_pid)
            print(client_pid, target_server_pid, target_index)
            reordered_server_vruntimes.append(server_vruntimes[target_index])

        server_vruntimes = reordered_server_vruntimes

        plt.figure(figsize=(5, 5*0.618))
        for c in range(n*core//2):
            plt.plot(client_vruntimes[c], color=colors[c%20], label=f'{client_pids[c]}')
        # plt.text(0.5, 0.5, f'lines={len(client_vruntimes)}', horizontalalignment='center', verticalalignment='center', transform=plt.gca().transAxes, fontsize=12)
        plt.yscale('log')
        # plt.legend()
        plt.savefig(f'./results/{hd}_{our_patch}_{n*core}_{io}_{d}_client_{load}_{run}_loaded.pdf')
        plt.close()

        plt.figure(figsize=(5, 5*0.618))
        for c in range(n*core//2):
            plt.plot(server_vruntimes[c], color=colors[c%20], label=f'{mapped_server_pids[c]}')
        plt.yscale('log')
        # plt.legend()
        plt.savefig(f'./results/{hd}_{our_patch}_{n*core}_{io}_{d}_server_{load}_{run}_loaded.pdf')
        plt.close()

if __name__ == "__main__":
    main()