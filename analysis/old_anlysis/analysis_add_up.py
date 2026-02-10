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

def norm_vruntime(vruntime_line):
    if len(vruntime_line) == 0:
        return []
    min_vruntime = min(vruntime_line)
    normed = []
    for v in vruntime_line:
        normed.append(v - min_vruntime + 1)
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
            else:
                continue

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
                line_index += 4
            else:
                line_index += 1

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


if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"
    experiments = [       
        # "airq_add_up_1_1/52_64_1_1_1_1_0_0_1_2",
        # "airq_sched_accounting_1_1/48_64_1_1_1_1_0_0_1_2"
        # "sirq_breakdown_2_1/48_64_1_1_1_1_0_0_1_2",
        # "sirq_breakdown_4_2/48_64_1_1_1_1_0_0_1_2",
        # "sirq_breakdown_2_1/52_64_1_1_1_1_0_0_1_2",
        "nh_sirq_half_1_1/26_64_1_1_1_2_0_0_1_2",
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
        threads_info = parse_netfilter(threads_info, experiment_dir)
        threads_info = parse_vruntime(threads_info, experiment_dir)
        for thread in threads_info:
            print(thread)

        # # Figure 0: x axis: involuntary context switches, y axis: rx_sched latency P99.9
        fig_sched = plt.figure(figsize=(6, 6*0.618))
        ax_sched = fig_sched.add_axes([0.2, 0.2, 0.7, 0.7])
        client_nivcsw = []
        server_nivcsw = []
        client_sched_latencies = []
        server_sched_latencies = []
        for thread in threads_info:
            if thread.client_core == 32:
                client_nivcsw.append(thread.client_nivcsw/1e6)
                server_nivcsw.append(thread.server_nivcsw/1e6)
                client_sched_latencies.append(thread.client_sched_latency/1e3)
                server_sched_latencies.append(thread.server_sched_latency/1e3)
        ax_sched.scatter(client_nivcsw, client_sched_latencies, label="Client", color="blue", marker="o")
        ax_sched.scatter(server_nivcsw, server_sched_latencies, label="Server", color="red", marker="^")
        ax_sched.set_xlabel("Millions of Involuntary Context Switches")
        ax_sched.set_ylabel("P99.9 rx_sched (us)")
        ax_sched.legend()
        fig_sched.savefig("nh_sched_vs_nivcsw_SCHEDa.pdf", dpi=300, bbox_inches='tight')
        plt.close(fig_sched)


        # # Figure 0-1: x axis: server-side last vruntime. y axis: client-side last vruntime
        # fig_vruntime = plt.figure(figsize=(6, 6*0.618))
        # ax_vruntime = fig_vruntime.add_axes([0.2, 0.2, 0.7, 0.7])
        # client_vruntimes = []
        # server_vruntimes = []
        # for thread in threads_info:
        #     if thread.client_core == 32:
        #         client_vruntimes.append(int(thread.client_vruntime[-1]))
        #         server_vruntimes.append(int(thread.server_vruntime[-1]))
        # client_vruntimes = norm_vruntime(client_vruntimes)
        # server_vruntimes = norm_vruntime(server_vruntimes)
        # ax_vruntime.scatter(server_vruntimes, client_vruntimes, label="Client vs Server vruntime", color="blue", marker="o")
        # ax_vruntime.set_xlabel("Server Last vruntime")
        # ax_vruntime.set_ylabel("Client Last vruntime")
        # ax_vruntime.legend()
        # fig_vruntime.savefig("scheda_middle_add_up_last_vruntime_server_vs_client32.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime)


        # # Figure 1-1: x axis: throughput, y axis: last virtual runtime
        # fig_vruntime = plt.figure(figsize=(6, 6*0.618))
        # ax_vruntime = fig_vruntime.add_axes([0.2, 0.2, 0.7, 0.7])
        # client_vruntimes = []
        # server_vruntimes = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 32:
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
        # fig_vruntime.savefig("scheda_good_add_up_last_vruntime_vs_throughput32.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime)

        # # Figure 1-2: x axis: throughput, y axis: last virtual runtime
        # fig_vruntime = plt.figure(figsize=(6, 6*0.618))
        # ax_vruntime = fig_vruntime.add_axes([0.2, 0.2, 0.7, 0.7])
        # abs_client_vruntimes = []
        # abs_server_vruntimes = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 32:
        #         abs_client_vruntimes.append(int(thread.client_abs_vruntime))
        #         abs_server_vruntimes.append(int(thread.server_abs_vruntime))
        #         throughputs.append(thread.thpt)
        # ax_vruntime.scatter(throughputs, abs_client_vruntimes, label="Client vruntime", color="blue", marker="o")
        # ax_vruntime.scatter(throughputs, abs_server_vruntimes, label="Server vruntime", color="red", marker="^")
        # ax_vruntime.set_xlabel("Throughput (IOPS)")
        # ax_vruntime.set_ylabel("Absolute vruntime")
        # ax_vruntime.legend()
        # fig_vruntime.savefig("scheda_good_add_up_abs_vruntime_vs_throughput32.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime)

        # # Figure 2-1: x axis: throughput, y axis: voluntary context switch, total packets
        # fig_nvcsw = plt.figure(figsize=(6, 6*0.618))
        # ax_nvcsw = fig_nvcsw.add_axes([0.2, 0.2, 0.7, 0.7])
        # client_nvcsw = []
        # server_nvcsw = []
        # packets = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 32:
        #         throughputs.append(thread.thpt)
        #         packets.append(thread.packets)
        #         client_nvcsw.append(thread.client_nvcsw)
        #         server_nvcsw.append(thread.server_nvcsw)
        # ax_nvcsw.scatter(throughputs, client_nvcsw, label="Client Voluntary", color="blue", marker="+")
        # ax_nvcsw.scatter(throughputs, server_nvcsw, label="Server Voluntary", color="red", marker="o")
        # ax_nvcsw.scatter(throughputs, packets, label="Total Packets", color="green", marker="s")
        # ax_nvcsw.set_xlabel("Throughput (IOPS)")
        # ax_nvcsw.set_ylabel("Switches / Packets")
        # ax_nvcsw.legend()
        # fig_nvcsw.savefig("scheda_good_add_up_nvcsw_packets_vs_throughput32.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_nvcsw)

        # # Figure 2-2: x axis: throughput, y axis: involuntary context switch, total packets
        # fig_nvcsw = plt.figure(figsize=(6, 6*0.618))
        # ax_nvcsw = fig_nvcsw.add_axes([0.2, 0.2, 0.7, 0.7])
        # client_nivcsw = []
        # server_nivcsw = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 32:
        #         throughputs.append(thread.thpt)
        #         client_nivcsw.append(thread.client_nivcsw)
        #         server_nivcsw.append(thread.server_nivcsw)
        # ax_nvcsw.scatter(throughputs, client_nivcsw, label="Client Involuntary", color="blue", marker="+")
        # ax_nvcsw.scatter(throughputs, server_nivcsw, label="Server Involuntary", color="red", marker="o")
        # ax_nvcsw.set_xlabel("Throughput (IOPS)")
        # ax_nvcsw.set_ylabel("Switches")
        # ax_nvcsw.legend()
        # fig_nvcsw.savefig("scheda_good_add_up_nivcsw_vs_throughput32.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_nvcsw)

        # # Figure 2-3: x axis: throughput, y axis: voluntary context switch + involuntary context switch
        # fig_nvcsw = plt.figure(figsize=(6, 6*0.618))
        # ax_nvcsw = fig_nvcsw.add_axes([0.2, 0.2, 0.7, 0.7])
        # client_ncsw = []
        # server_ncsw = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 32:
        #         throughputs.append(thread.thpt)
        #         client_ncsw.append(thread.client_nivcsw + thread.client_nvcsw)
        #         server_ncsw.append(thread.server_nivcsw + thread.server_nvcsw)
        # ax_nvcsw.scatter(throughputs, client_ncsw, label="Client", color="blue", marker="+")
        # ax_nvcsw.scatter(throughputs, server_ncsw, label="Server", color="red", marker="o")
        # ax_nvcsw.set_xlabel("Throughput (IOPS)")
        # ax_nvcsw.set_ylabel("Switches")
        # ax_nvcsw.legend()
        # fig_nvcsw.savefig("scheda_good_add_up_ncsw_vs_throughput32.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_nvcsw)

        # # [Unused] Figure 2-4: x axis: throughput, y axis: involuntary context switch (server + client)
        # fig_nivcsw = plt.figure(figsize=(6, 6*0.618))
        # ax_nivcsw = fig_nivcsw.add_axes([0.2, 0.2, 0.7, 0.7])
        # total_nivcsw = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         throughputs.append(thread.thpt)
        #         total_nivcsw.append(thread.client_nivcsw + thread.server_nivcsw)
        # ax_nivcsw.scatter(throughputs, total_nivcsw, label="Client + Server", color="blue", marker="o")
        # ax_nivcsw.set_xlabel("Throughput (IOPS)")
        # ax_nivcsw.set_ylabel("Involuntary Context Switches")
        # ax_nivcsw.legend()
        # fig_nivcsw.savefig("add_up_total_nivcsw_vs_throughput.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_nivcsw)

        # # [Unused]Figure 2-5: x axis: throughput, y axis: total context switch (server + client)
        # fig_ncsw = plt.figure(figsize=(6, 6*0.618))
        # ax_ncsw = fig_ncsw.add_axes([0.2, 0.2, 0.7, 0.7])
        # total_ncsw = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         throughputs.append(thread.thpt)
        #         total_ncsw.append(thread.client_nivcsw + thread.client_nvcsw + thread.server_nivcsw + thread.server_nvcsw)
        # ax_ncsw.scatter(throughputs, total_ncsw, label="Client + Server", color="blue", marker="o")
        # ax_ncsw.set_xlabel("Throughput (IOPS)")
        # ax_ncsw.set_ylabel("Total Context Switches")
        # ax_ncsw.legend()
        # fig_ncsw.savefig("add_up_total_ncsw_vs_throughput.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_ncsw)

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
        # weight = 10
        # client_abs_vruntime_adjusted = []
        # client_abs_vruntime = []
        # throughputs = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         client_abs_vruntime_adjusted.append(thread.client_abs_vruntime - thread.client_nivcsw * weight)
        #         client_abs_vruntime.append(thread.client_abs_vruntime)
        #         throughputs.append(thread.thpt)
        # ax_vruntime_client.scatter(throughputs, client_abs_vruntime, label="Client vruntime", color="red", marker="o")
        # ax_vruntime_client.scatter(throughputs, client_abs_vruntime_adjusted, label="Client vruntime (-ivcsw)", color="blue", marker="o")
        # min_thpt = min(throughputs)
        # client_abs_vruntime_normed = ([v/thpt*min_thpt for v, thpt in zip(client_abs_vruntime_adjusted, throughputs)])
        # ax_vruntime_client.scatter(throughputs, client_abs_vruntime_normed, label="Client vruntime (-ivcsw, normed)", color="green", marker="s")
        # ax_vruntime_client.set_xlabel("Throughput (IOPS)")
        # ax_vruntime_client.set_ylabel("Absolute vruntime")
        # ax_vruntime_client.legend()
        # ax_vruntime_client.set_ylim(bottom=6.6e7)
        # fig_vruntime_client.savefig("add_up_abs_vruntime_client_adjusted_vs_throughput.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime_client)


        # # Linear regression analysis
        # # We assume abs_vruntme = a1 * throughput + a2 * nivcsw + a3 * (nivcsw + nvcsw), where a1, a2, a3 are positive constants
        # from sklearn.linear_model import LinearRegression
        # import numpy as np
        # X_client = []
        # Y_client = []
        # for thread in threads_info:
        #     if thread.client_core == 96:
        #         X_client.append([thread.client_nivcsw])
        #         Y_client.append(thread.client_abs_vruntime - thread.thpt * 8653.14)
        # print("Client Linear Regression Data X:", np.array(X_client))
        # print("Client Linear Regression Data Y:", np.array(Y_client))
        # # set linear regression model intercept to zero
        # model_client = LinearRegression()
        # model_client.fit(X_client, Y_client)
        # print("Client Linear Regression Coefficients:", model_client.coef_)
        # print("Client Linear Regression Intercept:", model_client.intercept_)
        # # r^2 score
        # r2_client = model_client.score(X_client, Y_client)
        # print("Client Linear Regression R^2 Score:", r2_client)

        # # draw Y_client vs X_client
        # fig_client_lr = plt.figure(figsize=(6, 6*0.618))
        # ax_client_lr = fig_client_lr.add_axes([0.2, 0.2, 0.7, 0.7])
        # ax_client_lr.scatter(X_client, Y_client, label="Client Data Points", color="blue", marker="o")
        # # draw regression line
        # X_client_range = np.array([[min(X_client)[0]], [max(X_client)[0]]])
        # Y_client_range = model_client.predict(X_client_range)
        # ax_client_lr.plot(X_client_range, Y_client_range, label="Client Regression Line", color="red")
        # ax_client_lr.set_xlabel("Involuntary Context Switches")
        # ax_client_lr.set_ylabel("Absolute vruntime - Throughput Component")
        # ax_client_lr.legend()
        # fig_client_lr.savefig("client_linear_regression_nvcsw_vs_vruntime.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_client_lr)

        # # draw scatter plot of actual vs predicted
        # Y_client_pred = model_client.predict(X_client)
        # fig_client_lr = plt.figure(figsize=(6, 6*0.618))
        # ax_client_lr = fig_client_lr.add_axes([0.2, 0.2, 0.7, 0.7])
        # ax_client_lr.scatter(Y_client, Y_client_pred, label="Client Actual vs Predicted", color="blue", marker="o")
        # ax_client_lr.set_xlabel("Actual Absolute vruntime - Throughput Component")
        # ax_client_lr.set_ylabel("Predicted Absolute vruntime - Throughput Component")
        # ax_client_lr.legend()
        # fig_client_lr.savefig("client_linear_regression_actual_vs_predicted.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_client_lr)

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