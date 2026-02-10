import os
import re
import itertools
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import matplotlib.patheffects as path_effects
from matplotlib.ticker import MultipleLocator, LogLocator, LogFormatter

fm.fontManager.addfont("/home/ame/GillSans.ttc")

# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.family": "Gill Sans",
    "font.size": 12,

    # sizes
    "axes.titlesize": 12,
    "axes.labelsize": 12,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,

    # lines and markers
    "lines.linewidth": 2,
    "lines.markersize": 4,
    
    # thick frame and ticks
    "axes.linewidth": 2,
    "xtick.major.width": 2,
    "xtick.major.size": 6,
    "ytick.major.width": 2,
    "ytick.major.size": 6,
    "xtick.minor.width": 2,
    "xtick.minor.size": 3,
    "ytick.minor.width": 2,
    "ytick.minor.size": 3,
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

# 40 relatively dark colors
colors = list(mcolors.TABLEAU_COLORS.values()) + [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
    "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#393b79", "#637939",
    "#8c6d31", "#843c39", "#7b4173", "#3182bd", "#31a354", "#756bb1",
    "#636363", "#e6550d", "#fd8d3c", "#fdae6b", "#e7ba52", "#9e9ac8",
    "#cedb9c", "#8c6d31", "#bd9e39", "#ad494a", "#a55194", "#6b6ecf",
    "#b5cf6b", "#9c9ede", "#cedb9c", "#e7cb94", "#843c39", "#ad494a"]

class ThreadData:
    def __init__(self, port=0, client_pid=0, client_core=0,
                 client_softirq_packets=0, server_pid=0, server_core=0,
                 thpt=0, latency=0):
        self.port = port
        self.client_pid = client_pid
        self.client_core = client_core
        self.server_pid = server_pid
        self.server_core = server_core
        self.thpt = thpt
        self.latency = latency
        self.server_vruntime = []
        self.server_vruntime_abs = 0
        self.server_softirq_count = 0
        self.server_softirq_time = 0
        self.client_vruntime = []
        self.client_vruntime_abs = 0
        self.client_softirq_count = 0
        self.client_softirq_time = 0

    def __str__(self):
        return (f"Port: {self.port}, Client: {self.client_pid}, Client Core: {self.client_core}, "
                f"Server: {self.server_pid}, Server Core: {self.server_core}, "
                f"Throughput: {self.thpt}, Latency: {self.latency}, "
                f"S#VRT: {len(self.server_vruntime)}, "
                f"C#VRT: {len(self.client_vruntime)}, "
                f"C#ABS: {self.client_vruntime_abs}, S#ABS: {self.server_vruntime_abs}, "
                f"C#SoftIRQ: {self.client_softirq_count}, S#SoftIRQ: {self.server_softirq_count}, "
                f"C#SoftIRQ Time: {self.client_softirq_time}, S#SoftIRQ Time: {self.server_softirq_time}")

    def __repr__(self):
        return f"<ThreadData port={self.port} client_pid={self.client_pid} thpt={self.thpt} latency={self.latency}>"


def parse_all_thread_info(experiment_dir, total_threads, sc):
    threads_info = []
    for i in range(total_threads):
        throughput_log_path = os.path.join(experiment_dir, f"netperf-{i}_thpt.log")
        with open(throughput_log_path, "r") as throughput_log:
            lines = throughput_log.readlines()
            items = lines[0].split()
            client_pid, port, latency, throughput = int(items[0]), int(items[1]), float(items[4]), float(items[5])
        thread = ThreadData()
        thread.client_pid = client_pid
        thread.port = port
        thread.latency = float(latency)
        thread.thpt = float(throughput)
        threads_info.append(thread)

    
    server_log_path = os.path.join(experiment_dir, f"server.log")
    with open(server_log_path, "r") as server_log:
        lines = server_log.readlines()
        for line in lines:
            items = line.split()
            if len(items) < 5:
                continue
            core, pid, port = int(items[2]), int(items[4]), int(items[7])
            for thread in threads_info:
                if thread.port == port:
                    thread.server_pid = pid
                    thread.server_core = core
    
    client_log_path = os.path.join(experiment_dir, f"client.log")
    with open(client_log_path, "r") as client_log:
        lines = client_log.readlines()
        for line in lines:
            items = line.split()
            if len(items) < 5:
                continue
            core, pid, port = int(items[2]), int(items[4]), int(items[7])
            for thread in threads_info:
                if thread.port == port:
                    thread.client_core = core

    # Sort thread by port number
    threads_info.sort(key=lambda x: x.port)

    if not sc:
        # assert for server core, half threads on core 96, half threads on core 32
        # n_threads_on_96 = sum(1 for thread in threads_info if thread.server_core == 96)
        # n_threads_on_32 = sum(1 for thread in threads_info if thread.server_core == 32)
        n_threads_on_96 = sum(1 for thread in threads_info if thread.client_core == 96)
        n_threads_on_32 = sum(1 for thread in threads_info if thread.client_core == 32)
        assert n_threads_on_96 == total_threads // 2 and n_threads_on_32 == total_threads // 2, \
            f"Server core assignment error: {n_threads_on_96} on 96, {n_threads_on_32} on 32 for total {total_threads} threads."

    return threads_info


def parse_vruntime(threads_info, server_vruntime_path, client_vruntime_path):
    # Parse server vruntime
    with open(server_vruntime_path, "r") as server_log:
        lines = server_log.readlines()
        line_index = 0
        in_record = False
        while line_index < len(lines):
            if not in_record:
                if "iterate_cfs_rq:" in lines[line_index]:
                    in_record = True
                line_index += 1
                continue

            line = lines[line_index]
            items = line.split()
            if "All-thread IDs:" in line and len(line.split()) > 7:
                thread_index = items.index("IDs:") + 1
                thread_pids = [int(items[i]) for i in range(thread_index, len(items))]
                vruntime_items = lines[line_index + 1].split()
                vruntime_index = vruntime_items.index("vruntime:") + 1
                thread_vruntimes = [int(vruntime_items[i]) for i in range(vruntime_index, len(vruntime_items))]
                for thread in threads_info:
                    if thread.server_pid in thread_pids:
                        index = thread_pids.index(thread.server_pid)
                        thread.server_vruntime.append(thread_vruntimes[index])
                    else:
                        thread.server_vruntime.append(0)
                line_index += 4
            else:
                line_index += 1
    
    # Parse client vruntime
    with open(client_vruntime_path, "r") as client_log:
        lines = client_log.readlines()
        line_index = 0
        in_record = False
        while line_index < len(lines):
            if not in_record:
                if "iterate_cfs_rq:" in lines[line_index]:
                    in_record = True
                line_index += 1
                continue

            line = lines[line_index]
            items = line.split()
            if "All-thread IDs:" in line and len(line.split()) > 7:
                thread_index = items.index("IDs:") + 1
                thread_pids = [int(items[i]) for i in range(thread_index, len(items))]
                vruntime_items = lines[line_index + 1].split()
                vruntime_index = vruntime_items.index("vruntime:") + 1
                thread_vruntimes = [int(vruntime_items[i]) for i in range(vruntime_index, len(vruntime_items))]
                for thread in threads_info:
                    if thread.client_pid in thread_pids:
                        index = thread_pids.index(thread.client_pid)
                        thread.client_vruntime.append(thread_vruntimes[index])
                    else:
                        thread.client_vruntime.append(0)
                line_index += 4
            else:
                line_index += 1
    
    # Calculate absolute vruntime for client
    for thread in threads_info:
        thread.client_vruntime_abs = max(thread.client_vruntime) - min([v for v in thread.client_vruntime if v > 0])
        thread.server_vruntime_abs = max(thread.server_vruntime) - min([v for v in thread.server_vruntime if v > 0])

    return threads_info


def parse_bpftrace(threads_info, server_bpftrace_path, client_bpftrace_path):
    count_pattern = re.compile(r"@softirq_cnt\[(\d+)\]:\s*(\d+)")
    time_pattern = re.compile(r"@softirq_time_ns\[(\d+)\]:\s*(\d+)")
    with open(server_bpftrace_path, "r") as server_bpftrace_log:
        lines = server_bpftrace_log.readlines()
        server_softirq_count = {}
        server_softirq_time = {}
        for line in lines:
            count_match = count_pattern.match(line)
            time_match = time_pattern.match(line)
            if count_match:
                pid = int(count_match.group(1))
                count = int(count_match.group(2))
                server_softirq_count[pid] = count
            elif time_match:
                pid = int(time_match.group(1))
                time_ns = int(time_match.group(2))
                server_softirq_time[pid] = time_ns

        for thread in threads_info:
            if thread.server_pid in server_softirq_count:
                thread.server_softirq_count = server_softirq_count[thread.server_pid]
            if thread.server_pid in server_softirq_time:
                thread.server_softirq_time = server_softirq_time[thread.server_pid]

    with open(client_bpftrace_path, "r") as client_bpftrace_log:
        lines = client_bpftrace_log.readlines()
        client_softirq_count = {}
        client_softirq_time = {}
        for line in lines:
            count_match = count_pattern.match(line)
            time_match = time_pattern.match(line)
            if count_match:
                pid = int(count_match.group(1))
                count = int(count_match.group(2))
                client_softirq_count[pid] = count
            elif time_match:
                pid = int(time_match.group(1))
                time_ns = int(time_match.group(2))
                client_softirq_time[pid] = time_ns

        for thread in threads_info:
            if thread.client_pid in client_softirq_count:
                thread.client_softirq_count = client_softirq_count[thread.client_pid]
            if thread.client_pid in client_softirq_time:
                thread.client_softirq_time = client_softirq_time[thread.client_pid]
    return threads_info

def draw_single():

    for index, experiment in enumerate(experiments):
        print(f"Processing experiment: {experiment}")
        experiment_dir = os.path.join(result_dir, experiment)
        total_threads = n_threads[index]

        threads_info = parse_all_thread_info(experiment_dir, total_threads, single_core[index])

        server_vruntime_path = os.path.join(experiment_dir, f"iter_thread_server.log")
        client_vruntime_path = os.path.join(experiment_dir, f"iter_thread_client.log")
        threads_info = parse_vruntime(threads_info, server_vruntime_path, client_vruntime_path)

        server_bpftrace_path = os.path.join(experiment_dir, f"bpf_server.log")
        client_bpftrace_path = os.path.join(experiment_dir, f"bpf_client.log")
        threads_info = parse_bpftrace(threads_info, server_bpftrace_path, client_bpftrace_path)

        for thread in threads_info:
            print(thread)

        # Figure 1: SoftIRQ count vs Absolute vruntime (draw client and server in the same plot with different markers)
        plt.figure(figsize=(6, 6*0.618))
        client_softirq_counts = [thread.client_softirq_count for thread in threads_info if thread.client_core == 96]
        client_vruntime_abs = [thread.client_vruntime_abs for thread in threads_info if thread.client_core == 96]
        server_softirq_counts = [thread.server_softirq_count for thread in threads_info if thread.server_core == 96]
        server_vruntime_abs = [thread.server_vruntime_abs for thread in threads_info if thread.server_core == 96]
        plt.scatter(client_softirq_counts, client_vruntime_abs, marker='o', color=colors[0], label='Client', s=100)
        for i in range(len(client_softirq_counts)):
            plt.text(client_softirq_counts[i], client_vruntime_abs[i], str(i), fontsize=10,
                     verticalalignment='bottom', horizontalalignment='right', color=colors[i])
        plt.scatter(server_softirq_counts, server_vruntime_abs, marker='s', color=colors[1], label='Server', s=100)
        for i in range(len(server_softirq_counts)):
            plt.text(server_softirq_counts[i], server_vruntime_abs[i], str(i), fontsize=10,
                     verticalalignment='bottom', horizontalalignment='right', color=colors[i])
        plt.xlabel('SoftIRQ Count')
        plt.ylabel('Absolute virtual runtime (ns)')
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f'bpf_{save_names[index]}_softirq_count_vs_abs_vruntime.pdf'))

        # Figure 2: SoftIRQ time vs Absolute vruntime (draw client and server in the same plot with different markers)
        plt.figure(figsize=(6, 6*0.618))
        client_softirq_times = [thread.client_softirq_time / 1e6 for thread in threads_info if thread.client_core == 96]  # convert to ms
        client_vruntime_abs = [thread.client_vruntime_abs for thread in threads_info if thread.client_core == 96]
        server_softirq_times = [thread.server_softirq_time / 1e6 for thread in threads_info if thread.server_core == 96]  # convert to ms
        server_vruntime_abs = [thread.server_vruntime_abs for thread in threads_info if thread.server_core == 96]
        plt.scatter(client_softirq_times, client_vruntime_abs, marker='o', color=colors[0], label='Client', s=100)
        for i in range(len(client_softirq_times)):
            plt.text(client_softirq_times[i], client_vruntime_abs[i], str(i), fontsize=10,
                     verticalalignment='bottom', horizontalalignment='right', color=colors[i])
        plt.scatter(server_softirq_times, server_vruntime_abs, marker='s', color=colors[1], label='Server', s=100)
        for i in range(len(server_softirq_times)):
            plt.text(server_softirq_times[i], server_vruntime_abs[i], str(i), fontsize=10,
                     verticalalignment='bottom', horizontalalignment='right', color=colors[i])
        plt.xlabel('SoftIRQ Time (ms)')
        plt.ylabel('Absolute virtual runtime (ns)')
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f'bpf_{save_names[index]}_softirq_time_vs_abs_vruntime.pdf'))

if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"
    experiments = [
        "airq_bpftrace_softirq_1_1/52_64_1_1_1_1_0_0_1_1",
        "nirq_bpftrace_softirq_1_1/48_64_1_1_1_1_0_0_1_1",
    ]

    save_names = [
        "airq",
        "nirq"
    ]
    n_threads = [
        52,
        48
    ]
    single_core = [
        False,
        False
    ]

    draw_single()

    # draw_combined()