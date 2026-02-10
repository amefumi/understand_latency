import os
import re
import numpy as np
from xmlrpc import server
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
    def __init__(self):
        
        self.port = 0
        self.thpt = 0
        self.latency = 0
        self.packets = 0

        self.client_pid = 0
        self.client_core = 0
        self.client_softirq_packets = 0
        self.client_sched_latency = 0
        self.client_nivcsw = 0
        self.client_nvcsw = 0
        self.client_vruntime = []
        self.client_abs_vruntime = 0
        self.client_inflation = 0

        self.server_pid = 0
        self.server_core = 0
        self.server_softirq_packets = 0
        self.server_sched_latency = 0
        self.server_nivcsw = 0
        self.server_nvcsw = 0
        self.server_vruntime = []
        self.server_abs_vruntime = 0
        self.server_inflation = 0

    def __str__(self):
        return (f"--port: {self.port}, thpt: {self.thpt}, lat: {self.latency}, pkts: {self.packets}, "
                f"\t| Client: cpu-{self.client_core}, "
                f"#pkts-{self.client_softirq_packets}, sched_lat-{self.client_sched_latency}, "
                f"nvcsw-{self.client_nvcsw}, nivcsw={self.client_nivcsw}, abs_vrun-{self.client_abs_vruntime}, infl-{int(self.client_inflation)} "
                f"\t| Server: cpu-{self.server_core}, "
                f"#pkts-{self.server_softirq_packets}, sched_lat-{self.server_sched_latency}), "
                f"nvcsw-{self.server_nvcsw}, nivcsw={self.server_nivcsw}, abs_vrun-{self.server_abs_vruntime}, infl-{int(self.server_inflation)}")

    def __repr__(self):
        return f"<ThreadData port={self.port} client_pid={self.client_pid} thpt={self.thpt} latency={self.latency}>"


def read_histogram(file_path):
    assert os.path.exists(file_path), f"File {file_path} does not exist"
    with open(file_path, 'rb') as f:
        data = np.fromfile(f, dtype=np.uint64, count=100000)
    return data

def norm_vruntime(vruntime_line, base_value=1):
    if len(vruntime_line) == 0:
        return []
    min_vruntime = min(vruntime_line)
    normed = []
    for v in vruntime_line:
        normed.append(v - min_vruntime + base_value)
        # normed.append(v + 1)
    return normed

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

    for thread in threads_info:
        i = thread.port - 10000
        histo_log_path = os.path.join(experiment_dir, f"netperf-{i}_hist.bin")
        hist_data = read_histogram(histo_log_path)
        thread.packets = int(np.sum(hist_data, dtype=np.uint64))

    # read the core and pid info
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
    
    # read client general info and involuntary context switch count
    client_log_path = os.path.join(experiment_dir, f"client.log")
    with open(client_log_path, "r") as client_log:
        lines = client_log.readlines()
        for line in lines:
            items = line.split()
            if "cpu:" in line:
                core, pid, port = int(items[2]), int(items[4]), int(items[7])
                for thread in threads_info:
                    if thread.port == port:
                        thread.client_core = core
            elif "involuntary-context-switch-count:" in line:
                pid, nivcsw = int(items[1]), int(items[3])
                for thread in threads_info:
                    if thread.client_pid == pid:
                        thread.client_nivcsw = nivcsw
            elif "voluntary-context-switch-count:" in line:
                pid, nvcsw = int(items[1]), int(items[3])
                for thread in threads_info:
                    if thread.client_pid == pid:
                        thread.client_nvcsw = nvcsw
            elif "start-vruntime:" in line:
                pid, start_vruntime = int(items[1]), int(items[3])
                for thread in threads_info:
                    if thread.client_pid == pid:
                        thread.client_vruntime.append(start_vruntime)
            elif "final-vruntime:" in line:
                pid, end_vruntime = int(items[1]), int(items[3])
                for thread in threads_info:
                    if thread.client_pid == pid:
                        thread.client_abs_vruntime = end_vruntime - thread.client_vruntime[0]
            else:
                continue

    # read client inflation info
    client_inflation_path = os.path.join(experiment_dir, f"breakdown_sum_p90_client.txt")
    with open(client_inflation_path, "r") as client_inflation_log:
        lines = client_inflation_log.readlines()
        for line in lines[1:]:
            items = line.split()
            port, inflation = int(items[0]), float(items[3])
            for thread in threads_info:
                if thread.port == port:
                    thread.client_inflation = inflation

    # read server inflation info
    server_inflation_path = os.path.join(experiment_dir, f"breakdown_sum_p90_server.txt")
    with open(server_inflation_path, "r") as server_inflation_log:
        lines = server_inflation_log.readlines()
        for line in lines[1:]:
            items = line.split()
            port, inflation = int(items[0]), float(items[3])
            for thread in threads_info:
                if thread.port == port:
                    thread.server_inflation = inflation

    # read server involuntary context switch count
    server_nivcsw_path = os.path.join(experiment_dir, f"server_nivcsw.log")
    with open(server_nivcsw_path, "r") as server_nivcsw_log:
        lines = server_nivcsw_log.readlines()
        for line in lines:
            items = line.split()
            if len(items) < 3:
                continue
            pid, nivcsw, nvcsw = int(items[0]), int(items[1]), int(items[2])
            for thread in threads_info:
                if thread.server_pid == pid:
                    thread.server_nivcsw = int(nivcsw * (300/297))
                    thread.server_nvcsw = int(nvcsw * (300/297))

    # read the scheduling latency info
    client_sched_path = os.path.join(experiment_dir, f"sched_client_{total_threads}.txt")
    with open(client_sched_path, "r") as client_sched_log:
        lines = client_sched_log.readlines()
        for line in lines[1:]: # skip header
            items = line.split(',')
            if len(items) < 4:
                continue
            port, avg_latency, p999_latency = int(items[0]), float(items[1]), int(items[3])
            for thread in threads_info:
                if thread.port == port:
                    thread.client_sched_latency = p999_latency
                    thread.client_sched_latency_avg = avg_latency

    server_sched_path = os.path.join(experiment_dir, f"sched_server_{total_threads}.txt")
    with open(server_sched_path, "r") as server_sched_log:
        lines = server_sched_log.readlines()
        for line in lines[1:]: # skip header
            items = line.split(',')
            if len(items) < 4:
                continue
            port, avg_latency, p999_latency = int(items[0]), float(items[1]), int(items[3])
            for thread in threads_info:
                if thread.port == port:
                    thread.server_sched_latency = p999_latency
                    thread.server_sched_latency_avg = avg_latency

    # Sort thread by port number
    threads_info.sort(key=lambda x: x.port)
    return threads_info


def parse_netfilter(threads_info, experiment_dir):
    client_log_path = os.path.join(experiment_dir, f"iter_thread_client.log")
    with open(client_log_path, "r") as log:
        lines = log.readlines()
        line_index = 0
        in_record = False
        while line_index < len(lines):
            if not in_record:
                if "Loading filter module" in lines[line_index]:
                    in_record = True
                line_index += 1
                continue

            line = lines[line_index]
            counts = 0
            if "Core:" in line and "PIDs" in line and counts < NETFILTER_COUNT:
                counts += 1
                start_index = line.split().index("PIDs:")
                pid_items = [int(item) for item in line.split()[start_index + 1:]]
                count_line = lines[line_index + 1]
                start_index = count_line.split().index("Counts:")
                count_items = [int(item) for item in count_line.split()[start_index + 1:]]
                for pid, count in zip(pid_items, count_items):
                    for thread in threads_info:
                        if thread.client_pid == pid:
                            thread.client_softirq_packets += count
                line_index += 2
            else:
                line_index += 1

    server_log_path = os.path.join(experiment_dir, f"iter_thread_server.log")
    with open(server_log_path, "r") as log:
        lines = log.readlines()
        line_index = 0
        in_record = False
        while line_index < len(lines):
            if not in_record:
                if "Loading filter module" in lines[line_index]:
                    in_record = True
                line_index += 1
                continue

            line = lines[line_index]
            counts = 0
            if "Core:" in line and "PIDs" in line and counts < NETFILTER_COUNT:
                counts += 1
                start_index = line.split().index("PIDs:")
                pid_items = [int(item) for item in line.split()[start_index + 1:]]
                count_line = lines[line_index + 1]
                start_index = count_line.split().index("Counts:")
                count_items = [int(item) for item in count_line.split()[start_index + 1:]]
                for pid, count in zip(pid_items, count_items):
                    for thread in threads_info:
                        if thread.server_pid == pid:
                            thread.server_softirq_packets += count
                line_index += 2
            else:
                line_index += 1
    return threads_info


def parse_vruntime(threads_info, experiment_dir):
    client_vruntime_path = os.path.join(experiment_dir, f"iter_thread_client.log")
    server_vruntime_path = os.path.join(experiment_dir, f"iter_thread_server.log")
    # # Parse client vruntime
    # with open(client_vruntime_path, "r") as client_log:
    #     lines = client_log.readlines()
    #     line_index = 0
    #     in_record = False
    #     while line_index < len(lines):
    #         if not in_record:
    #             if "iterate_cfs_rq:" in lines[line_index]:
    #                 in_record = True
    #             line_index += 1
    #             continue

    #         line = lines[line_index]
    #         items = line.split()
    #         if "All-thread IDs:" in line and len(line.split()) > 7:
    #             thread_index = items.index("IDs:") + 1
    #             thread_pids = [int(items[i]) for i in range(thread_index, len(items))]
    #             vruntime_items = lines[line_index + 1].split()
    #             vruntime_index = vruntime_items.index("vruntime:") + 1
    #             thread_vruntimes = [int(vruntime_items[i]) for i in range(vruntime_index, len(vruntime_items))]
    #             on_rq_items = lines[line_index + 2].split()
    #             on_rq_index = on_rq_items.index("IDs:") + 1
    #             thread_pids_on_rq = [int(on_rq_items[i]) for i in range(on_rq_index, len(on_rq_items))]
    #             for thread in threads_info:
    #                 if thread.client_pid in thread_pids:
    #                     index = thread_pids.index(thread.client_pid)
    #                     thread.client_vruntime.append(thread_vruntimes[index])
    #                 else:
    #                     thread.client_vruntime.append(0)
    #             line_index += 4
    #         else:
    #             line_index += 1

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
                line_index += 4
            else:
                line_index += 1

    # Calculate absolute vruntime increase: final_vruntime - initial_vruntime that is non-zero
    for thread in threads_info:
        # client_vruntimes_non_zero = [v for v in thread.client_vruntime if v > 0]
        server_vruntimes_non_zero = [v for v in thread.server_vruntime if v > 0]
        # if len(client_vruntimes_non_zero) >= 2:
        #     thread.client_abs_vruntime = client_vruntimes_non_zero[-1] - client_vruntimes_non_zero[0]
        # else:
        #     thread.client_abs_vruntime = 0
        if len(server_vruntimes_non_zero) >= 2:
            thread.server_abs_vruntime = server_vruntimes_non_zero[-1] - server_vruntimes_non_zero[0]
        else:
            thread.server_abs_vruntime = 0

    return threads_info


if __name__ == "__main__":

    NETFILTER_COUNT = 30

    result_dir = "/data0/projects/latency/"
    experiments = [       
        # "sirq_breakdown_6_2/52_64_1_1_1_1_0_0_1_0",
        # "sirq_breakdown_2_1/52_64_1_1_1_1_0_0_1_0",
        "sirq_understanding_1_1/48_64_1_1_1_1_0_0_1_0",
        "sirq_understanding_1_1/48_64_1_1_1_1_0_0_1_1",
        "sirq_understanding_1_1/48_64_1_1_1_1_0_0_1_2",
        "sirq_understanding_1_1/48_64_1_1_1_1_0_0_1_3",
        "sirq_understanding_1_1/48_64_1_1_1_1_0_0_1_4"
    ]


    n_threads = [48, 48, 48, 48, 48]
    labels = [
        "0", "1", "2", "3", "4"
    ]

    # fig_latency_client = plt.figure(figsize=(fig_width, fig_height))
    # fig_latency_server = plt.figure(figsize=(fig_width, fig_height))
    # throughput_fig = plt.figure(figsize=(fig_width, fig_height))

    # ax_latency_client = fig_latency_client.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])
    # ax_latency_server = fig_latency_server.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])
    # ax_throughput = throughput_fig.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])

    for index, experiment, n_thread, label in zip(range(len(experiments)), experiments, n_threads, labels):
        experiment_dir = os.path.join(result_dir, experiment)
        threads_info = parse_all_thread_info(experiment_dir, n_thread)
        threads_info = parse_netfilter(threads_info, experiment_dir)
        threads_info = parse_vruntime(threads_info, experiment_dir)
        for thread in threads_info:
            print(thread)
        # # Figure 1: x axis: normalized abs vruntime, y axis: sched_lat; for client and server
        # fig_sched_lat = plt.figure(figsize=(5, 5*0.618))
        # ax_sched_lat = fig_sched_lat.add_axes([0.2, 0.2, 0.7, 0.7])
        # fig_vruntime = plt.figure(figsize=(5, 5*0.618))
        # ax_vruntime = fig_vruntime.add_axes([0.2, 0.2, 0.7, 0.7])
        # client_sched_lats = []
        # server_sched_lats = []
        # normed_abs_client_vruntimes = []
        # normed_abs_server_vruntimes = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         normed_abs_client_vruntimes.append(thread.client_abs_vruntime)
        #         normed_abs_server_vruntimes.append(thread.server_abs_vruntime)
        #         client_sched_lats.append(thread.client_sched_latency)
        #         server_sched_lats.append(thread.server_sched_latency)
        # normed_abs_client_vruntimes = norm_vruntime(normed_abs_client_vruntimes, 0)
        # normed_abs_server_vruntimes = norm_vruntime(normed_abs_server_vruntimes, 0)
        # ax_sched_lat.scatter(normed_abs_client_vruntimes, client_sched_lats, label="Client", color="blue", marker="o")
        # ax_sched_lat.scatter(normed_abs_server_vruntimes, server_sched_lats, label="Server", color="red", marker="^")
        # ax_sched_lat.set_xlabel("Absolute vruntime gap")
        # ax_sched_lat.set_ylabel("P99.9 rx_sched (us)")
        # ax_sched_lat.legend()
        # fig_sched_lat.savefig("rtc_SCHEDa_vruntime_gap_vs_sched_latency.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_sched_lat)
        # ax_vruntime.scatter(normed_abs_client_vruntimes, normed_abs_server_vruntimes, color="purple", marker="o")
        # ax_vruntime.set_xlabel("Client absolute vruntime gap")
        # ax_vruntime.set_ylabel("Server absolute vruntime gap")
        # fig_vruntime.savefig("rtc_SCHEDa_client_vs_server_vruntime_gap.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime)

        # # Figure 2: x axis: thread index, y axis: (1) bar chart to show abs vruntime (left y-axis); (2) line char to show throughput (right y-axis)
        # fig_vruntime_thpt = plt.figure(figsize=(10, 5*0.618))
        # ax_vruntime_bar = fig_vruntime_thpt.add_axes([0.1, 0.2, 0.6, 0.7])
        # ax_thpt_line = ax_vruntime_bar.twinx()
        # client_abs_vruntimes = []
        # server_abs_vruntimes = []
        # average_abs_vruntimes = []
        # throughputs = []
        # thread_indices = []
        # for idx, thread in enumerate(threads_info):
        #     if thread.client_core == 96:
        #         thread_indices.append(idx)
        #         client_abs_vruntimes.append(thread.client_abs_vruntime)
        #         server_abs_vruntimes.append(thread.server_abs_vruntime)
        #         average_abs_vruntimes.append((thread.client_abs_vruntime + thread.server_abs_vruntime)/2)
        #         throughputs.append(thread.thpt)
        # bar_width = 0.2
        # ax_vruntime_bar.bar(np.array(thread_indices) - bar_width, client_abs_vruntimes, width=bar_width, label="Client", edgecolor="royalblue", alpha=0.7, hatch='\\\\\\', fill=False, linewidth=2)
        # ax_vruntime_bar.bar(np.array(thread_indices), average_abs_vruntimes, width=bar_width, label="Average", edgecolor="green", alpha=0.7, hatch='///', fill=False, linewidth=2)
        # ax_vruntime_bar.bar(np.array(thread_indices) + bar_width, server_abs_vruntimes, width=bar_width, label="Server", edgecolor="orange", alpha=0.7, hatch='\\\\\\', fill=False, linewidth=2)
        # # bar_width = 0.35
        # # ax_vruntime_bar.bar(np.array(thread_indices) - bar_width/2, client_abs_vruntimes, width=bar_width, label="Client", edgecolor="royalblue", alpha=0.7, hatch='\\\\\\', fill=False, linewidth=2)
        # # ax_vruntime_bar.bar(np.array(thread_indices) + bar_width/2, server_abs_vruntimes, width=bar_width, label="Server", edgecolor="orange", alpha=0.7, hatch='\\\\\\', fill=False, linewidth=2)
        # ax_thpt_line.plot(thread_indices, throughputs, label="Throughput", color="green", marker="o")

        # ax_vruntime_bar.set_xlabel("Thread Index")
        # ax_vruntime_bar.set_ylabel("Absolute vruntime")
        # ax_vruntime_bar.legend(loc="upper left")
        # ax_vruntime_bar.set_ylim(min(client_abs_vruntimes + server_abs_vruntimes)*0.97, max(max(client_abs_vruntimes), max(server_abs_vruntimes)) * 1.03)
        # ax_thpt_line.set_ylabel("Throughput (IOPS)")
        # ax_thpt_line.legend(loc="upper right")
        # fig_vruntime_thpt.savefig("cIRQa_vruntime_and_throughput_vs_thread_index.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime_thpt)

        # Figure 3: x axis: thread index, y axis: (1) bar chart to show abs vruntime (left y-axis); (2) line char to show inflation (right y-axis)
        fig_vruntime_infl = plt.figure(figsize=(10, 5*0.618))
        ax_vruntime_bar = fig_vruntime_infl.add_axes([0.1, 0.2, 0.6, 0.7])
        ax_infl_line = ax_vruntime_bar.twinx()
        client_abs_vruntimes = []
        server_abs_vruntimes = []
        client_inflations = []
        server_inflations = []
        thread_indices = []
        for idx, thread in enumerate(threads_info):
            if thread.client_core == 96:
                thread_indices.append(idx)
                client_abs_vruntimes.append(thread.client_abs_vruntime)
                server_abs_vruntimes.append(thread.server_abs_vruntime)
                client_inflations.append(thread.client_inflation)
                server_inflations.append(thread.server_inflation)
        bar_width = 0.2
        ax_vruntime_bar.bar(np.array(thread_indices) - bar_width, client_abs_vruntimes, width=bar_width, label="Client", edgecolor="royalblue", alpha=0.7, hatch='\\\\\\', fill=False, linewidth=2)
        ax_vruntime_bar.bar(np.array(thread_indices) + bar_width, server_abs_vruntimes, width=bar_width, label="Server", edgecolor="orange", alpha=0.7, hatch='\\\\\\', fill=False, linewidth=2)
        ax_infl_line.plot(thread_indices, client_inflations, label="Client Inflation", color="blue", marker="o")
        ax_infl_line.plot(thread_indices, server_inflations, label="Server Inflation", color="red", marker="^")
        ax_vruntime_bar.set_xlabel("Thread Index")
        ax_vruntime_bar.set_ylabel("Absolute vruntime")
        ax_vruntime_bar.legend(loc="upper left")
        ax_vruntime_bar.set_ylim(min(client_abs_vruntimes + server_abs_vruntimes)*0.97, max(max(client_abs_vruntimes), max(server_abs_vruntimes)) * 1.03)
        ax_infl_line.set_ylabel("Inflation (us)")
        ax_infl_line.legend(loc="upper right")
        fig_vruntime_infl.savefig(f"check_inflation_unfiltered_{label}.pdf", dpi=300, bbox_inches='tight')
        plt.close(fig_vruntime_infl)

        # # Figure 5: x axis: thread index, y axis: abs vruntime. For each Client thread, draw two bar: (1) abs vruntime; (2) throughput*inflation*k, k is parameters.
        # fig_vruntime_infl_thpt = plt.figure(figsize=(10, 5*0.618))
        # ax_vruntime_bar = fig_vruntime_infl_thpt.add_axes([0.1, 0.2, 0.6, 0.7])
        # client_abs_vruntimes = []
        # combined_metrics = []
        # thread_indices = []
        # k = 1

        # # Find the best k to minimize the MSE between client_abs_vruntimes and combined_metrics
        # for idx, thread in enumerate(threads_info):
        #     if thread.client_core == 96:
        #         thread_indices.append(idx)
        #         client_abs_vruntimes.append(thread.client_abs_vruntime)
        # best_k = 1.0
        # min_mse = float('inf')
        # for k in np.arange(0.1, 10.0, 0.01):
        #     scaled_metrics = [thread.thpt * thread.client_inflation * k for thread in threads_info if thread.client_core == 96]
        #     mse = np.mean([(a - b) ** 2 for a, b in zip(client_abs_vruntimes, scaled_metrics)])
        #     if mse < min_mse:
        #         min_mse = mse
        #         best_k = k

        # for idx, thread in enumerate(threads_info):
        #     if thread.client_core == 96:
        #         combined_value = thread.thpt * thread.client_inflation * best_k
        #         combined_metrics.append(combined_value)

        # bar_width = 0.3
        # ax_vruntime_bar.bar(np.array(thread_indices) - bar_width/2, client_abs_vruntimes, width=bar_width, label="Client Abs Vruntime", edgecolor="forestgreen", hatch='\\\\\\', fill=False, linewidth=2)
        # ax_vruntime_bar.bar(np.array(thread_indices) + bar_width/2, combined_metrics, width=bar_width, label=f"Throughput * Inflation * {best_k:.2f}", edgecolor="firebrick", hatch='///', fill=False, linewidth=2)
        # ax_vruntime_bar.set_xlabel("Thread Index")
        # ax_vruntime_bar.set_ylabel("Absolute vruntime")
        # ax_vruntime_bar.legend(loc="upper left")
        # ax_vruntime_bar.set_ylim(min(client_abs_vruntimes + combined_metrics)*0.97, max(max(client_abs_vruntimes), max(combined_metrics)) * 1.03)
        # fig_vruntime_infl_thpt.savefig(f"check_throughput_attribution_unfiltered_52_{label}.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime_infl_thpt)

        # # Figure 6: x axis: thread index, y axis: abs vruntime. For each Server thread, draw two bar: (1) abs vruntime; (2) throughput*inflation*k, k is parameters.
        # fig_vruntime_infl_thpt = plt.figure(figsize=(10, 5*0.618))
        # ax_vruntime_bar = fig_vruntime_infl_thpt.add_axes([0.1, 0.2, 0.6, 0.7])
        # server_abs_vruntimes = []
        # combined_metrics = []
        # thread_indices = []
        # k = 1

        # # Find the best k to minimize the MSE between server_abs_vruntimes and combined_metrics
        # for idx, thread in enumerate(threads_info):
        #     if thread.client_core == 96:
        #         thread_indices.append(idx)
        #         server_abs_vruntimes.append(thread.server_abs_vruntime)
        # best_k = 1.0
        # min_mse = float('inf')
        # for k in np.arange(0.1, 10.0, 0.01):
        #     scaled_metrics = [thread.thpt * thread.server_inflation * k for thread in threads_info if thread.client_core == 96]
        #     mse = np.mean([(a - b) ** 2 for a, b in zip(server_abs_vruntimes, scaled_metrics)])
        #     if mse < min_mse:
        #         min_mse = mse
        #         best_k = k
        
        # for idx, thread in enumerate(threads_info):
        #     if thread.client_core == 96:
        #         combined_value = thread.thpt * thread.server_inflation * best_k
        #         combined_metrics.append(combined_value)

        # bar_width = 0.3
        # ax_vruntime_bar.bar(np.array(thread_indices) - bar_width/2, server_abs_vruntimes, width=bar_width, label="Server Abs Vruntime", edgecolor="forestgreen", hatch='\\\\\\', fill=False, linewidth=2)
        # ax_vruntime_bar.bar(np.array(thread_indices) + bar_width/2, combined_metrics, width=bar_width, label=f"Throughput * Inflation * {best_k:.2f}", edgecolor="firebrick", hatch='///', fill=False, linewidth=2)
        # ax_vruntime_bar.set_xlabel("Thread Index")
        # ax_vruntime_bar.set_ylabel("Absolute vruntime")
        # ax_vruntime_bar.legend(loc="upper left")
        # ax_vruntime_bar.set_ylim(min(server_abs_vruntimes + combined_metrics)*0.97, max(max(server_abs_vruntimes), max(combined_metrics)) * 1.03)
        # fig_vruntime_infl_thpt.savefig(f"check_throughput_attribution_unfiltered_52_server_{label}.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime_infl_thpt)

        # # Figure 1-1: x axis: throughput, y axis: last virtual runtime
        # fig_vruntime = plt.figure(figsize=(6, 6*0.618))
        # ax_vruntime = fig_vruntime.add_axes([0.2, 0.2, 0.7, 0.7])
        # client_vruntimes = []
        # server_vruntimes = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         client_vruntimes.append(int(thread.client_vruntime[-1]))
        #         server_vruntimes.append(int(thread.server_vruntime[-1]))
        #         throughputs.append(thread.thpt)
        # client_vruntimes = norm_vruntime(client_vruntimes)
        # server_vruntimes = norm_vruntime(server_vruntimes)
        # ax_vruntime.scatter(throughputs, client_vruntimes, label="Client vruntime", color="blue", marker="o")
        # ax_vruntime.scatter(throughputs, server_vruntimes, label="Server vruntime", color="red", marker="^")
        # ax_vruntime.set_xlabel("Throughput (IOPS)")
        # ax_vruntime.set_ylabel("Last vruntime")
        # ax_vruntime.legend()
        # fig_vruntime.savefig("add_up_last_vruntime_vs_throughput.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime)

        # # Figure 1-2: x axis: throughput, y axis: last virtual runtime
        # fig_vruntime = plt.figure(figsize=(6, 6*0.618))
        # ax_vruntime = fig_vruntime.add_axes([0.2, 0.2, 0.7, 0.7])
        # abs_client_vruntimes = []
        # abs_server_vruntimes = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         abs_client_vruntimes.append(int(thread.client_abs_vruntime))
        #         abs_server_vruntimes.append(int(thread.server_abs_vruntime))
        #         throughputs.append(thread.thpt)
        # ax_vruntime.scatter(throughputs, abs_client_vruntimes, label="Client vruntime", color="blue", marker="o")
        # ax_vruntime.scatter(throughputs, abs_server_vruntimes, label="Server vruntime", color="red", marker="^")
        # ax_vruntime.set_xlabel("Throughput (IOPS)")
        # ax_vruntime.set_ylabel("Absolute vruntime")
        # ax_vruntime.legend()
        # fig_vruntime.savefig("add_up_abs_vruntime_vs_throughput_sched.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime)

        # # Figure 2-1: x axis: throughput, y axis: voluntary context switch, total packets
        # fig_nvcsw = plt.figure(figsize=(6, 6*0.618))
        # ax_nvcsw = fig_nvcsw.add_axes([0.2, 0.2, 0.7, 0.7])
        # client_nvcsw = []
        # server_nvcsw = []
        # packets = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         throughputs.append(thread.thpt)
        #         packets.append(thread.packets)
        #         client_nvcsw.append(thread.client_nvcsw)
        #         server_nvcsw.append(thread.server_nvcsw)
        # ax_nvcsw.scatter(throughputs, client_nvcsw, label="Client Voluntary", color="blue", marker="o")
        # ax_nvcsw.scatter(throughputs, server_nvcsw, label="Server Voluntary", color="red", marker="o")
        # ax_nvcsw.scatter(throughputs, packets, label="Total Packets", color="green", marker="s")
        # ax_nvcsw.set_xlabel("Throughput (IOPS)")
        # ax_nvcsw.set_ylabel("Switches / Packets")
        # ax_nvcsw.legend()
        # fig_nvcsw.savefig("add_up_nvcsw_packets_vs_throughput.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_nvcsw)

        # # Figure 2-2: x axis: throughput, y axis: voluntary context switch, total packets
        # fig_nvcsw = plt.figure(figsize=(6, 6*0.618))
        # ax_nvcsw = fig_nvcsw.add_axes([0.2, 0.2, 0.7, 0.7])
        # client_nivcsw = []
        # server_nivcsw = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         throughputs.append(thread.thpt)
        #         client_nivcsw.append(thread.client_nivcsw)
        #         server_nivcsw.append(thread.server_nivcsw)
        # ax_nvcsw.scatter(throughputs, client_nivcsw, label="Client Voluntary", color="blue", marker="o")
        # ax_nvcsw.scatter(throughputs, server_nivcsw, label="Server Voluntary", color="red", marker="o")
        # ax_nvcsw.set_xlabel("Throughput (IOPS)")
        # ax_nvcsw.set_ylabel("Switches")
        # ax_nvcsw.legend()
        # fig_nvcsw.savefig("add_up_nivcsw_vs_throughput.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_nvcsw)

        # # Figure 2-3: x axis: throughput, y axis: voluntary context switch + involuntary context switch
        # fig_nvcsw = plt.figure(figsize=(6, 6*0.618))
        # ax_nvcsw = fig_nvcsw.add_axes([0.2, 0.2, 0.7, 0.7])
        # client_ncsw = []
        # server_ncsw = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         throughputs.append(thread.thpt)
        #         client_ncsw.append(thread.client_nivcsw + thread.client_nvcsw)
        #         server_ncsw.append(thread.server_nivcsw + thread.server_nvcsw)
        # ax_nvcsw.scatter(throughputs, client_ncsw, label="Client", color="blue", marker="o")
        # ax_nvcsw.scatter(throughputs, server_ncsw, label="Server", color="red", marker="o")
        # ax_nvcsw.set_xlabel("Throughput (IOPS)")
        # ax_nvcsw.set_ylabel("Switches")
        # ax_nvcsw.legend()
        # fig_nvcsw.savefig("add_up_ncsw_vs_throughput.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_nvcsw)

        # # Figure 4-1: x axis: throughput, y axis: server side last vruntime adjusted by server side involuntary context switch
        # fig_vruntime_server = plt.figure(figsize=(6, 6*0.618))
        # ax_vruntime_server = fig_vruntime_server.add_axes([0.2, 0.2, 0.7, 0.7])
        # weight = 10
        # server_vruntime = []
        # server_vruntime_adjusted = []
        # server_vruntime_vcsw = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         server_vruntime.append(thread.server_vruntime[-1])
        #         server_vruntime_adjusted.append(thread.server_vruntime[-1] - thread.server_nivcsw * weight)
        #         server_vruntime_vcsw.append(thread.server_vruntime[-1] - (thread.server_nivcsw - (thread.packets-thread.server_nvcsw)) * weight)
        #         throughputs.append(thread.thpt)
        # server_vruntime = norm_vruntime(server_vruntime)
        # server_vruntime_adjusted = norm_vruntime(server_vruntime_adjusted)
        # server_vruntime_vcsw = norm_vruntime(server_vruntime_vcsw)
        # ax_vruntime_server.scatter(throughputs, server_vruntime, label="Server", color="red", marker="o")
        # ax_vruntime_server.scatter(throughputs, server_vruntime_adjusted, label="Server (-ivcsw)", color="orange", marker="o")
        # ax_vruntime_server.scatter(throughputs, server_vruntime_vcsw, label="Server (-ivcsw+vcsw)", color="blue", marker="o")
        # min_thpt = min(throughputs)
        # ax_vruntime_server.set_xlabel("Throughput (IOPS)")
        # ax_vruntime_server.set_ylabel("Last vruntime")
        # ax_vruntime_server.legend()
        # # ax_vruntime_server.set_ylim(bottom=6.5e7)
        # fig_vruntime_server.savefig("add_up_vruntime_server_adjusted_vs_throughput.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime_server)

        # # Figure 4-2: x axis: throughput, y axis: server side abs vruntime adjusted by server side involuntary context switch
        # fig_vruntime_server = plt.figure(figsize=(6, 6*0.618))
        # ax_vruntime_server = fig_vruntime_server.add_axes([0.2, 0.2, 0.7, 0.7])
        # weight = 10
        # abs_server_vruntime = []
        # abs_server_vruntime_adjusted = []
        # abs_server_vruntime_vcsw = []
        # abs_server_vruntime_thpt_normed = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         abs_server_vruntime.append(thread.server_abs_vruntime)
        #         abs_server_vruntime_adjusted.append(thread.server_abs_vruntime - thread.server_nivcsw * weight)
        #         abs_server_vruntime_vcsw.append(thread.server_abs_vruntime - (thread.server_nivcsw - (thread.packets-thread.server_nvcsw)) * weight)
        #         throughputs.append(thread.thpt)
        # min_thpt = min(throughputs)
        # abs_server_vruntime_normed = ([v/thpt*min_thpt for v, thpt in zip(abs_server_vruntime_vcsw, throughputs)])
        # ax_vruntime_server.scatter(throughputs, abs_server_vruntime, label="Server", color="red", marker="o")
        # ax_vruntime_server.scatter(throughputs, abs_server_vruntime_adjusted, label="Server (-ivcsw)", color="orange", marker="o")
        # ax_vruntime_server.scatter(throughputs, abs_server_vruntime_vcsw, label="Server (-ivcsw+vcsw)", color="blue", marker="o")
        # ax_vruntime_server.scatter(throughputs, abs_server_vruntime_normed, label="Server (-ivcsw+vcsw, normed)", color="green", marker="o")
        # ax_vruntime_server.set_xlabel("Throughput (IOPS)")
        # ax_vruntime_server.set_ylabel("Absolute vruntime")
        # ax_vruntime_server.legend()
        # # ax_vruntime_server.set_ylim(bottom=6.5e7)
        # fig_vruntime_server.savefig("add_up_abs_vruntime_server_adjusted_vs_throughput.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime_server)

        # # Figure 5-1: x axis: throughput, y axis: client side last vruntime adjusted by client side involuntary context switch
        # fig_vruntime_client = plt.figure(figsize=(6, 6*0.618))
        # ax_vruntime_client = fig_vruntime_client.add_axes([0.2, 0.2, 0.7, 0.7])
        # weight = 10
        # client_vruntime_adjusted = []
        # client_vruntime = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         client_vruntime.append(thread.client_vruntime[-1])
        #         client_vruntime_adjusted.append(thread.client_vruntime[-1] - thread.client_nivcsw * weight)
        #         throughputs.append(thread.thpt)
        # client_vruntime = norm_vruntime(client_vruntime)
        # client_vruntime_adjusted = norm_vruntime(client_vruntime_adjusted)
        # ax_vruntime_client.scatter(throughputs, client_vruntime, label="Client vruntime", color="red", marker="o")
        # ax_vruntime_client.scatter(throughputs, client_vruntime_adjusted, label="Client vruntime (-ivcsw)", color="blue", marker="o")
        # ax_vruntime_client.set_xlabel("Throughput (IOPS)")
        # ax_vruntime_client.set_ylabel("Last vruntime")
        # ax_vruntime_client.legend()
        # fig_vruntime_client.savefig("add_up_vruntime_client_adjusted_vs_throughput.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime_client)

        # # Figure 5-2: x axis: throughput, y axis: client side abs vruntime adjusted by client side involuntary context switch
        # fig_vruntime_client = plt.figure(figsize=(6, 6*0.618))
        # ax_vruntime_client = fig_vruntime_client.add_axes([0.2, 0.2, 0.7, 0.7])
        # weight = 15
        # client_abs_vruntime = []
        # client_abs_vruntime_deflated = []
        # client_abs_vruntime_adjusted = []
        # throughputs = []
        # inflations = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         throughputs.append(thread.thpt)
        #         inflations.append(thread.client_inflation)
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         client_abs_vruntime.append(thread.client_abs_vruntime)
        #         client_abs_vruntime_deflated.append(thread.client_abs_vruntime * min(inflations)/thread.client_inflation)
        #         client_abs_vruntime_adjusted.append(thread.client_abs_vruntime * min(inflations)/thread.client_inflation - thread.client_nivcsw * weight)
        # ax_vruntime_client.scatter(throughputs, client_abs_vruntime, label="Client vruntime", color="red", marker="o")
        # ax_vruntime_client.scatter(throughputs, client_abs_vruntime_deflated, label="Client vruntime (deflated)", color="orange", marker="^")
        # ax_vruntime_client.scatter(throughputs, client_abs_vruntime_adjusted, label="Client vruntime (deflated, -ivcsw)", color="blue", marker="+")
        # min_thpt = min(throughputs)
        # min_inflation = min(inflations)
        # client_abs_vruntime_normed = ([v/thpt*min_thpt for v, thpt in zip(client_abs_vruntime_adjusted, throughputs)])
        # ax_vruntime_client.scatter(throughputs, client_abs_vruntime_normed, label="Client vruntime (deflated -ivcsw, normed)", color="green", marker="s")
        # ax_vruntime_client.set_xlabel("Throughput (IOPS)")
        # ax_vruntime_client.set_ylabel("Absolute vruntime")
        # ax_vruntime_client.legend()
        # # ax_vruntime_client.set_ylim(bottom=6.6e7)
        # fig_vruntime_client.savefig("add_up_abs_vruntime_client_adjusted_vs_throughput_3_15_1_sched.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime_client)

# Figure Unused
        # # Figure 3-1: x axis: nvcsw+nivcsw, y axis: last relative vruntime
        # fig_vruntime_ncsw = plt.figure(figsize=(6, 6*0.618))
        # ax_vruntime_ncsw = fig_vruntime_ncsw.add_axes([0.2, 0.2, 0.7, 0.7])
        # client_ncsw = []
        # server_ncsw = []
        # client_vruntime = []
        # server_vruntime = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         client_ncsw.append(thread.client_nivcsw + thread.client_nvcsw)
        #         server_ncsw.append(thread.server_nivcsw + thread.server_nvcsw)
        #         client_vruntime.append(thread.client_vruntime[-1])
        #         server_vruntime.append(thread.server_vruntime[-1])
        # client_vruntime = norm_vruntime(client_vruntime)
        # server_vruntime = norm_vruntime(server_vruntime)
        # ax_vruntime_ncsw.scatter(client_ncsw, client_vruntime, label="Client vruntime", color="blue", marker="o")
        # ax_vruntime_ncsw.scatter(server_ncsw, server_vruntime, label="Server vruntime", color="red", marker="^")
        # ax_vruntime_ncsw.set_xlabel("Voluntary + Involuntary Context Switches")
        # ax_vruntime_ncsw.set_ylabel("Last vruntime")
        # ax_vruntime_ncsw.legend()
        # fig_vruntime_ncsw.savefig("add_up_vruntime_vs_ncsw.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime_ncsw)