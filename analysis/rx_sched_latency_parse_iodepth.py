#!/usr/bin/env python3
import os
import re
import sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

# 20 distinct colors for plotting
colors = [
    'blue', 'orange', 'green', 'red', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan',
    'magenta', 'yellow', 'teal', 'lavender', 'turquoise', 'tan', 'salmon', 'gold', 'navy', 'maroon'
]


def server_sched_parser(breakdown_log_path):
    with open(breakdown_log_path, "r") as file:
        lines = file.readlines()

    pattern = re.compile(r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -rx_sched: ([0-9]+).*")

    samples = {}
    count = {}

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 3:
                _, port, rx_sched = timestamps

                if port not in samples:
                    samples[port] = []
                    count[port] = 0

                if not count[port] < 2: # We skip first two packets to avoid zero time stamp issue.
                    samples[port].append({
                        'rx_sched': rx_sched,
                    })
                count[port] += 1  # We skip the first two packets for each port to avoid initialization effects 

    sched_latency = {}

    for port, port_samples in samples.items():
        sched_latency[port] = {'raw': [], 'avg': 0, 'mid': 0, 'p999': 0}
        for ts in port_samples:
            sched_latency[port]['raw'].append(ts['rx_sched'])
        sched_latency[port]['raw'].sort()
        sched_latency[port]['avg'] = sum(sched_latency[port]['raw']) / len(sched_latency[port]['raw'])
        sched_latency[port]['mid'] = sched_latency[port]['raw'][len(sched_latency[port]['raw']) // 2]
        sched_latency[port]['p999'] = sched_latency[port]['raw'][int(len(sched_latency[port]['raw']) * 0.999) - 1]

    return sched_latency 


def client_sched_parser(breakdown_log_path):
    with open(breakdown_log_path, "r") as file:
        lines = file.readlines()

    pattern = re.compile(r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -rx_sched: ([0-9]+).*")

    samples = {}
    count = {}

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 3:
                port, _, rx_sched = timestamps

                if port not in samples:
                    samples[port] = []
                    count[port] = 0

                if not count[port] < 2: # We skip first two packets to avoid zero time stamp issue.
                    samples[port].append({
                        'rx_sched': rx_sched,
                    })
                count[port] += 1

    sched_latency = {}
    
    for port, port_samples in samples.items():
        sched_latency[port] = {'raw': [], 'avg': 0, 'mid': 0, 'p999': 0}
        for ts in port_samples:
            sched_latency[port]['raw'].append(ts['rx_sched'])
        sched_latency[port]['raw'].sort()
        sched_latency[port]['avg'] = sum(sched_latency[port]['raw']) / len(sched_latency[port]['raw'])
        sched_latency[port]['mid'] = sched_latency[port]['raw'][len(sched_latency[port]['raw']) // 2]
        sched_latency[port]['p999'] = sched_latency[port]['raw'][int(len(sched_latency[port]['raw']) * 0.999) - 1]
    return sched_latency 


def process_experiment(result_dir, experiment, n_thread, save_id):
    print(f"[PID {os.getpid()}] Processing experiment: {experiment} with {n_thread} threads")

    experiment_dir = os.path.join(result_dir, experiment)
    client_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}.log")
    server_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}-server.log")

    client_sched = client_sched_parser(client_breakdown_path)
    server_sched = server_sched_parser(server_breakdown_path)
    client_save_path = os.path.join(experiment_dir, f"sched_client_iodepth_{n_thread}.txt")
    server_save_path = os.path.join(experiment_dir, f"sched_server_iodepth_{n_thread}.txt")

    with open(client_save_path, "w") as cf:
        cf.write("Port,Avg,Mid,P99.9\n")
        for port in sorted(client_sched.keys()):
            cf.write(
                f"{port},{client_sched[port]['avg']},"
                f"{client_sched[port]['mid']},{client_sched[port]['p999']}\n"
            )

    with open(server_save_path, "w") as sf:
        sf.write("Port,Avg,Mid,P99.9\n")
        for port in sorted(server_sched.keys()):
            sf.write(
                f"{port},{server_sched[port]['avg']},"
                f"{server_sched[port]['mid']},{server_sched[port]['p999']}\n"
            )

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
    save_id = [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
    ]

    tasks = list(zip(experiments, n_threads, save_id))

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