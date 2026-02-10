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

# 40 colors
colors = ["firebrick", "darkorange", "forestgreen", "royalblue", "darkviolet",
            "gold", "turquoise", "limegreen", "coral", "mediumblue",
            "purple", "sienna", "olive", "teal", "navy",
            "magenta", "peru", "darkcyan", "indigo", "darkgoldenrod",
            "lightcoral", "darkorange", "seagreen", "dodgerblue", "orchid",
            "chocolate", "darkslategray", "mediumseagreen", "cornflowerblue", "plum",
            "sandybrown", "cadetblue", "limegreen", "deepskyblue", "violet",
            "tan", "steelblue", "springgreen", "royalblue", "fuchsia",
            "burlywood", "slateblue", "mediumturquoise", "crimson", "darkolivegreen"]

class ThreadData:
    def __init__(self, port=0, client_pid=0, client_core=0, server_pid=0, server_core=0, thpt=0, latency=0):
        self.port = port
        self.client_start_time = 0
        self.server_start_time = 0
        self.client_pid = client_pid
        self.client_core = client_core
        self.server_pid = server_pid
        self.server_core = server_core
        self.thpt = thpt
        self.latency = latency
        self.server_vruntime = []
        self.normed_server_vruntime = []
        self.client_vruntime = []
        self.normed_client_vruntime = []
        self.server_on_rq = []
        self.client_on_rq = []

    def __str__(self):
        return (f"Port: {self.port}, Client: {self.client_pid}@{self.client_core}, "
                f"Server: {self.server_pid}@{self.server_core}, "
                f"Throughput: {self.thpt}, Latency: {self.latency}, "
                f"#C_vruntime: {len(self.client_vruntime)}, #S_vruntime: {len(self.server_vruntime)}, "
                f"#C_on_rq: {len(self.client_on_rq)}, #S_on_rq: {len(self.server_on_rq)},")

    def __repr__(self):
        return f"<ThreadData port={self.port} client_pid={self.client_pid} thpt={self.thpt} latency={self.latency}>"


def norm_vruntime(vruntimes):
    if len(vruntimes) == 0:
        return []
    min_vruntime = min([v for v in vruntimes if v > 0], default=0)
    normed = []
    for v in vruntimes:
        normed.append(v - min_vruntime + 0.01 if v > 0 else 0.01)
    return normed


def build_cooccurrence(thread_pids_t, n_threads):
    C = np.zeros((n_threads, n_threads), dtype=int)
    for pids in thread_pids_t:
        for i, j in itertools.combinations(pids, 2):
            C[i, j] += 1
            C[j, i] += 1
    return C


def parse_all_thread_info(experiment_dir, total_threads):
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
            time, core, pid, port = float(items[0]), int(items[2]), int(items[4]), int(items[7])
            for thread in threads_info:
                if thread.port == port:
                    thread.server_start_time = time
                    thread.server_pid = pid
                    thread.server_core = core
    
    client_log_path = os.path.join(experiment_dir, f"client.log")
    with open(client_log_path, "r") as client_log:
        lines = client_log.readlines()
        for line in lines:
            items = line.split()
            if len(items) < 5:
                continue
            time, core, pid, port = float(items[0]), int(items[2]), int(items[4]), int(items[7])
            for thread in threads_info:
                if thread.port == port:
                    thread.client_start_time = time
                    thread.client_core = core

    # Sort thread by port number
    threads_info.sort(key=lambda x: x.port)

    # Validate server core assignment: half threads on core 96, half on core 32
    n_threads_on_96 = sum(1 for thread in threads_info if thread.server_core == 96)
    n_threads_on_32 = sum(1 for thread in threads_info if thread.server_core == 32)
    assert n_threads_on_96 == total_threads // 2 and n_threads_on_32 == total_threads // 2, \
        f"Server core assignment error: {n_threads_on_96} on 96, {n_threads_on_32} on 32 for total {total_threads} threads."

    return threads_info

def parse_vruntime(threads_info, client_vruntime_path, server_vruntime_path):
    with open(client_vruntime_path, "r") as client_log:
        lines = client_log.readlines()
        line_index = 0
        in_record = 0
        while line_index < len(lines):
            if not in_record:
                if "iterate_cfs_rq:" in lines[line_index]:
                    in_record = 1
                    line_index += 1
                else:
                    line_index += 1
                continue

            line = lines[line_index]
            if "All-thread IDs:" in line:
                items = line.split()
                thread_index = items.index("IDs:") + 1
                thread_pids = [int(pid_str) for pid_str in items[thread_index:]]
                vruntime_items = lines[line_index + 1].split()
                vruntime_index = vruntime_items.index("vruntime:") + 1
                thread_vruntimes = [int(v_str) for v_str in vruntime_items[vruntime_index:]]
                for thread in threads_info:
                    if thread.client_pid in thread_pids:
                        pid_idx = thread_pids.index(thread.client_pid)
                        thread.client_vruntime.append(thread_vruntimes[pid_idx])
                    else:
                        thread.client_vruntime.append(0)
                line_index += 4
            else:
                line_index += 1

    with open(server_vruntime_path, "r") as server_log:
        lines = server_log.readlines()
        line_index = 0
        in_record = 0
        while line_index < len(lines):
            if not in_record:
                if "iterate_cfs_rq:" in lines[line_index]:
                    in_record = 1
                    line_index += 1
                else:
                    line_index += 1
                continue

            line = lines[line_index]
            if "All-thread IDs:" in line:
                items = line.split()
                thread_index = items.index("IDs:") + 1
                thread_pids = [int(pid_str) for pid_str in items[thread_index:]]
                vruntime_items = lines[line_index + 1].split()
                vruntime_index = vruntime_items.index("vruntime:") + 1
                thread_vruntimes = [int(v_str) for v_str in vruntime_items[vruntime_index:]]
                for thread in threads_info:
                    if thread.server_pid in thread_pids:
                        pid_idx = thread_pids.index(thread.server_pid)
                        thread.server_vruntime.append(thread_vruntimes[pid_idx])
                    else:
                        thread.server_vruntime.append(0)
                line_index += 4
            else:
                line_index += 1

    # Normalize vruntime
    threads_on_96 = [thread for thread in threads_info if thread.client_core == 96]
    for time_idx in range(len(threads_on_96[0].client_vruntime)):
        vruntimes_at_time = [thread.client_vruntime[time_idx] for thread in threads_on_96]
        normed_vruntimes = norm_vruntime(vruntimes_at_time)
        for idx, thread in enumerate(threads_on_96):
            thread.normed_client_vruntime.append(normed_vruntimes[idx])
    for time_idx in range(len(threads_on_96[0].server_vruntime)):
        vruntimes_at_time = [thread.server_vruntime[time_idx] for thread in threads_on_96]
        normed_vruntimes = norm_vruntime(vruntimes_at_time)
        for idx, thread in enumerate(threads_on_96):
            thread.normed_server_vruntime.append(normed_vruntimes[idx])

    return threads_info
    

def parse_on_rq(threads_info, client_vruntime_path, server_vruntime_path):
    # Parse client vruntime
    with open(client_vruntime_path, "r") as client_log:
        lines = client_log.readlines()
        line_index = 0
        in_record = 0
        while line_index < len(lines):
            if not in_record:
                if "Loading filter module" in lines[line_index]:
                    in_record = 1
                    line_index += 1
                else:
                    line_index += 1
                continue
            line = lines[line_index]
            items = line.split()

            if "Netfilter Runqueue IDs:" in line:
                pid_start_index = items.index("IDs:") + 1
                pids = [int(pid_str) for pid_str in items[pid_start_index:]]
                # print(f"Client RQ PIDs at line {line_index}: {pids}")
                for thread in threads_info:
                    if thread.client_pid in pids:
                        thread.client_on_rq.append(1)
                    else:
                        thread.client_on_rq.append(0)
            line_index += 1

    with open(server_vruntime_path, "r") as server_log:
        lines = server_log.readlines()
        line_index = 0
        in_record = 0
        while line_index < len(lines):
            if not in_record:
                if "Loading filter module" in lines[line_index]:
                    in_record = 1
                    line_index += 1
                else:
                    line_index += 1
                continue
            line = lines[line_index]
            items = line.split()

            if "Netfilter Runqueue IDs:" in line:
                pid_start_index = items.index("IDs:") + 1
                pids = [int(pid_str) for pid_str in items[pid_start_index:]]
                for thread in threads_info:
                    if thread.server_pid in pids:
                        thread.server_on_rq.append(1)
                    else:
                        thread.server_on_rq.append(0)
            line_index += 1

    return threads_info


def draw_coorcurrence(threads_info, index):
            # Build co-occurrence matrix for threads on core 96
        thread_pids_t = []
        thread_selected_for_coorcurrence = [thread for thread in threads_info if thread.client_core == 96]
        thread_selected_for_coorcurrence.sort(key=lambda x: x.port)

        for i in range(len(threads_info[0].client_on_rq)):
            pids_at_time_i = []
            for idx, thread in enumerate(thread_selected_for_coorcurrence):
                if thread.client_on_rq[i] == 1:
                    pids_at_time_i.append(idx)
            thread_pids_t.append(pids_at_time_i)

        C1 = build_cooccurrence(thread_pids_t, len(thread_selected_for_coorcurrence))
        plt.figure(figsize=(6, 5))
        plt.imshow(C1, cmap='Reds', interpolation='nearest')
        # write numbers on heatmap with white color and black edge. font size 2
        for i in range(C1.shape[0]):
            for j in range(C1.shape[1]):
                text = plt.text(j, i, C1[i, j], fontsize=4,
                               ha="center", va="center", color="white",
                               path_effects=[path_effects.Stroke(linewidth=1.5, foreground='black'), path_effects.Normal()])
        plt.colorbar(label='Co-occurrence Count')
        plt.xlabel('Thread Index')
        plt.ylabel('Thread Index')
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"vruntime_{save_names[index]}_cooccurrence.pdf"))
        plt.close()

        for i in range(len(threads_info[0].server_on_rq)):
            pids_at_time_i = []
            for idx, thread in enumerate(thread_selected_for_coorcurrence):
                if thread.server_on_rq[i] == 1:
                    pids_at_time_i.append(idx)
            thread_pids_t.append(pids_at_time_i)
        C2 = build_cooccurrence(thread_pids_t, len(thread_selected_for_coorcurrence))
        plt.figure(figsize=(6, 5))
        plt.imshow(C2, cmap='Reds', interpolation='nearest')
        # write numbers on heatmap with white color and black edge. font size 2
        for i in range(C2.shape[0]):
            for j in range(C2.shape[1]):
                text = plt.text(j, i, C2[i, j], fontsize=4,
                               ha="center", va="center", color="white",
                               path_effects=[path_effects.Stroke(linewidth=1.5, foreground='black'), path_effects.Normal()])
        plt.colorbar(label='Co-occurrence Count')
        plt.xlabel('Thread Index')
        plt.ylabel('Thread Index')
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"vruntime_{save_names[index]}_server_cooccurrence.pdf"))
        plt.close()

        C = C1 + C2
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
        plt.savefig(os.path.join(result_dir, f"vruntime_{save_names[index]}_combined_cooccurrence.pdf"))
        plt.close()


def draw_vruntime(threads_info, index):
    selected_threads = [thread for thread in threads_info if thread.client_core == 96]
    selected_threads.sort(key=lambda x: x.port)
    plt.figure(figsize=(6, 6*0.618))
    for thread in selected_threads:
        plt.plot(thread.normed_client_vruntime, label=f"Port {thread.port} C", color=colors[thread.port % len(colors)], linestyle='-')
        plt.text(len(thread.normed_client_vruntime), thread.normed_client_vruntime[-1], f"{thread.port-10000-n_threads[index]//2}", fontsize=6, color=colors[thread.port % len(colors)], va='center')
    plt.xlabel("Time (s)")
    plt.ylabel("Relative virtual runtime")
    plt.tight_layout()
    plt.savefig(os.path.join(result_dir, f"vruntime_{save_names[index]}_client_vruntime.pdf"))
    plt.close()

    plt.figure(figsize=(6, 6*0.618))
    for thread in selected_threads:
        plt.plot(thread.normed_server_vruntime, label=f"Port {thread.port} S", color=colors[thread.port % len(colors)], linestyle='-')
        plt.text(len(thread.normed_server_vruntime), thread.normed_server_vruntime[-1], f"{thread.port-10000-n_threads[index]//2}", fontsize=6, color=colors[thread.port % len(colors)], va='center')
    plt.xlabel("Time (s)")
    plt.ylabel("Relative virtual runtime")
    plt.tight_layout()
    plt.savefig(os.path.join(result_dir, f"vruntime_{save_names[index]}_server_vruntime.pdf"))
    plt.close()


def draw_on_rq(threads_info, index):
    selected_threads = [thread for thread in threads_info if thread.client_core == 96]
    # For server and client side, draw a bar graph showing how many times each threads is on rq:
    # x-axis: thread port number - 10000 - n_threads/2
    # y-axis: number of times on rq
    selected_threads.sort(key=lambda x: x.port)
    client_on_rq_counts = [sum(thread.client_on_rq) for thread in selected_threads]
    server_on_rq_counts = [sum(thread.server_on_rq) for thread in selected_threads]
    total_counts = [c + s for c, s in zip(client_on_rq_counts, server_on_rq_counts)]

    x_labels = [thread.port - 10000 - n_threads[index]//2 for thread in selected_threads]
    x = np.arange(len(selected_threads))
    plt.figure(figsize=(10, 10*0.618))
    width = 0.25
    plt.bar(x - width, client_on_rq_counts, width=width, label='Client on RQ', color='royalblue')
    plt.bar(x, server_on_rq_counts, width=width, label='Server on RQ', color='orange')
    plt.bar(x + width, total_counts, width=width, label='Total on RQ', color='forestgreen', alpha=0.5)
    plt.xlabel("Thread Index")
    plt.ylabel("Number of times on runqueue")
    plt.xticks(x, x_labels)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(result_dir, f"vruntime_{save_names[index]}_on_rq_counts.pdf"))
    plt.close()


def draw_single_threads():

    for index, experiment in enumerate(experiments):
        experiment_dir = os.path.join(result_dir, experiment)
        total_threads = n_threads[index]
        threads_info = parse_all_thread_info(experiment_dir, total_threads)

        # Parse virtual runtime for threads_info for analyzing vruntime impact
        client_vruntime_path = os.path.join(experiment_dir, f"iter_thread_client.log")
        server_vruntime_path = os.path.join(experiment_dir, f"iter_thread_server.log")
        threads_info = parse_on_rq(threads_info, client_vruntime_path, server_vruntime_path)
        threads_info = parse_vruntime(threads_info, client_vruntime_path, server_vruntime_path)

        threads_info.sort(key=lambda x: x.port)

        # Print parsed thread info
        for thread in threads_info:
            print(thread)

        draw_vruntime(threads_info, index)
        draw_coorcurrence(threads_info, index)
        draw_on_rq(threads_info, index)



if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"
    experiments = [
        "airq_packet_runqueue_1_1/52_64_1_1_1_1_0_0_1_1",
    ]

    save_names = [
        "airq_packet_runqueue",
    ]

    # experiments = [
    #     "nirq_pktirq_1_1/48_64_1_1_1_1_0_0_1_3",
    #     "airq_pktirq_1_1/52_64_1_1_1_1_0_0_1_3",
    # ]
    # label_names = [
    #     "Linux",
    #     "Linux + cIRQa"
    # ]
    # save_name = "3"

    n_threads = [52]

    draw_single_threads()

    # draw_combined()