#!/usr/bin/env python3
import os
import re
import subprocess
import numpy as np
from itertools import product
import matplotlib.pyplot as plt
import itertools


colors1 = plt.cm.tab20b(np.linspace(0, 1, 20))
colors2 = plt.cm.tab20c(np.linspace(0, 1, 20))
colors = np.vstack((colors1, colors2))

hd="airq_vruntime_fine"
our_patch="1"
c_state=1
num_apps = [52]
flowsize = [64]
iodepth = [1]
dim = [1]
pin = [1]
permute = [1]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0]


def get_latency999(log_path):
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


def build_cooccurrence(thread_pids_t, n_threads):
    C = np.zeros((n_threads, n_threads), dtype=int)
    for pids in thread_pids_t:
        for i, j in itertools.combinations(pids, 2):
            C[i, j] += 1
            C[j, i] += 1
    return C

def main():
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs)

    for n, f, io, d, p, perm, h, s, core, run in combinations:
        result_dir = f"/data0/projects/latency/{hd}_{our_patch}_{c_state}/{n}_{f}_{io}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}"

        client_pids = get_thread_pids_core(os.path.join(result_dir, f"client.log"), 96)
        server_pids = get_thread_pids_core(os.path.join(result_dir, f"server.log"), 96)
        assert len(client_pids) == n//2, "Client PIDs do not match expected count"
        assert len(server_pids) == n//2 , "Server PIDs do not match expected count"

        client_pids.sort()
        server_pids.sort()

        latency = get_latency999(os.path.join(result_dir, "latency.log"))
        throughput = get_throughput(os.path.join(result_dir, "linux_latency"))

        client_vruntime_path = os.path.join(result_dir, "iter_thread_client.log")
        server_vruntime_path = os.path.join(result_dir, "iter_thread_server.log")

        client_thread_vruntime = [[] for _ in range(n//2)]
        server_thread_vruntime = [[] for _ in range(n//2)]
        client_on_rq = [[] for _ in range(n//2)]
        server_on_rq = [[] for _ in range(n//2)]

        client_rq_pids = []
        server_rq_pids = []

        # Part 1: readout vruntime and runqueue size

        activated = 0
        time_index = -1
        scan_index = 0
        thread_pids = []
        thread_vruntimes = []
        rq_pids = []

        with open(client_vruntime_path, "r") as client_vruntime_log:
            lines = client_vruntime_log.readlines()
            for line in lines:
                items = line.split()
                if activated == 0 and "All-thread IDs:" in line and items[-1] in client_pids:
                    time_index += 1
                    activated = 3
                    scan_index = len(items)
                    for i in range(8, len(items)):
                        if items[i] in client_pids:
                            scan_index = i
                            break
                    thread_pids = [items[i] for i in range(scan_index, len(items))]
                elif activated == 3:
                    activated = 2
                    thread_vruntimes = [int(items[i]) for i in range(scan_index, len(items))]
                    thread_vruntimes = norm_vruntime(thread_vruntimes)
                elif activated == 2:
                    activated = 1
                    scan_index = len(items)
                    for i in range(9, len(items)):
                        if items[i] in client_pids:
                            scan_index = i
                            break
                    rq_pids = [items[i] for i in range(scan_index, len(items))] if (len(items) > scan_index) else []
                elif activated == 1:
                    activated = 0
                    client_rq_pids.append(rq_pids)
                    for i in range(len(thread_pids)):
                        if thread_pids[i] in client_pids:
                            index = client_pids.index(thread_pids[i])
                            client_thread_vruntime[index].append((time_index, thread_vruntimes[i]))
                    for i in range(len(rq_pids)):
                        if rq_pids[i] in client_pids:
                            index = client_pids.index(rq_pids[i])
                            client_on_rq[index].append(time_index)

        activated = 0
        time_index = -1
        thread_pids = []
        thread_vruntimes = []
        rq_pids = []
        scan_index = 0

        with open(server_vruntime_path, "r") as server_vruntime_log:
            lines = server_vruntime_log.readlines()
            for line in lines:
                items = line.split()
                if activated == 0 and "All-thread IDs on CPU" in line and items[-1] in server_pids:
                    time_index += 1
                    activated = 3
                    scan_index = len(items)
                    for i in range(8, len(items)):
                        if items[i] in server_pids:
                            scan_index = i
                            break
                    thread_pids = [items[i] for i in range(scan_index, len(items))]
                elif activated == 3:
                    activated = 2
                    thread_vruntimes = [int(items[i]) for i in range(scan_index, len(items))]
                    thread_vruntimes = norm_vruntime(thread_vruntimes)
                elif activated == 2:
                    activated = 1
                    scan_index = len(items)
                    for i in range(9, len(items)):
                        if items[i] in server_pids:
                            scan_index = i
                            break
                    rq_pids = [items[i] for i in range(scan_index, len(items))] if (len(items) > scan_index) else []
                elif activated == 1:
                    activated = 0
                    server_rq_pids.append(rq_pids)
                    for i in range(len(thread_pids)):
                        if thread_pids[i] in server_pids:
                            index = server_pids.index(thread_pids[i])
                            server_thread_vruntime[index].append((time_index, thread_vruntimes[i]))
                    for i in range(len(rq_pids)):
                        if rq_pids[i] in server_pids:
                            index = server_pids.index(rq_pids[i])
                            server_on_rq[index].append(time_index)


        # Part 2: align vruntime and runqueue size time series
        client_pid_to_server_pid = get_client_server_pid_map(result_dir, 96)
        reordered_server_thread_vruntime = []
        reordered_server_on_rq = []
        reordered_server_pids = []
        for client_pid in client_pids:
            target_server_pid = client_pid_to_server_pid[client_pid]
            target_index = server_pids.index(target_server_pid)
            reordered_server_thread_vruntime.append(server_thread_vruntime[target_index])
            reordered_server_on_rq.append(server_on_rq[target_index])
            reordered_server_pids.append(target_server_pid)

        server_thread_vruntimes = reordered_server_thread_vruntime
        server_on_rq = reordered_server_on_rq


        # Part 3: rq_affinity matrix for client and server
        for i in range(len(client_rq_pids)):
            for j in range(len(client_rq_pids[i])):
                if client_rq_pids[i][j] in client_pids:
                    client_rq_pids[i][j] = client_pids.index(client_rq_pids[i][j])
                else:
                    client_rq_pids[i][j] = -1

        for i in range(len(server_rq_pids)):
            for j in range(len(server_rq_pids[i])):
                if server_rq_pids[i][j] in reordered_server_pids:
                    server_rq_pids[i][j] = reordered_server_pids.index(server_rq_pids[i][j])
                else:
                    server_rq_pids[i][j] = -1


        # Part 4: plot figures
        assert len(client_thread_vruntime) == n//2
        assert len(server_thread_vruntimes) == n//2

        # client vruntime
        plt.figure(figsize=(5, 5*0.618))
        for i in range(n//2):
            time, vruntime = zip(*client_thread_vruntime[i]) # thread i's time and corresponding vruntime
            plt.plot(time, vruntime, label=f"thread {i}", color=colors[i%40])
        rq_vruntimes = [[] for _ in range(120)]
        for i in range(n//2):
            time, vruntime = zip(*client_thread_vruntime[i])
            on_rq = client_on_rq[i]  # thread i's on_rq time points
            on_rq_vruntime = [vruntime[time.index(t)] for t in on_rq] # thread i's vruntime at on_rq time points
            plt.scatter(on_rq, on_rq_vruntime, s=5, color=colors[i%40], edgecolors='black', zorder=3) # same color for thread i
            for j in range(len(on_rq)):
                rq_vruntimes[on_rq[j]].append(on_rq_vruntime[j])
        for i in range(len(rq_vruntimes)):
            # plt.scatter([i for _ in range(len(rq_vruntimes[i]))], rq_vruntimes[i], s=5, color=colors[i%40], edgecolors='black', zorder=2) # same color for time i
            if len(rq_vruntimes[i]) > 0:
                plt.text(i, max(rq_vruntimes[i])*1.2, str(len(rq_vruntimes[i])), horizontalalignment='center', color=colors[i%40], fontsize=4)
        plt.yscale("log")
        plt.xlabel("time (s)")
        plt.ylabel("Client vruntime")
        plt.tight_layout()
        plt.savefig(f'./results/{hd}_{our_patch}_{n}_{io}_{d}_{run}_client_vruntime.pdf')
        plt.close()

        # client on_rq
        plt.figure(figsize=(5, 5*0.618))
        for i in range(len(client_on_rq)):
            thread_rq = client_on_rq[i]
            # scatter thread_rq, with x = thread_rq, y = i
            plt.scatter(thread_rq, [i for _ in range(len(thread_rq))], s=10, color=colors[i%40], edgecolors='black', zorder=5)
            if len(thread_rq) > 0:
                plt.text(0, i+0.2, str(len(thread_rq)), horizontalalignment='center', color=colors[i%40], fontsize=4)
        plt.xlabel("time (s)")
        plt.ylabel("Client thread index")
        plt.tight_layout()
        plt.grid(True, linestyle='--', linewidth=0.5)
        plt.savefig(f'./results/{hd}_{our_patch}_{n}_{io}_{d}_{run}_client_on_rq.pdf')
        plt.close()

        # server vruntime
        plt.figure(figsize=(5, 5*0.618))
        for i in range(n//2):
            time, vruntime = zip(*server_thread_vruntimes[i])
            plt.plot(time, vruntime, label=f"thread {i}", color=colors[i%40])
        rq_vruntimes = [[] for _ in range(120)]
        for i in range(n//2):
            time, vruntime = zip(*server_thread_vruntimes[i])
            on_rq = server_on_rq[i]
            on_rq_vruntime = [vruntime[time.index(t)] for t in on_rq]
            for j in range(len(on_rq)):
                rq_vruntimes[on_rq[j]].append(on_rq_vruntime[j])
            plt.scatter(on_rq, on_rq_vruntime, s=5, color=colors[i%40], edgecolors='black', zorder=3) # same color for thread i
        for i in range(len(rq_vruntimes)):
            # plt.scatter([i for _ in range(len(rq_vruntimes[i]))], rq_vruntimes[i], s=5, color=colors[i%40], edgecolors='black', zorder=2) # same color for time i
            if len(rq_vruntimes[i]) > 0:
                plt.text(i, max(rq_vruntimes[i])*1.2, str(len(rq_vruntimes[i])), horizontalalignment='center', color=colors[i%40], fontsize=4)
        plt.yscale("log")
        plt.xlabel("time (s)")
        plt.ylabel("Server vruntime")
        plt.tight_layout()
        plt.savefig(f'./results/{hd}_{our_patch}_{n}_{io}_{d}_{run}_server_vruntime.pdf')
        plt.close()

        # server on_rq
        plt.figure(figsize=(5, 5*0.618))
        for i in range(len(server_on_rq)):
            thread_rq = server_on_rq[i]
            # scatter thread_rq, with x = thread_rq, y = i
            plt.scatter(thread_rq, [i for _ in range(len(thread_rq))], s=10, color=colors[i%40], edgecolors='black', zorder=5)
            if len(thread_rq) > 0:
                plt.text(0, i+0.2, str(len(thread_rq)), horizontalalignment='center', color=colors[i%40], fontsize=4)
        plt.xlabel("time (s)")
        plt.ylabel("Server thread index")
        plt.tight_layout()
        plt.grid(True, linestyle='--', linewidth=0.5)
        plt.savefig(f'./results/{hd}_{our_patch}_{n}_{io}_{d}_{run}_server_on_rq.pdf')
        plt.close() 

        # client and server co-occurrence matrix
        client_C = build_cooccurrence(client_rq_pids, n//2)
        server_C = build_cooccurrence(server_rq_pids, n//2)
        plt.figure()
        plt.imshow(client_C, origin='lower', aspect='auto', cmap='Reds')
        plt.title("Client Thread Co-occurrence (Counts)")
        plt.xlabel("Thread ID")
        plt.ylabel("Thread ID")
        plt.colorbar()
        plt.tight_layout()
        plt.savefig(f'./results/{hd}_{our_patch}_{n}_{io}_{d}_{run}_client_cooccurrence.pdf')
        plt.close()
        plt.figure()
        plt.imshow(server_C, origin='lower', aspect='auto', cmap='Reds')
        plt.title("Server Thread Co-occurrence (Counts)")
        plt.xlabel("Thread ID")
        plt.ylabel("Thread ID")
        plt.colorbar()
        plt.tight_layout()
        plt.savefig(f'./results/{hd}_{our_patch}_{n}_{io}_{d}_{run}_server_cooccurrence.pdf')
        plt.close()

        print(f"Completed {result_dir}")


if __name__ == "__main__":
    main()