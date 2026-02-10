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


hd="p2_airq"
our_patch="vruntime"
c_state=1
# num_apps = [64 ]#44, 48, 52, 56, 60, 64, 68, 72, 76, 80]
# 8 is lost
# num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64,  68, 72, 76, 80, 84, 88, 92, 96]

num_apps = [32, 40, 48, 52]
flowsize = [64]
iodepth = [1, 2, 4, 8, 16, 32]
dim = [0, 1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 0]

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
        normed.append(v - min_vruntime)
    return normed


def main():
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs)

    for n, f, i, d, p, perm, h, s, core, run in combinations:
        result_dir = f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}"
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
                if "pid:" not in line or "cpu: 32" not in line:
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
                if "pid:" not in line or "core: 32" not in line:
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
        
        client_pids.sort() # This is the client_vruntime order
        server_pids.sort() # This is the original server_vruntime order
        min_server_pid = min(server_pids)

        # Reorder server_vruntimes according to client_vruntimes
        reordered_server_vruntimes = []
        for client_pid in client_pids:
            target_server_pid = client_pid_to_server_pid[client_pid]
            target_index = int(target_server_pid) - int(min_server_pid)
            print(client_pid, target_server_pid, target_index)
            reordered_server_vruntimes.append(server_vruntimes[target_index])

        server_vruntimes = reordered_server_vruntimes
        print(client_pids, server_pids, client_pid_to_server_pid)
        
        exit()

        plt.figure(figsize=(5, 5*0.618))
        for i in range(n*core//2):
            plt.plot(client_vruntimes[i])
        plt.yscale('log')
        plt.savefig(f'./results/{hd}_vruntime_{n*core}_{d}_client_{run}.pdf')

        plt.figure(figsize=(5, 5*0.618))
        for i in range(n*core//2):
            plt.plot(server_vruntimes[i])
        plt.yscale('log')
        plt.savefig(f'./results/{hd}_vruntime_{n*core}_{d}_server_{run}.pdf')

if __name__ == "__main__":
    main()