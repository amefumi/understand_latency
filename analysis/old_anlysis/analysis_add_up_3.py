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

    def __str__(self):
        return (f"---port: {self.port}, thpt: {self.thpt}, lat: {self.latency}, pkts: {self.packets}, "
                f"| Client: pid-{self.client_pid}, cpu-{self.client_core}, "
                f"#pkts-{self.client_softirq_packets}, sched_lat-{self.client_sched_latency}, "
                f"nvcsw-{self.client_nvcsw}, nivcsw={self.client_nivcsw}, abs_vrun-{self.client_abs_vruntime}, "
                f"| Server: pid-{self.server_pid}, cpu-{self.server_core}, "
                f"#pkts-{self.server_softirq_packets}, sched_lat-{self.server_sched_latency}), "
                f"nvcsw-{self.server_nvcsw}, nivcsw={self.server_nivcsw}, abs_vrun-{self.server_abs_vruntime}")

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

    # # read client inflation info
    # client_inflation_path = os.path.join(experiment_dir, f"breakdown_sum_p90_client.txt")
    # with open(client_inflation_path, "r") as client_inflation_log:
    #     lines = client_inflation_log.readlines()
    #     for line in lines[1:]:
    #         items = line.split()
    #         # port, rx_data_copy_90th = int(items[0]), float(items[5])
    #         port, len_800, len_1000 = int(items[0]), float(items[3]), float(items[4])
    #         for thread in threads_info:
    #             if thread.port == port:
    #                 # thread.client_inflation = rx_data_copy_90th
    #                 # thread.client_inflation = len_800
    #                 thread.client_inflation = len_1000

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
                    thread.server_nivcsw = nivcsw * (300/297)
                    thread.server_nvcsw = nvcsw * (300/297)

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


if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"
    experiments = [       
        # "airq_add_up_3_1/52_64_1_1_1_1_0_0_1_2",
        # "airq_sched_accounting_1_1/52_64_1_1_1_1_0_0_1_1"
        # "sirq_breakdown_5_2/52_64_1_2_1_1_0_0_1_0",
        # "sirq_breakdown_1_1/52_64_1_1_1_1_0_0_1_3",
        # "airq_run_to_complete_1_1/64_64_1_1_1_1_0_0_1_0",
        # "airq_run_to_complete_1_1/64_64_1_2_1_1_0_0_1_0"
        "nh_airq_half_1_1/26_64_1_1_1_2_0_0_1_2",
    ]

    n_threads = [26]
    NETFILTER_COUNT = 30


    # fig_latency_client = plt.figure(figsize=(fig_width, fig_height))
    # fig_latency_server = plt.figure(figsize=(fig_width, fig_height))
    # throughput_fig = plt.figure(figsize=(fig_width, fig_height))

    # ax_latency_client = fig_latency_client.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])
    # ax_latency_server = fig_latency_server.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])
    # ax_throughput = throughput_fig.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])

    for index, experiment, n_thread in zip(range(len(experiments)), experiments, n_threads):
        experiment_dir = os.path.join(result_dir, experiment)
        threads_info = parse_all_thread_info(experiment_dir, n_thread)
        # threads_info = parse_netfilter(threads_info, experiment_dir)
        for thread in threads_info:
            print(thread)

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


        # ----------------For some linear regression analysis----------------

        # # # norm inflation
        # norm_inflation = []
        # pakcets = []
        # for thread in threads_info:
        #     if thread.client_core == 32:
        #         norm_inflation.append(thread.client_inflation)
        #         pakcets.append(thread.packets)
        # # min_infaltion = min(norm_inflation)
        # # norm_inflation = [infl / min_infaltion for infl in norm_inflation]

        # norm_inflation = norm_vruntime(norm_inflation, 0)
        # norm_inflation = [infl * pkts/86 for infl, pkts in zip(norm_inflation, pakcets)]


        # print("Normalized Inflation Values for Client Core 32:", norm_inflation)
        # # # print("Inflation * Packets for Client Core 32:", inflation)


        # Analysis for sched-accounting case
        # pick the threads (on core 32 or 96) with the lowest involuntary context switches, calculate the absolute vruntime divided by throughput
        # min_abs_vruntime_thread = None
        # min_abs_vruntime = float('inf')
        # for thread in threads_info:
        #     if thread.client_core == 32:
        #         if thread.client_abs_vruntime < min_abs_vruntime:
        #             min_abs_vruntime = thread.client_abs_vruntime
        #             min_abs_vruntime_thread = thread
        # if min_abs_vruntime_thread is not None:
        #     ratio = min_abs_vruntime_thread.client_abs_vruntime / min_abs_vruntime_thread.thpt
        #     print(f"Min client abs vruntime thread: Port {min_abs_vruntime_thread.port}, Core {min_abs_vruntime_thread.client_core}, Abs Vruntime {min_abs_vruntime_thread.client_abs_vruntime}, NIVCSW {min_abs_vruntime_thread.client_nivcsw}, Throughput {min_abs_vruntime_thread.thpt}, Ratio {ratio}")        

        # for thread in threads_info:
        #     if thread.client_core == 32:
        #         thread.client_abs_vruntime = thread.client_abs_vruntime - thread.thpt * ratio
        #         print(f"Port {thread.port}, Core {thread.client_core}, NIVCSW {thread.client_nivcsw}, Abs Vruntime {thread.client_abs_vruntime}, Throughput {thread.thpt}, Adjusted Abs Vruntime {thread.client_abs_vruntime}, Adjusted Ratio {thread.client_abs_vruntime/thread.thpt}")


        # index = 0
        # for thread in threads_info:
        #     if thread.client_core == 32:
        #         thread.client_abs_vruntime -= norm_inflation[index]
        #         index += 1

        # for i in range(len(adjusted_abs_vruntime)):
        #     adjusted_abs_vruntime[i] = adjusted_abs_vruntime[i] - norm_inflation[i]
        #     # adjusted_abs_vruntime[i] = adjusted_abs_vruntime[i] #  / norm_inflation[i]
        #     adjusted_abs_vruntime[i] = adjusted_abs_vruntime[i] - thread_thpt[i] * ratio
        #     print(adjusted_abs_vruntime[i]/thread_thpt[i])

        # thread_thpt = []
        # thread_involuntary = []
        # adjusted_abs_vruntime = []
        # for thread in threads_info:
        #     if thread.client_core == 32:
        #         thread_thpt.append(thread.thpt)
        #         thread_involuntary.append(thread.client_nivcsw)
        #         adjusted_abs_vruntime.append(thread.client_abs_vruntime)

        # # draw the adjusted absolute vruntime vs involuntary context switches
        # fig_adjusted = plt.figure(figsize=(6, 6*0.618))
        # ax_adjusted = fig_adjusted.add_axes([0.2, 0.2, 0.7, 0.7])
        # # ax_adjusted.scatter(thread_thpt, adjusted_abs_vruntime, label="Adjusted Abs Vruntime", color="blue", marker="o")
        # ax_adjusted.scatter(adjusted_abs_vruntime, thread_involuntary, label="Adjusted Abs Vruntime", color="blue", marker="o")
        # ax_adjusted.set_xlabel("Involuntary Context Switches")
        # ax_adjusted.set_ylabel("Adjusted Absolute Vruntime")
        # ax_adjusted.legend()
        # fig_adjusted.savefig("sched_accounting_client_adjusted_abs_vruntime_vs_nivcsw.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_adjusted)


        # # Linear regression analysis
        # # We assume abs_vruntme = k * throughput + m * nivcsw, where k and m are constants to be determined
        # from sklearn.linear_model import LinearRegression
        # import numpy as np
        # X_client = []
        # X_server = []
        # Y_client = []
        # Y_server = []
        # for thread in threads_info:
        #     if thread.client_core == 32:
        #         X_client.append([thread.thpt*300,]) # thread.client_nvcsw])
        #         Y_client.append(thread.client_abs_vruntime)
        # for i, val in enumerate(X_client):
        #     val.append(norm_inflation[i])

        # X_client = np.array(X_client)
        # Y_client = np.array(Y_client)
        # # intercept = 0
        # model_client = LinearRegression(fit_intercept=False)
        # model_server = LinearRegression(fit_intercept=False)
        # model_client.fit(X_client, Y_client)
        # print("Client Linear Regression Coefficients:")
        # print(f"  Intercept: {model_client.intercept_}")
        # print(f"  Coefficients: {model_client.coef_}")
        # # print r^2
        # Y_pred_client = model_client.predict(X_client)
        # print(Y_pred_client, Y_client)
        # r2_client = model_client.score(X_client, Y_client)
        # print(f"  R^2: {r2_client}")
        # print([k-kk for k, kk in zip(Y_client, Y_pred_client)])

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