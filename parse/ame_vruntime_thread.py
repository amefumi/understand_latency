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

# Input a single configuration here for thread vruntime plotting
hd="p1_airq"
our_patch="1"
c_state=1
num_apps = 32
flowsize = 64
iodepth = 1
dim = 0
pin = 1
permute = 1
hrtick = 0
sched = 0
core = 1
run = 4

# Plot threads
threads = [0, 1, 2, 3, 4, 5, 6, 7]


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
    result_dir = f"../results/{hd}_{our_patch}_{c_state}/{num_apps}_{flowsize}_{iodepth}_{dim}_{pin}_{permute}_{hrtick}_{sched}_{core}_{run}"

    client_pids = get_thread_pids(os.path.join(result_dir, f"client.log"))
    server_pids = get_thread_pids(os.path.join(result_dir, f"server.log"))

    client_vruntime_path = os.path.join(result_dir, "iter_thread_client.log")
    server_vruntime_path = os.path.join(result_dir, "iter_thread_server.log")

    client_vruntimes = [[] for _ in range(num_apps//2)]
    server_vruntimes = [[] for _ in range(num_apps//2)]

    with open(client_vruntime_path, "r") as client_vruntime_log:
        lines = client_vruntime_log.readlines()
        record_next_line = False
        for line in lines:
            items = line.split()
            if record_next_line:
                record_next_line = False
                vruntime_line = []
                for i in range(num_apps//2):
                    vruntime_line.append(int(items[-i-1]))
                vruntime_line_normed = norm_vruntime(vruntime_line)
                for i in range(num_apps//2):
                    client_vruntimes[i].append(vruntime_line_normed[i])
                continue
            if items[-1] in client_pids and items[-2] in client_pids:
                record_next_line = True

    with open(server_vruntime_path, "r") as server_vruntime_log:
        lines = server_vruntime_log.readlines()
        record_next_line = False
        for line in lines:
            items = line.split()
            if record_next_line:
                record_next_line = False
                vruntime_line = []
                for i in range(num_apps//2):
                    vruntime_line.append(int(items[-i-1]))
                vruntime_line_normed = norm_vruntime(vruntime_line)
                for i in range(num_apps//2):
                    server_vruntimes[i].append(vruntime_line_normed[i])
                continue
            if items[-1] in server_pids and items[-2] in server_pids:
                record_next_line = True

    # Adjusting the order of server's vruntime to match client's
    # client.log records client_pid -> port mapping, and server.log records port -> server_pid mapping
    with open(os.path.join(result_dir, "client.log"), "r") as client_log:
        lines = client_log.readlines()
        client_pids = []
        client_pid_to_port = {}
        for line in lines:
            items = line.split()
            if "pid:" not in line or "cpu: 96" not in line: # Only consider server threads on core 96
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
            if "pid:" not in line or "core: 96" not in line: # Only consider server threads on core 96
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

    client_pids.sort() # This is the client_vruntime order
    server_pids.sort() # This is the original server_vruntime order
    mapped_server_pids = [client_pid_to_server_pid[cp] for cp in client_pids]

    # Reorder server_vruntimes according to client_vruntimes
    reordered_server_vruntimes = []
    for client_pid in client_pids:
        target_server_pid = client_pid_to_server_pid[client_pid]
        target_index = server_pids.index(target_server_pid)
        print(client_pid, target_server_pid, target_index)
        reordered_server_vruntimes.append(server_vruntimes[target_index])

    server_vruntimes = reordered_server_vruntimes

    for thread in range(len(client_vruntimes)):
        # The length of client and server vruntime records may differ by a few seconds, I think the effect is negligible
        thread_server_vruntimes = server_vruntimes[thread]
        thread_client_vruntimes = client_vruntimes[thread]
        plt.figure(figsize=(10, 5))
        plt.plot(thread_client_vruntimes, color='blue', label=f'Client {client_pids[thread]}')
        plt.plot(thread_server_vruntimes, color='orange', label=f'Server {mapped_server_pids[thread]}')
        plt.yscale('log')
        plt.legend()
        plt.savefig(f'./results/{hd}_{our_patch}_{num_apps}_{iodepth}_{dim}_thread_{thread}_{client_pids[thread]}_{mapped_server_pids[thread]}_{run}_reorder.pdf')


if __name__ == "__main__":
    main()