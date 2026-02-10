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
                 server_softirq_packets=0, thpt=0, latency=0):
        self.port = port
        self.client_pid = client_pid
        self.client_core = client_core
        self.client_softirq_packets = client_softirq_packets
        self.server_pid = server_pid
        self.server_core = server_core
        self.server_softirq_packets = server_softirq_packets
        self.thpt = thpt
        self.latency = latency
        self.server_vruntime = []
        self.normed_server_vruntime = []
        self.server_on_rq = []
        self.client_vruntime = []
        self.normed_client_vruntime = []
        self.client_on_rq = []
        self.abs_client_vruntime = 0
        self.abs_server_vruntime = 0

    def __str__(self):
        return (f"Port: {self.port}, Client: {self.client_pid}, Client Core: {self.client_core}, "
                f"Server: {self.server_pid}, Server Core: {self.server_core}, "
                f"Throughput: {self.thpt}, Latency: {self.latency}, "
                f"S#Packets: {self.server_softirq_packets}, #S_vruntime: {len(self.server_vruntime)}, "
                f"#S_on_rq: {len(self.server_on_rq)}, "
                f"#C_vruntime: {len(self.client_vruntime)}, #C_on_rq: {len(self.client_on_rq)}")

    def __repr__(self):
        return f"<ThreadData port={self.port} client_pid={self.client_pid} thpt={self.thpt} latency={self.latency}>"


def build_cooccurrence(thread_pids_t, n_threads):
    C = np.zeros((n_threads, n_threads), dtype=int)
    for pids in thread_pids_t:
        for i, j in itertools.combinations(pids, 2):
            C[i, j] += 1
            C[j, i] += 1
    return C


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
                on_rq_items = lines[line_index + 2].split()
                on_rq_index = on_rq_items.index("IDs:") + 1
                thread_pids_on_rq = [int(on_rq_items[i]) for i in range(on_rq_index, len(on_rq_items))]
                for thread in threads_info:
                    if thread.server_pid in thread_pids:
                        index = thread_pids.index(thread.server_pid)
                        thread.server_vruntime.append(thread_vruntimes[index])
                    else:
                        thread.server_vruntime.append(0)
                    thread.server_on_rq.append(1 if thread.server_pid in thread_pids_on_rq else 0)
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
                on_rq_items = lines[line_index + 2].split()
                on_rq_index = on_rq_items.index("IDs:") + 1
                thread_pids_on_rq = [int(on_rq_items[i]) for i in range(on_rq_index, len(on_rq_items))]
                for thread in threads_info:
                    if thread.client_pid in thread_pids:
                        index = thread_pids.index(thread.client_pid)
                        thread.client_vruntime.append(thread_vruntimes[index])
                    else:
                        thread.client_vruntime.append(0)
                    thread.client_on_rq.append(1 if thread.client_pid in thread_pids_on_rq else 0)
                line_index += 4
            else:
                line_index += 1
    
    # Calculate absolute vruntime for client
    for thread in threads_info:
        thread.abs_client_vruntime = max(thread.client_vruntime) - min([v for v in thread.client_vruntime if v > 0]) + 1e-2
        thread.abs_server_vruntime = max(thread.server_vruntime) - min([v for v in thread.server_vruntime if v > 0]) + 1e-2


    # Normalize server vruntime: normed_vruntime = vruntime - min(vruntime) + 1.
    # 1. Get vruntime at time i for all threads on the same core, find the min value (non zero) among all threads at time i.
    # 2. For each thread, normed_vruntime[i] = vruntime[i] - min_vruntime + 1 if vruntime[i] > 0 else 1
    n_times = len(threads_info[0].server_vruntime)
    threads_on_32 = [thread for thread in threads_info if thread.server_core == 32]
    threads_on_96 = [thread for thread in threads_info if thread.server_core == 96]

    for time_index in range(n_times):
        vruntime_32 = [thread.server_vruntime[time_index] for thread in threads_on_32]
        # get non-zero min vruntime
        non_zero_vruntimes_32 = [v for v in vruntime_32 if v > 0]
        for i, thread in enumerate(threads_on_32):
            thread.normed_server_vruntime.append(vruntime_32[i] - min(non_zero_vruntimes_32) + 1e-2 if vruntime_32[i] > 0 else 1e-2)

        vruntime_96 = [thread.server_vruntime[time_index] for thread in threads_on_96]
        # get non-zero min vruntime
        non_zero_vruntimes_96 = [v for v in vruntime_96 if v > 0]
        for i, thread in enumerate(threads_on_96):
            thread.normed_server_vruntime.append(vruntime_96[i] - min(non_zero_vruntimes_96) + 1e-2 if vruntime_96[i] > 0 else 1e-2)

    new_threads_info = threads_on_32 + threads_on_96
    new_threads_info.sort(key=lambda x: x.port)

    # Normalize client vruntime too
    threads_on_32 = [thread for thread in threads_info if thread.client_core == 32]
    threads_on_96 = [thread for thread in threads_info if thread.client_core == 96]
    for time_index in range(n_times):
        vruntime_32 = [thread.client_vruntime[time_index] for thread in threads_on_32]
        print(vruntime_32)
        # get non-zero min vruntime
        non_zero_vruntimes_32 = [v for v in vruntime_32 if v > 0]
        for i, thread in enumerate(threads_on_32):
            thread.normed_client_vruntime.append(vruntime_32[i] - min(non_zero_vruntimes_32) + 1e-2 if vruntime_32[i] > 0 else 1e-2)

        vruntime_96 = [thread.client_vruntime[time_index] for thread in threads_on_96]
        # get non-zero min vruntime
        non_zero_vruntimes_96 = [v for v in vruntime_96 if v > 0]
        for i, thread in enumerate(threads_on_96):
            thread.normed_client_vruntime.append(vruntime_96[i] - min(non_zero_vruntimes_96) + 1e-2 if vruntime_96[i] > 0 else 1e-2)

    new_threads_info = threads_on_32 + threads_on_96
    new_threads_info.sort(key=lambda x: x.port)

    return new_threads_info


def draw_single():

    for index, experiment in enumerate(experiments):
        print(f"Processing experiment: {experiment}")
        experiment_dir = os.path.join(result_dir, experiment)
        total_threads = n_threads[index]

        threads_info = parse_all_thread_info(experiment_dir, total_threads, single_core[index])

        server_vruntime_path = os.path.join(experiment_dir, f"iter_thread_server.log")
        client_vruntime_path = os.path.join(experiment_dir, f"iter_thread_client.log")
        threads_info = parse_vruntime(threads_info, server_vruntime_path, client_vruntime_path)

        for thread in threads_info:
            print(thread)

        # For each thread whose core = 32, draw its normed_server_vruntime
        plt.figure(figsize=(5, 5*0.618))

        # selected_threads = [thread for thread in threads_info if thread.server_core == core_selection[index]]

        # for idx, thread in enumerate(selected_threads):
        #     print(f"Plotting thread: {thread.normed_server_vruntime}")
        #     plt.plot(thread.normed_server_vruntime, label=f"Port {thread.port}", color=colors[idx%len(colors)], zorder=2)
        
        selected_threads = [thread for thread in threads_info if thread.client_core==core_selection[index]]
        for idx, thread in enumerate(selected_threads):
            print(f"Plotting thread: {thread.normed_client_vruntime}")
            plt.plot(thread.normed_client_vruntime, label=f"Port {thread.port}", color=colors[idx%len(colors)], zorder=2)

        plt.xlim(left=0, right=120)
        plt.xlabel("Time (s)")
        plt.yscale("log")
        plt.ylim(bottom=1e-2, top=1e8)
        plt.yticks([1e-2, 1e0, 1e2, 1e4, 1e6, 1e8])
        plt.ylabel("Relative virtual runtime (ns)")
        plt.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=1)
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"vruntime_{save_names[index]}.pdf"))

        # plt.figure(figsize=(5, 5*0.618))
        # for idx, thread in enumerate(selected_threads):
        #     plt.scatter(idx, thread.abs_client_vruntime, color=colors[idx%len(colors)], zorder=2)
        # plt.yscale("log")
        # plt.xlabel("Thread Index")
        # plt.ylabel("Absolute client virtual runtime (ns)")
        # plt.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=1)
        # plt.tight_layout()
        # plt.savefig(os.path.join(result_dir, f"vruntime_{save_names[index]}_client_abs.pdf"))


        # Analysis co-occurrence on server_on_rq
        thread_pids_t = []
        # thread_selected_for_coorcurrence = [thread for thread in threads_info if thread.server_core==32]
        # thread_selected_for_coorcurrence.sort(key=lambda x: x.port)
        # for i in range(len(threads_info[0].server_on_rq)):
        #     pids_at_time_i = []
        #     for idx, thread in enumerate(thread_selected_for_coorcurrence):
        #         if thread.server_on_rq[i] == 1:
        #             pids_at_time_i.append(idx)
        #     thread_pids_t.append(pids_at_time_i)
        
        thread_selected_for_coorcurrence = [thread for thread in threads_info if thread.client_core==core_selection[index]]
        thread_selected_for_coorcurrence.sort(key=lambda x: x.port)
        for i in range(len(threads_info[0].client_on_rq)):
            pids_at_time_i = []
            for idx, thread in enumerate(thread_selected_for_coorcurrence):
                if thread.client_on_rq[i] == 1:
                    pids_at_time_i.append(idx)
            thread_pids_t.append(pids_at_time_i)

        C = build_cooccurrence(thread_pids_t, len(thread_selected_for_coorcurrence))
        plt.figure(figsize=(6, 5))
        plt.imshow(C, cmap='Reds', interpolation='nearest')
        # write numbers on heatmap with white color and black edge. font size 2
        for i in range(C.shape[0]):
            for j in range(C.shape[1]):
                text = plt.text(j, i, C[i, j], fontsize=4,
                               ha="center", va="center", color="white",
                               path_effects=[path_effects.Stroke(linewidth=1.5, foreground='black'), path_effects.Normal()])
        plt.colorbar(label='Co-occurrence Count')
        plt.xlabel('Thread Index')
        plt.ylabel('Thread Index')
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"vruntime_{save_names[index]}_cooccurrence.pdf"))
        plt.close()

if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"
    experiments = [
        # "airq_client_decoupled_1_1/32_64_1_1_1_3_0_0_16_0", # core 32
        # "airq_client_decoupled_1_1/64_64_1_1_1_3_0_0_16_0", # core 32
        # "nirq_client_decoupled_1_1/32_64_1_1_1_3_0_0_16_0", # core 96
        # "nirq_client_decoupled_1_1/64_64_1_1_1_3_0_0_16_1", # core 96
        # "dirq_client_decoupled_1_1/32_64_1_1_1_3_0_0_16_2", # core 32
        # "dirq_client_decoupled_1_1/64_64_1_1_1_3_0_0_16_2", # core 32
        # "airq_client_decoupled_2_1/64_64_1_1_1_1_0_0_16_0", # core 32
        # "airq_client_decoupled_2_1/32_64_1_1_1_1_0_0_16_0", # core 32
        # "nirq_client_decoupled_2_1/64_64_1_1_1_1_0_0_16_2", # core 32
        # "nirq_client_decoupled_2_1/32_64_1_1_1_1_0_0_16_2", # core 32
        # "dirq_client_decoupled_2_1/64_64_1_1_1_1_0_0_16_4", # core 32
        # "dirq_client_decoupled_2_1/32_64_1_1_1_1_0_0_16_4", # core 32
        # "airq_server_decoupled_1_1/52_64_1_1_1_4_0_0_13_0", # core 96
        # "dirq_server_decoupled_1_1/48_64_1_1_1_4_0_0_12_1", # core 32
        # "nirq_server_decoupled_1_1/48_64_1_1_1_4_0_0_12_1", # core 32
        "airq_packet_runqueue_1_1/52_64_1_1_1_1_0_0_1_0"
    ]

    save_names = [
        # "airq_decoupled_32",
        # "airq_decoupled_64",
        # "nirq_decoupled_32",
        # "nirq_decoupled_64",
        # "dirq_decoupled_32",
        # "dirq_decoupled_64",
        # "airq_decoupled_2_64",
        # "airq_decoupled_2_32",
        # "nirq_decoupled_2_64",
        # "nirq_decoupled_2_32",
        # "dirq_decoupled_2_64",
        # "dirq_decoupled_2_32",
        # "airq_decoupled_server_1_52",
        # "dirq_decoupled_server_1_48",
        # "nirq_decoupled_server_1_48",
        "airq_packet_runqueue_1_52"
    ]

    # single core or two core
    # single_core = [False, False, False, False, False, False, True, True, True, True, True, True]
    single_core = [False, False, False]

    # n_threads = [32, 64, 32, 64, 32, 64, 64, 32, 64, 32, 64, 32]
    n_threads = [52, 48, 48]
    # core_selection = [32, 32, 96, 96, 32, 32]
    # core_selection = [96, 96, 32, 32, 32, 32, 32, 32, 32, 32, 32, 32]
    core_selection = [32, 32, 32]
    draw_single()

    # draw_combined()