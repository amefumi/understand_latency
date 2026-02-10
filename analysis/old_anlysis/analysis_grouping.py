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
                f"#C_on_rq: {len(self.client_on_rq)}, #S_on_rq: {len(self.server_on_rq)}, "
                f"#C_abs_vruntime: {self.client_abs_vruntime}, #S_abs_vruntime: {self.server_abs_vruntime}")

    def __repr__(self):
        return f"<ThreadData port={self.port} client_pid={self.client_pid} thpt={self.thpt} latency={self.latency}>"


def norm_vruntime(vruntimes):
    if len(vruntimes) == 0:
        return []
    min_vruntime = min([v for v in vruntimes if v > 0], default=0)
    normed = []
    for v in vruntimes:
        normed.append(v - min_vruntime + 1 if v > 0 else 1)
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

    # Validate server core assignment: half threads on core 96, half on core 32
    n_threads_on_96 = sum(1 for thread in threads_info if thread.server_core == 96)
    n_threads_on_32 = sum(1 for thread in threads_info if thread.server_core == 32)
    assert n_threads_on_96 == total_threads // 2 and n_threads_on_32 == total_threads // 2, \
        f"Server core assignment error: {n_threads_on_96} on 96, {n_threads_on_32} on 32 for total {total_threads} threads."

    return threads_info


def parse_vruntime(threads_info, client_vruntime_path, server_vruntime_path):
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
    
    # Normalize vruntime: normed_vruntime = vruntime - min(vruntime) + 1.
    # 1. Get vruntime at time i for all threads, find the min value (non zero) among all threads at time i.
    # 2. For each thread, normed_vruntime[i] = vruntime[i] - min_vruntime + 1 if vruntime[i] > 0 else 1
    n_times = len(threads_info[0].client_vruntime)
    for time_index in range(n_times):
        client_virtual_runtimes_non_zero = [thread.client_vruntime[time_index] for thread in threads_info if thread.client_vruntime[time_index] > 0]
        server_virtual_runtimes_non_zero = [thread.server_vruntime[time_index] for thread in threads_info if thread.server_vruntime[time_index] > 0]    
        min_client_vruntime = min(client_virtual_runtimes_non_zero) if len(client_virtual_runtimes_non_zero) > 0 else 0
        min_server_vruntime = min(server_virtual_runtimes_non_zero) if len(server_virtual_runtimes_non_zero) > 0 else 0
        for thread in threads_info:
            if thread.client_vruntime[time_index] > 0:
                normed_client_vruntime = thread.client_vruntime[time_index] - min_client_vruntime + 1
            else:
                normed_client_vruntime = 1
            thread.normed_client_vruntime.append(normed_client_vruntime)

            if thread.server_vruntime[time_index] > 0:
                normed_server_vruntime = thread.server_vruntime[time_index] - min_server_vruntime + 1
            else:
                normed_server_vruntime = 1
            thread.normed_server_vruntime.append(normed_server_vruntime)

    # Calculate absolute vruntime increase: final_vruntime - initial_vruntime that is non-zero
    for thread in threads_info:
        client_vruntimes_non_zero = [v for v in thread.client_vruntime if v > 0]
        server_vruntimes_non_zero = [v for v in thread.server_vruntime if v > 0]
        if len(client_vruntimes_non_zero) >= 2:
            thread.client_abs_vruntime = client_vruntimes_non_zero[-1] - client_vruntimes_non_zero[0]
        else:
            thread.client_abs_vruntime = 0
        if len(server_vruntimes_non_zero) >= 2:
            thread.server_abs_vruntime = server_vruntimes_non_zero[-1] - server_vruntimes_non_zero[0]
        else:
            thread.server_abs_vruntime = 0

    return threads_info


def draw_single():

    for index, experiment in enumerate(experiments):
        experiment_dir = os.path.join(result_dir, experiment)
        total_threads = n_threads[index]
        threads_info = parse_all_thread_info(experiment_dir, total_threads)

        # Parse virtual runtime for threads_info for analyzing vruntime impact
        client_vruntime_path = os.path.join(experiment_dir, f"iter_thread_client.log")
        server_vruntime_path = os.path.join(experiment_dir, f"iter_thread_server.log")
        threads_info = parse_vruntime(threads_info, client_vruntime_path, server_vruntime_path)

        # Sort thread according to port number
        threads_info.sort(key=lambda x: x.port)

        # For each thread with core=96, plot the vruntime on client and server side. x-axis is the index, y-axis is the normalized vruntime. Draw all threads in one single figure.
        plt.figure(figsize=(6, 6*0.618))
        for i, thread in enumerate(threads_info):
            if thread.client_core == 96:
                plt.plot(thread.normed_client_vruntime[300:600], label=f'Port {thread.port}', color=colors[(thread.port-10000)%40], linestyle='-')
                plt.text(305, thread.normed_client_vruntime[599], f'{thread.port-10000-n_threads[index]//2}', fontsize=6, color=colors[(thread.port-10000)%40], va='center')
                for j in range(300, 600):
                    if thread.client_on_rq[j] == 1:
                        plt.scatter(j-300, thread.normed_client_vruntime[j], color=colors[(thread.port-10000)%40], marker='o', s=5, edgecolors='black', zorder=3)
        plt.xlabel("Time (0.1 second)")
        plt.ylabel("Relative virtual runtime")
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_client_vruntime_core96.pdf"))
        plt.close()

        plt.figure(figsize=(6, 6*0.618))
        for i, thread in enumerate(threads_info):
            if thread.server_core == 96:
                plt.plot(thread.normed_server_vruntime[300:600], label=f'Port {thread.port}', color=colors[(thread.port-10000)%40], linestyle='-')
                plt.text(305, thread.normed_server_vruntime[599], f'{thread.port-10000-n_threads[index]//2}', fontsize=6, color=colors[(thread.port-10000)%40], va='center')
                for j in range(300, 600):
                    if thread.server_on_rq[j] == 1:
                        plt.scatter(j-300, thread.normed_server_vruntime[j], color=colors[(thread.port-10000)%40], marker='o', s=5, edgecolors='black', zorder=3)
        plt.xlabel("Time (0.1 second)")
        plt.ylabel("Relative virtual runtime")
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_server_vruntime_core96.pdf"))
        plt.close()

        # For server and client, for each thread (y-axis), draw the on_rq with time (x-axis) during 300~600. Draw all threads in one single figure.
        plt.figure(figsize=(6, 6*0.618))
        for i, thread in enumerate(threads_info):
            if thread.client_core == 96:
                on_rq_times = [j-300 for j in range(300, 600) if thread.client_on_rq[j] == 1]
                on_rq_values = [(thread.port - 10000 - n_threads[index] // 2)] * len(on_rq_times)
                plt.scatter(on_rq_times, on_rq_values, label=f'Port {thread.port}', color=colors[(thread.port-10000)%40], marker='o', s=5, edgecolors='black', zorder=3)
                plt.text(-5, thread.port - 10000 - n_threads[index] // 2, f'{len(on_rq_times)}', fontsize=4, color='red', ha='center')
        plt.xlabel("Time (0.1 second)")
        plt.ylabel("Thread (core 96)")
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_client_on_rq_core96.pdf"))
        plt.close()

        plt.figure(figsize=(6, 6*0.618))
        for i, thread in enumerate(threads_info):
            if thread.server_core == 96:
                on_rq_times = [j-300 for j in range(300, 600) if thread.server_on_rq[j] == 1]
                on_rq_values = [(thread.port - 10000 - n_threads[index] // 2)] * len(on_rq_times)
                plt.scatter(on_rq_times, on_rq_values, label=f'Port {thread.port}', color=colors[(thread.port-10000)%40], marker='o', s=5, edgecolors='black', zorder=3)
                plt.text(-5, thread.port - 10000 - n_threads[index] // 2, f'{len(on_rq_times)}', fontsize=4, color='red', ha='center')
        plt.xlabel("Time (0.1 second)")
        plt.ylabel("Thread (core 96)")
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_server_on_rq_core96.pdf"))
        plt.close()

        # Build co-occurrence matrix for client and server side
        client_on_rq_pids_t = []
        server_on_rq_pids_t = []
        for i in range(300, 600):
            client_pids = [thread.port-10000-(n_threads[index]//2) for thread in threads_info if thread.client_on_rq[i] == 1 and thread.client_core == 96]
            server_pids = [thread.port-10000-(n_threads[index]//2) for thread in threads_info if thread.server_on_rq[i] == 1 and thread.server_core == 96]
            client_on_rq_pids_t.append(client_pids)
            server_on_rq_pids_t.append(server_pids)
        
        print(client_on_rq_pids_t)
        C_client = build_cooccurrence(client_on_rq_pids_t, n_threads[index]//2)
        C_server = build_cooccurrence(server_on_rq_pids_t, n_threads[index]//2)
        plt.figure(figsize=(6, 6*0.618))
        plt.imshow(C_client, cmap='Reds')
        plt.colorbar(label='Co-occurrence Count')
        plt.xlabel('Thread (core 96)')
        plt.ylabel('Thread (core 96)')
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_client_cooccurrence_core96.pdf"))
        plt.close()
        plt.figure(figsize=(6, 6*0.618))
        plt.imshow(C_server, cmap='Reds')
        plt.colorbar(label='Co-occurrence Count')
        plt.xlabel('Thread (core 96)')
        plt.ylabel('Thread (core 96)')
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_server_cooccurrence_core96.pdf"))
        plt.close()

if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"
    experiments = [
        "airq_vruntime_fine_1_1/52_64_1_1_1_1_0_0_1_0",
    ]

    save_names = [
        "airq_vruntime_fine",
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

    draw_single()

    # draw_combined()