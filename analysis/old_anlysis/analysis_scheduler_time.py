#!/usr/bin/env python3
import os
import re
import sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.font_manager as fm

# 20 distinct colors for plotting
colors = [
    'blue', 'orange', 'green', 'red', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan',
    'magenta', 'yellow', 'teal', 'lavender', 'turquoise', 'tan', 'salmon', 'gold', 'navy', 'maroon'
]

fm.fontManager.addfont("/home/ame/GillSans.ttc")

# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.family": "Gill Sans",
    "font.size": 14,

    # sizes
    "axes.titlesize": 14,
    "axes.labelsize": 14,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,

    # lines and markers
    "lines.linewidth": 2.5,
    "lines.markersize": 4,
    
    # thick frame and ticks
    "axes.linewidth": 2,
    "xtick.major.width": 1,
    "xtick.major.size": 3,
    "ytick.major.width": 1,
    "ytick.major.size": 3,
    "xtick.minor.width": 2,
    "xtick.minor.size": 2,
    "ytick.minor.width": 2,
    "ytick.minor.size": 2,
    "xtick.direction": "in",
    "ytick.direction": "in",
    
    # grid
    "grid.linestyle": ":",
    "grid.linewidth": 2,
    "grid.color": "black",
    "grid.alpha": 1,
    "axes.axisbelow": True,

    # legend
    "legend.fontsize": 12,
})
def client_sched_parser(breakdown_log_path):
    with open(breakdown_log_path, "r") as file:
        lines = file.readlines()

    pattern = re.compile(r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) " \
    r"napi: ([0-9]+) gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) wakeup: ([0-9]+) " \
    r"data copy: ([0-9]+) return: ([0-9]+) -- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) tcp: ([0-9]+) ip: ([0-9]+) " \
    r"queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+) -- sched -- t1: ([0-9]+) t2: ([0-9]+) t3: ([0-9]+) t4: ([0-9]+) t5: ([0-9]+) t6: ([0-9]+) t7: ([0-9]+) p: ([0-9]+) f: ([0-9]+)" \
    r".*")
    
    samples = {}
    count = {}

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 32:
                port, _, rx_hw, rx_alloc, rx_irq, rx_napi, rx_gro, rx_ip, rx_tcp, rx_read, rx_sleep, rx_ready, rx_wake_up, rx_data_copy, rx_return, tx_alloc, tx_write, tx_data_copy, tx_tcp, tx_ip, tx_queue, tx_xmit, tx_finish, t1, t2, t3, t4, t5, t6, t7, p, f = timestamps

                if port not in samples:
                    samples[port] = []
                    count[port] = 0

                if not count[port] < 2: # We skip first two packets to avoid zero time stamp issue.
                    samples[port].append({
                        'rq_clock_start': t1,
                        'rq_clock_end': t2,
                        'rq_clock_task_start': t3,
                        'rq_clock_task_end': t4,
                        'enter': t5,
                        'middle': t6,
                        'exit': t7,
                        'tophalf': t6 - t5,
                        'bottomhalf': t7 - t6,
                        'total': t7 - t5 if (t1 == t2 and t3 == t4) else -1,
                        'voluntary': p,
                        'flag': f,
                    })
                count[port] += 1
    return samples

def process_experiment(result_dir, experiment, n_thread, save_id):
    print(f"[PID {os.getpid()}] Processing experiment: {experiment} with {n_thread} threads")

    experiment_dir = os.path.join(result_dir, experiment)
    client_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}.log")
    client_samples = client_sched_parser(client_breakdown_path)

    # for each port, draw each sample's tophalf, bottomhalf, and total times with x asix the index
    plt.figure(figsize=(10, 10*0.618))
    for port, samples in client_samples.items():
        total_len = len(samples)
        sample_interval = total_len // 1000
        total = [sample['total'] for sample in samples][::sample_interval]
        # sample these three list to 1000 point
        plt.plot(range(0, total_len, sample_interval), total, label=f"Port {port} Total", color=colors[port % len(colors)])
    plt.yscale("log")
    plt.tight_layout()
    plt.savefig(f"scheduler_sample_{save_id}.pdf")

    plt.figure(figsize=(10, 10*0.618))
    for port, samples in client_samples.items():
        total_len = len(samples)
        sample_interval = total_len // 1000
        top_half = [sample['tophalf'] for sample in samples][::sample_interval]
        # sample these three list to 1000 point
        plt.plot(range(0, total_len, sample_interval), top_half, label=f"Port {port} Top half", color=colors[port % len(colors)])
    plt.yscale("log")
    plt.tight_layout()
    plt.savefig(f"scheduler_sample_{save_id}_noirq.pdf")

    top_half = [sample['tophalf'] for sample in samples]
    top_half_average = np.mean(top_half)

    # non -1 total times
    total_times = [sample['total'] for sample in samples if sample['total'] != -1]
    total_average = np.mean(total_times)

    print(f"[PID {os.getpid()}] Experiment: {experiment}, Thread: {n_thread}, Top half average: {top_half_average} ns, Total average: {total_average} ns")

    return experiment  # just for logging in the parent


def process_experiment_differ(result_dir, experiment, n_thread, save_id):
    print(f"[PID {os.getpid()}] Processing experiment: {experiment} with {n_thread} threads")

    experiment_dir = os.path.join(result_dir, experiment)
    client_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}.log")
    client_samples = client_sched_parser(client_breakdown_path)

    # for all samples, draw CDF of top half when voluntary is 1 and when voluntary is 0
    voluntary_top_half = []
    involuntary_top_half = []
    count = 0
    count1 = 0
    for port, samples in client_samples.items():
        for sample in samples:
            if sample['voluntary'] == 1:
                voluntary_top_half.append(sample['tophalf'])
            else:
                involuntary_top_half.append(sample['tophalf'])

    voluntary_top_half = np.array(voluntary_top_half)
    involuntary_top_half = np.array(involuntary_top_half)
    voluntary_top_half = np.sort(voluntary_top_half)
    involuntary_top_half = np.sort(involuntary_top_half)
    voluntary_cdf = np.arange(len(voluntary_top_half)) / float(len(voluntary_top_half))
    involuntary_cdf = np.arange(len(involuntary_top_half)) / float(len(involuntary_top_half))
    plt.figure(figsize=(6, 6*0.618))
    plt.plot(voluntary_top_half, voluntary_cdf, label="Voluntary Top Half", color='blue')
    plt.plot(involuntary_top_half, involuntary_cdf, label="Involuntary Top Half", color='red')

    # write the average top half times and P99.9 top half times for both voluntary and involuntary in the figure
    voluntary_top_half_average = np.mean(voluntary_top_half)
    involuntary_top_half_average = np.mean(involuntary_top_half)
    voluntary_top_half_p99_9 = voluntary_top_half[int(len(voluntary_top_half) * 0.999)]
    involuntary_top_half_p99_9 = involuntary_top_half[int(len(involuntary_top_half) * 0.999)]
    plt.axvline(voluntary_top_half_average, color='blue', linestyle='--', label=f"Voluntary Avg: {voluntary_top_half_average:.2f} ns")
    plt.axvline(involuntary_top_half_average, color='red', linestyle='--', label=f"Involuntary Avg: {involuntary_top_half_average:.2f} ns")
    plt.axvline(voluntary_top_half_p99_9, color='blue', linestyle=':', label=f"Voluntary P99.9: {voluntary_top_half_p99_9:.2f} ns")
    plt.axvline(involuntary_top_half_p99_9, color='red', linestyle=':', label=f"Involuntary P99.9: {involuntary_top_half_p99_9:.2f} ns")

    plt.xscale("log")
    plt.xlabel("Scheduler's top half (before `context_swtich`) latency (ns)")
    plt.ylabel("CDF")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"scheduler_cdf_{save_id}.pdf")
    plt.close()

    # do the same for bottom half
    voluntary_bottom_half = []
    involuntary_bottom_half = []
    for port, samples in client_samples.items():
        for sample in samples:
            if sample['voluntary'] == 1:
                voluntary_bottom_half.append(sample['bottomhalf'])
            else:
                involuntary_bottom_half.append(sample['bottomhalf'])
    voluntary_bottom_half = np.array(voluntary_bottom_half)
    involuntary_bottom_half = np.array(involuntary_bottom_half)
    voluntary_bottom_half = np.sort(voluntary_bottom_half)
    involuntary_bottom_half = np.sort(involuntary_bottom_half)
    voluntary_cdf = np.arange(len(voluntary_bottom_half)) / float(len(voluntary_bottom_half))
    involuntary_cdf = np.arange(len(involuntary_bottom_half)) / float(len(involuntary_bottom_half))
    plt.figure(figsize=(6, 6*0.618))
    plt.plot(voluntary_bottom_half, voluntary_cdf, label="Voluntary Bottom Half", color='blue')
    plt.plot(involuntary_bottom_half, involuntary_cdf, label="Involuntary Bottom Half", color='red')
    plt.xscale("log")
    plt.xlabel("Scheduler's bottom half (after `context_swtich`) latency (ns)")
    plt.ylabel("CDF")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"scheduler_cdf_{save_id}_bottom.pdf")
    plt.close()

    return experiment  # just for logging in the parent



if __name__ == "__main__":
    result_dir = "/data0/projects/latency/"
    experiments = [
        "airq_scheduler_lat_3_1/52_64_1_1_1_1_0_0_1_0",
        "airq_scheduler_lat_3_1/52_64_1_1_1_1_0_0_1_1",
        "airq_scheduler_lat_3_1/52_64_1_1_1_1_0_0_1_2",
        "airq_scheduler_lat_3_1/52_64_1_1_1_1_0_0_1_3",
        "airq_scheduler_lat_3_1/52_64_1_1_1_1_0_0_1_4",
    ]
    n_threads = [
        52, 52, 52, 52, 52
    ]
    save_id = [0, 1, 2, 3, 4]
    tasks = list(zip(experiments, n_threads, save_id))

    # Use as many workers as you like; os.cpu_count() is a good default
    max_workers = min(len(tasks), os.cpu_count() or 1)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_experiment_differ, result_dir, exp, th, sid)
            for (exp, th, sid) in tasks
        ]

        for fut in as_completed(futures):
            # This will raise if any worker crashed, which is helpful for debugging
            exp_done = fut.result()
            print(f"[MAIN] Finished experiment: {exp_done}")