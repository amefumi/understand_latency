#!/usr/bin/env python3
import os
import re
import sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import matplotlib.pyplot as plt

# 20 distinct colors for plotting
colors = [
    'blue', 'orange', 'green', 'red', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan',
    'magenta', 'yellow', 'teal', 'lavender', 'turquoise', 'tan', 'salmon', 'gold', 'navy', 'maroon'
]


def process_experiment(result_dir, experiment, n_thread, save_id):
    print(f"[PID {os.getpid()}] Processing experiment: {experiment} with {n_thread} threads")

    experiment_dir = os.path.join(result_dir, experiment)
    client_save_path = os.path.join(experiment_dir, f"sched_client_iodepth_{n_thread}.txt")
    server_save_path = os.path.join(experiment_dir, f"sched_server_iodepth_{n_thread}.txt")

    client_mean_sched = []
    client_p999_sched = []
    server_mean_sched = []
    server_p999_sched = []

    with open(client_save_path, "r") as cf:
        client_log_lines = cf.readlines()
        for line in client_log_lines[1:]:
            parts = line.strip().split(",")
            if len(parts) != 4:
                continue
            port, avg, mid, p999 = parts
            if int(port) - 10000 >= n_thread//2: # port 96
                client_mean_sched.append(float(avg)/1e3)    
                client_p999_sched.append(float(p999)/1e3)

    with open(server_save_path, "r") as sf:
        server_log_lines = sf.readlines()
        for line in server_log_lines[1:]:
            parts = line.strip().split(",")
            if len(parts) != 4:
                continue
            port, avg, mid, p999 = parts
            if int(port) - 10000 >= n_thread//2: # port 96
                server_mean_sched.append(float(avg)/1e3)    
                server_p999_sched.append(float(p999)/1e3)

    plt.figure(figsize=(6, 6*0.618))
    x = np.arange(len(client_mean_sched))
    plt.plot(x, client_mean_sched, label='Client Mean', color='blue')
    plt.plot(x, client_p999_sched, label='Client P99.9', color='lightblue', linestyle='--')
    plt.plot(x, server_mean_sched, label='Server Mean', color='red', marker='o')
    plt.plot(x, server_p999_sched, label='Server P99.9', color='lightcoral', marker='o', linestyle='--')
    plt.xlabel('Thread Index')
    plt.ylabel('Rx Sched Latency (us)')
    plt.yscale('log')
    plt.legend()
    plt.grid()
    plt.ylim(10, 20000)
    plt.savefig(f"sched_latency_iodepth_{save_id}.pdf")

    return experiment  # just for logging in the parent


if __name__ == "__main__":
    result_dir = "/data0/projects/latency/"
    experiments = [
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_5",
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_6",
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_7",
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_8",
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_9",
    ]
    n_threads = [
        48, 48, 48, 48, 48, 48, 48, 48, 48, 48,
    ]
    save_name = [
        "sirq_vruntime_2_48_32_5_core96",
        "sirq_vruntime_2_48_32_6_core96",
        "sirq_vruntime_2_48_32_7_core96",
        "sirq_vruntime_2_48_32_8_core96",
        "sirq_vruntime_2_48_32_9_core96",
    ]

    tasks = list(zip(experiments, n_threads, save_name))

    # Use as many workers as you like; os.cpu_count() is a good default
    max_workers = min(len(tasks), os.cpu_count() or 1)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_experiment, result_dir, exp, th, sid)
            for (exp, th, sid) in tasks
        ]

        for fut in as_completed(futures):
            # This will raise if any worker crashed, which is helpful for debugging
            exp_done = fut.result()
            print(f"[MAIN] Finished experiment: {exp_done}")