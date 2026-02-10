import os
import re
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
    def __init__(self, port=0, client_pid=0, client_core=0,
                 client_softirq_packets=0, server_pid=0, server_core=0,
                 server_softirq_packets=0, thpt=0, latency=0):
        
        self.port = port
        self.thpt = thpt
        self.latency = latency

        self.client_pid = client_pid
        self.client_core = client_core
        self.client_softirq_packets = client_softirq_packets
        self.client_vruntime = []
        self.client_abs_vruntime = 0
        self.client_cache_ref = 0
        self.client_cache_miss = 0
        self.client_cache_miss_rate = 0

        self.server_pid = server_pid
        self.server_core = server_core
        self.server_softirq_packets = server_softirq_packets
        self.server_vruntime = []
        self.server_abs_vruntime = 0
        self.server_cache_ref = 0
        self.server_cache_miss = 0
        self.server_cache_miss_rate = 0

    def __str__(self):
        return (f"Port: {self.port}, Througput: {self.thpt}, Latency: {self.latency}, "
                f"Client PID: {self.client_pid}, Client Core: {self.client_core}, "
                f"Server PID: {self.server_pid}, Server Core: {self.server_core}, "
                f"Client Abs Vruntime: {self.client_abs_vruntime}, Server Abs Vruntime: {self.server_abs_vruntime}, "
                f"Client Cache Ref: {self.client_cache_ref}, Client Cache Miss: {self.client_cache_miss}, "
                f"Client Cache Miss Rate: {self.client_cache_miss_rate:.4f}, "
                f"Client Softirq Packets: {self.client_softirq_packets}, Server Softirq Packets: {self.server_softirq_packets}")

    def __repr__(self):
        return f"<ThreadData port={self.port} client_pid={self.client_pid} thpt={self.thpt} latency={self.latency}>"


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

    # read the core and pid info, as well as perf info.
    server_log_path = os.path.join(experiment_dir, f"server.log")
    with open(server_log_path, "r") as server_log:
        lines = server_log.readlines()
        for line in lines:
            items = line.split()
            if "core:" in line:
                core, pid, port = int(items[2]), int(items[4]), int(items[7])
                for thread in threads_info:
                    if thread.port == port:
                        thread.server_pid = pid
                        thread.server_core = core
            elif "events:" in line:
                pid = int(items[1])
                cache_ref = int(items[5])
                case_miss = int(items[7])
                for thread in threads_info:
                    if thread.server_pid == pid:
                        thread.server_cache_ref = cache_ref
                        thread.server_cache_miss = case_miss
                        thread.server_cache_miss_rate = case_miss / cache_ref
            else:
                continue

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
            elif "events:" in line:
                pid = int(items[1])
                cache_ref = int(items[5])
                case_miss = int(items[7])
                for thread in threads_info:
                    if thread.client_pid == pid:
                        thread.client_cache_ref = cache_ref
                        thread.client_cache_miss = case_miss
                        thread.client_cache_miss_rate = case_miss / cache_ref
            else:
                continue
    # Sort thread by port number
    threads_info.sort(key=lambda x: x.port)

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
        f"airq_thread_perf_2_1/52_64_1_1_1_1_0_0_1_0",
    ]
    labels = [
        "Linux + cIRQa",
    ]
    markers = ['s', 'P']

    colors = ["firebrick", "forestgreen"]

    n_threads = [52]
    NETFILTER_COUNT = 30

    for index, experiment, n_thread in zip(range(len(experiments)), experiments, n_threads):
        experiment_dir = os.path.join(result_dir, experiment)
        client_vruntime_path = os.path.join(experiment_dir, f"iter_thread_client.log")
        server_vruntime_path = os.path.join(experiment_dir, f"iter_thread_server.log")
        threads_info = parse_all_thread_info(experiment_dir, n_thread)
        threads_info = parse_vruntime(threads_info, client_vruntime_path, server_vruntime_path)
        threads_info = parse_netfilter(threads_info, experiment_dir)
        for thread in threads_info:
            print(thread)

        # draw client_abs_vruntime vs client cache miss count
        plt.figure(figsize=(6, 6*0.618))
        client_abs_vruntimes = [thread.client_abs_vruntime for thread in threads_info if thread.client_core == 96]
        # client_cache_miss_counts = [thread.client_cache_miss for thread in threads_info if thread.client_core == 96]
        # client_cache_ref_counts = [thread.client_cache_ref for thread in threads_info if thread.client_core == 96]
        client_cache_miss_rates = [thread.client_cache_miss_rate for thread in threads_info if thread.client_core == 96]
        plt.scatter(client_cache_miss_rates, client_abs_vruntimes, 
                    color=colors[index], marker=markers[index], s=100, label=labels[index])
        plt.xlabel("Client Cache Miss Rate")
        plt.ylabel("Client Absolute Vruntime Increase")
        plt.grid(True, which="both", linestyle=":", linewidth=1.5)
        plt.legend()
        plt.tight_layout()
        plt.savefig(f"client_cache_miss_rate_vs_vruntime_core96.pdf")
        plt.close()


        # draw latency vs client softirq packets
        # plt.figure(figsize=(6, 6*0.618))
        # client_softirq_packets = [thread.client_softirq_packets for thread in threads_info if thread.client_core == 96]
        # latencies = [thread.latency for thread in threads_info if thread.client_core == 96]
        # plt.scatter(client_softirq_packets, latencies, 
        #             color=colors[index], marker=markers[index], s=100, label=labels[index])
        # plt.xlabel("Client Softirq Packets Processed")
        # plt.ylabel("Latency (us)")
        # plt.grid(True, which="both", linestyle=":", linewidth=1.5)
        # plt.legend()
        # plt.tight_layout()
        # plt.savefig(f"client_softirq_vs_latency_core96.pdf")
        # plt.close()
