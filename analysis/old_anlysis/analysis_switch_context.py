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
        self.total_packets = 0
        self.server_vruntime = []
        self.client_vruntime = []
        self.abs_client_vruntime = 0
        self.abs_server_vruntime = 0
        self.server_context_switches = 0
        self.client_context_switches = 0
        self.client_forced_switches = 0
        self.server_forced_switches = 0

    def __str__(self):
        return (f"Port: {self.port}, Client: {self.client_pid}, Client Core: {self.client_core}, "
                f"Server: {self.server_pid}, Server Core: {self.server_core}, "
                f"Throughput: {self.thpt}, Latency: {self.latency}, "
                f"S#VRT: {len(self.server_vruntime)}, "
                f"C#VRT: {len(self.client_vruntime)}, "
                f"C#ABS: {self.abs_client_vruntime}, S#ABS: {self.abs_server_vruntime}, "
                f"C#Switch: {self.client_context_switches}, S#Switch: {self.server_context_switches}, "
                f"Total Packets: {self.total_packets}, "
                f"C#Forced: {self.client_forced_switches}, S#Forced: {self.server_forced_switches}")

    def __repr__(self):
        return f"<ThreadData port={self.port} client_pid={self.client_pid} thpt={self.thpt} latency={self.latency}>"


def read_histogram(file_path):
    assert os.path.exists(file_path), f"File {file_path} does not exist"
    with open(file_path, 'rb') as f:
        data = np.fromfile(f, dtype=np.uint64, count=100000)
    return data


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

    # Parse client total packets
    for i in range(total_threads):
        thread_netperf_path = os.path.join(experiment_dir, f"netperf-{i}_thpt.log")
        with open(thread_netperf_path, "r") as thread_log:
            pid = int(thread_log.readlines()[0].split()[0])
        thread_bin_path = os.path.join(experiment_dir, f"netperf-{i}_hist.bin")
        thread_hist = read_histogram(thread_bin_path)
        total_packets = np.sum(thread_hist, dtype=np.int64)
        for thread in threads_info:
            if thread.client_pid == pid:
                thread.total_packets = total_packets
    
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
        thread.abs_client_vruntime = max(thread.client_vruntime) - min([v for v in thread.client_vruntime if v > 0])
        thread.abs_server_vruntime = max(thread.server_vruntime) - min([v for v in thread.server_vruntime if v > 0])

    return threads_info


def parse_context_switches(threads_info, server_perf_path, client_perf_path):
    pattern = re.compile(r".*?-(\d+)\s+([\d,]+)\s+context-switches")

    # Parse client context switches
    with open(client_perf_path, "r") as client_log:
        for line in client_log.readlines():
            match = pattern.match(line)
            if match:
                pid = int(match.group(1))
                cswitches = int(match.group(2).replace(",", ""))
                for thread in threads_info:
                    if thread.client_pid == pid:
                        thread.client_context_switches = cswitches
                        thread.client_forced_switches = cswitches - thread.total_packets if cswitches >= thread.total_packets else -(thread.total_packets-cswitches)
    
    # Parse server context switches
    with open(server_perf_path, "r") as server_log:
        for line in server_log.readlines():
            match = pattern.match(line)
            if match:
                pid = int(match.group(1))
                sswitches = int(match.group(2).replace(",", ""))
                for thread in threads_info:
                    if thread.server_pid == pid:
                        thread.server_context_switches = sswitches
                        thread.server_forced_switches = sswitches - thread.total_packets if sswitches >= thread.total_packets else -(thread.total_packets-sswitches)

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

        server_perf_path = os.path.join(experiment_dir, f"perf_server.log")
        client_perf_path = os.path.join(experiment_dir, f"perf_client.log")
        threads_info = parse_context_switches(threads_info, server_perf_path, client_perf_path)

        for thread in threads_info:
            print(thread)

        x = [thread.server_forced_switches for thread in threads_info if thread.client_core == 96]
        y = [thread.abs_server_vruntime for thread in threads_info if thread.client_core == 96]
        plt.figure(figsize=(6, 6*0.618))
        plt.scatter(x, y, color='#ff0000', label="Client Threads", marker='+', s=100)
        plt.xlabel("#Context swithces - #Packets sent")
        plt.ylabel("Absolute virtual runtime")
        plt.grid(True)
        plt.tight_layout()
        save_path = os.path.join(result_dir, f"context_switch_forced_vs_abs_vruntime_server.pdf")
        plt.savefig(save_path)
        plt.close()

        x = [thread.server_context_switches for thread in threads_info if thread.client_core == 96]
        y = [thread.abs_server_vruntime for thread in threads_info if thread.client_core == 96]
        plt.figure(figsize=(6, 6*0.618))
        plt.scatter(x, y, color='#0000ff', label="Server Threads", marker='o', s=100)
        plt.xlabel("Total #Context swithces")
        plt.ylabel("Absolute virtual runtime")
        plt.grid(True)
        plt.tight_layout()
        save_path = os.path.join(result_dir, f"context_switch_total_vs_abs_vruntime_server.pdf")
        plt.savefig(save_path)
        plt.close()


if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"
    experiments = [
        "airq_contextswitch_1_1/52_64_1_1_1_1_0_0_1_0"
    ]

    save_names = [
    ]
    n_threads = [
        52
    ]
    single_core = [
        False
    ]

    draw_single()

    # draw_combined()