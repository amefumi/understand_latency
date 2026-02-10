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


hd="p2_nirq"
our_patch="1"
c_state=1
# num_apps = [64 ]#44, 48, 52, 56, 60, 64, 68, 72, 76, 80]
# 8 is lost
# num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64,  68, 72, 76, 80, 84, 88, 92, 96]

num_apps = [1, 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64,  68, 72, 76, 80, 84, 88, 92, 96, ]#100, 112, 128]
num_apps_short = [1, 2, 4, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64,  68, 72, 76, 80, 84, 88, 92, 96, ]
flowsize = [64]
iodepth = [1]
dim = [0, 1]
pin = [1]
permute = [2]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 1, 2, 3, 4]

cpu_list = [32, 96]


def analyze_cpu_usage(cpu_log_path: str, cpu_list: List[int]) -> float:
    idle_by_cpu = {}
    with open(cpu_log_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if not line.lstrip().startswith("Average:"):
                continue
            tokens = line.strip().split()
            if len(tokens) < 3:
                continue
            cpu_token = tokens[1]
            if cpu_token.lower() == "all":
                continue
            try:
                cpu_id = int(cpu_token)
            except ValueError:
                continue
            value_tokens = tokens[2:]
            idle_percent = None
            for tok in reversed(value_tokens):
                try:
                    idle_percent = float(tok)
                    break
                except ValueError:
                    continue
            if idle_percent is None:
                continue
            idle_by_cpu[cpu_id] = idle_percent
    missing = [c for c in cpu_list if c not in idle_by_cpu]
    if missing:
        raise ValueError(f"Missing CPU data for CPUs: {missing}")
    utilizations = [(100.0 - idle_by_cpu[c]) for c in cpu_list]
    avg_util = sum(utilizations) / len(utilizations)

    return avg_util



def analyze_interrupts(before_path: str, after_path: str, dev_prefix: str) -> int:
    def _parse_snapshot(path: str, dev_prefix: str):
        result = []
        with open(path, 'r') as file:
            lines = file.readlines()
            for line in lines:
                if dev_prefix in line:
                    elements = line.split()
                    total_sum = 0
                    # Loop through each element except the first one (exclude the first column)
                    for element in elements[1:]:
                        # Try to convert the element to an integer
                        try:
                            number = int(element)
                            # If successful, add it to the total sum
                            total_sum += number
                        except ValueError:
                            # If an element is not a number, break the loop (assuming non-numbers only come at the end)
                            break
                    result.append(total_sum)
        return result

    result_before = _parse_snapshot(before_path, dev_prefix)
    result_after = _parse_snapshot(after_path, dev_prefix)
    difference = [(a - b) if a >= b else 2**32 + a - b for a, b in zip(result_after, result_before)]

    return sum(difference)


def main():
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores)
    
    combination_results = []
    combination_results_dim = []
    combination_results_dimoff = []
    # A single result = tuple(cpu_client, cpu_server, interrupts_client, interrupts_server, num_apps)

    # Get performance for each experiment
    for n, f, i, d, p, perm, h, s, core in combinations:
        comb_apps = n * core

        cpu_client = 0
        cpu_server = 0
        interrupts_client = 0
        interrupts_server = 0

        check_dir = f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_0"
        if not os.path.exists(check_dir):
            print(f"Skipping missing dir {check_dir}")
            continue

        for run in runs:
            result_dir = f"../results/{hd}_{our_patch}_{c_state}/{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}"

            
            cpu_client_log_path = os.path.join(result_dir, f"cpu-{n}.log")
            cpu_server_log_path = os.path.join(result_dir, f"cpu-server-{n}.log")
            cpu_client += analyze_cpu_usage(cpu_client_log_path, cpu_list)
            cpu_server += analyze_cpu_usage(cpu_server_log_path, cpu_list)


            interrupt_before_client_path = os.path.join(result_dir, "interrupt_before")
            interrupt_after_client_path = os.path.join(result_dir, "interrupt_after")
            interrupt_before_server_path = os.path.join(result_dir, "interrupt_before_server")
            interrupt_after_server_path = os.path.join(result_dir, "interrupt_after_server")
            interrupts_client += analyze_interrupts(interrupt_before_client_path, interrupt_after_client_path, "mlx5")
            interrupts_server += analyze_interrupts(interrupt_before_server_path, interrupt_after_server_path, "mlx5")

        # Average over runs
        cpu_client /= len(runs)
        cpu_server /= len(runs)
        interrupts_client /= len(runs)
        interrupts_server /= len(runs)
        
        combination_results.append((cpu_client, cpu_server, interrupts_client, interrupts_server, n*core))
        if d == 1:
            combination_results_dim.append((cpu_client, cpu_server, interrupts_client, interrupts_server, n*core))
        else:
            combination_results_dimoff.append((cpu_client, cpu_server, interrupts_client, interrupts_server, n*core))

    # Sort combination_results, combination_results_dim, and combination_results_dimoff by num_apps (the last element in the tuple)
    combination_results.sort(key=lambda x: x[4])
    combination_results_dim.sort(key=lambda x: x[4])
    combination_results_dimoff.sort(key=lambda x: x[4])

    # Plot throughput vs latency (p999)
    cpu_clients_dim = [res[0] for res in combination_results_dim]
    cpu_servers_dim = [res[1] for res in combination_results_dim]
    interrupts_clients_dim = [res[2] for res in combination_results_dim]
    interrupts_servers_dim = [res[3] for res in combination_results_dim] 
    cpu_clients_dimoff = [res[0] for res in combination_results_dimoff]
    cpu_servers_dimoff = [res[1] for res in combination_results_dimoff]
    interrupts_clients_dimoff = [res[2] for res in combination_results_dimoff]
    interrupts_servers_dimoff = [res[3] for res in combination_results_dimoff]



    plt.figure(figsize=(5, 5*0.618))
    plt.plot(num_apps, cpu_clients_dim, marker='o', linestyle='-', linewidth=1, zorder=3, label='Client CPU%, w/ DIM')
    plt.plot(num_apps, cpu_servers_dim, marker='o', linestyle='-', linewidth=1, zorder=3, label='Server CPU%, w/ DIM')
    plt.plot(num_apps, cpu_clients_dimoff, marker='o', linestyle='-', linewidth=1, zorder=3, label='Client CPU%, w/o DIM')
    plt.plot(num_apps, cpu_servers_dimoff, marker='o', linestyle='-', linewidth=1, zorder=3, label='Server CPU%, w/o DIM')
    # plt.xticks(x, num_apps)
    plt.xlabel('Number of Applications')
    plt.ylabel('CPU Utilization (%)')
    plt.grid(True, linestyle='--', alpha=0.2)
    plt.ylim(0, 100)
    plt.xlim(0, 100)
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(5, 5*0.618))
    plt.plot(num_apps, interrupts_clients_dim, marker='o', linestyle='-', linewidth=1, zorder=3, label='Client Interrupts, w/ DIM')
    plt.plot(num_apps, interrupts_servers_dim, marker='o', linestyle='-', linewidth=1, zorder=3, label='Server Interrupts, w/ DIM')
    plt.plot(num_apps, interrupts_clients_dimoff, marker='o', linestyle='-', linewidth=1, zorder=3, label='Client Interrupts, w/o DIM')
    plt.plot(num_apps, interrupts_servers_dimoff, marker='o', linestyle='-', linewidth=1, zorder=3, label='Server Interrupts, w/o DIM')
    # plt.xticks(x, num_apps)
    plt.xlabel('Number of Applications')
    plt.ylabel('Total Interrupts on CPUs')
    plt.grid(True, linestyle='--', alpha=0.2)
    # plt.ylim(0, 1.2e7)
    plt.xlim(0, 100)
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.show()
    # plt.savefig(f'./results/{hd}_{our_patch}_cpu.pdf', dpi=300)

    # # 3) 轴标签与样式
    # plt.xlabel('Throughput (mIOPS)')
    # plt.ylabel('P99.9 Latency ($\mu$s)')
    # plt.grid(True, linestyle='--', alpha=0.2)
    # plt.ylim(0, 4000)
    # plt.xlim(0, 0.4)
    # plt.tight_layout()
    # plt.show()
    # plt.savefig(f'./results/{hd}_{our_patch}.pdf', dpi=300)

if __name__ == "__main__":
    main()