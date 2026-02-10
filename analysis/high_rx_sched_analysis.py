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

    pattern = re.compile(r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -rx_sched: ([0-9]+) timestamp: ([0-9]+).*")

    high_lat_samples = {}
    count = {}

    first_ts = -1

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            sample = list(map(int, m.groups()))
            if len(sample) == 4:
                _, port, rx_sched, ts_ns = sample

                if first_ts == -1:
                    first_ts = ts_ns

                if port not in high_lat_samples:
                    high_lat_samples[port] = []
                    count[port] = 0
                    
                if rx_sched >= rx_sched_threshold:
                    high_lat_samples[port].append((ts_ns - first_ts, rx_sched))
                count[port] += 1

    return high_lat_samples


def client_sched_parser(breakdown_log_path):
    with open(breakdown_log_path, "r") as file:
        lines = file.readlines()

    pattern = re.compile(r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -rx_sched: ([0-9]+) timestamp: ([0-9]+).*")

    high_lat_samples = {}
    count = {}
    first_ts = -1

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            sample = list(map(int, m.groups()))
            if len(sample) == 4:
                port, _, rx_sched, ts_ns = sample

                if first_ts == -1:
                    first_ts = ts_ns

                if port not in high_lat_samples:
                    high_lat_samples[port] = []
                    count[port] = 0

                if rx_sched >= rx_sched_threshold:
                    high_lat_samples[port].append((ts_ns - first_ts, rx_sched))

                count[port] += 1

    return high_lat_samples


def process_experiment(result_dir, experiment, n_thread, save_id):
    print(f"[PID {os.getpid()}] Processing experiment: {experiment} with {n_thread} threads")

    experiment_dir = os.path.join(result_dir, experiment)
    client_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}.log")
    server_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}-server.log")

    client_sched = client_sched_parser(client_breakdown_path)
    server_sched = server_sched_parser(server_breakdown_path)

    for thread_id in range(n_thread):
        port = 10000 + thread_id
        client_save_path = os.path.join(experiment_dir, f"netperf-{thread_id}_high_client_rx_sched.log")
        server_save_path = os.path.join(experiment_dir, f"netperf-{thread_id}_high_server_rx_sched.log")

        with open(client_save_path, "a") as client_file:
            if port in client_sched:
                for ts, rx_sched in client_sched[port]:
                    client_file.write(f"{ts} {rx_sched}\n")
        with open(server_save_path, "a") as server_file:
            if port in server_sched:
                for ts, rx_sched in server_sched[port]:
                    server_file.write(f"{ts} {rx_sched}\n")

    return experiment  # just for logging in the parent


if __name__ == "__main__":
    result_dir = "/data0/projects/latency/"
    experiments = [
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_5",
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_6",
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_7",
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_8",
    ]
    n_threads = [
        48, 48, 48, 48, 48, 48, 48, 48, 48, 48,
    ]
    save_id = [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
    ]

    rx_sched_threshold = 800000  # 800us

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