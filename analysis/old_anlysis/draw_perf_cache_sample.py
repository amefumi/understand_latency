import os
import re
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
    def __init__(self, port=0, client_pid=0, client_core=0,
                 client_softirq_packets=0, server_pid=0, server_core=0,
                 server_softirq_packets=0, thpt=0, latency=0):
        
        self.port = port
        self.thpt = thpt
        self.latency = latency

        self.client_pid = client_pid
        self.client_core = client_core
        self.client_softirq_packets = client_softirq_packets
        self.client_sched_latency = 0
        self.client_sched_latency_avg = 0
        self.client_perf_sample = 0
        self.client_vruntime = []
        self.client_abs_vruntime = 0

        self.server_pid = server_pid
        self.server_core = server_core
        self.server_softirq_packets = server_softirq_packets
        self.server_sched_latency = 0
        self.server_sched_latency_avg = 0
        self.server_vruntime = []
        self.server_abs_vruntime = 0

    def __str__(self):
        return (f"Port: {self.port}, Througput: {self.thpt}, Latency: {self.latency}, "
                f"Client PID: {self.client_pid}, Client Core: {self.client_core}, "
                f"Client SoftIRQ Packets: {self.client_softirq_packets}, Client Sched Latency: {self.client_sched_latency}, "
                f"Client Perf Sample: {self.client_perf_sample}, "
                f"Server PID: {self.server_pid}, Server Core: {self.server_core}, "
                f"Server SoftIRQ Packets: {self.server_softirq_packets}, Server Sched Latency: {self.server_sched_latency}), "
                f"Client Abs Vruntime: {self.client_abs_vruntime}, Server Abs Vruntime: {self.server_abs_vruntime}")

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
    client_log_path = os.path.join(experiment_dir, f"filter_client.log")
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

    server_log_path = os.path.join(experiment_dir, f"filter_server.log")
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


def parse_perf_sample(threads_info, experiment_dir):
    client_perf_path = os.path.join(experiment_dir, f"perf_sample_client.txt")
    with open(client_perf_path, "r") as log:
        lines = log.readlines()
        for line in lines:
            items = line.split()
            pid, sample = int(items[0]), int(items[1])
            for thread in threads_info:
                if thread.client_pid == pid:
                    thread.client_perf_sample = sample

    return threads_info


if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"
    experiments = [       
        "airq_kneepoint_random_1_1/52_64_1_1_1_1_0_0_1_5",
        # f"airq_pktirq_1_1/48_64_1_1_1_1_0_0_1_{run}",
    ]
    labels = [
        "Linux",
        "Linux + cIRQa",
    ]
    markers = ['s', 'P']

    colors = ["firebrick", "forestgreen"]

    n_threads = [52]
    NETFILTER_COUNT = 30

    # Initialize figure and axis
    ax_height = 2.5 # NOTE: we basically need to make sure all latency-throughput curve figures have the same size
    ax_width = 2.5/0.618 # Golden ratio
    fig_height = 20
    fig_width = 20
    ax_width_frac = ax_width / fig_width
    ax_height_frac = ax_height / fig_height

    # fig_latency_client = plt.figure(figsize=(fig_width, fig_height))
    # fig_latency_server = plt.figure(figsize=(fig_width, fig_height))
    # throughput_fig = plt.figure(figsize=(fig_width, fig_height))

    # ax_latency_client = fig_latency_client.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])
    # ax_latency_server = fig_latency_server.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])
    # ax_throughput = throughput_fig.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])

    for index, experiment, n_thread in zip(range(len(experiments)), experiments, n_threads):
        experiment_dir = os.path.join(result_dir, experiment)
        threads_info = parse_all_thread_info(experiment_dir, n_thread)
        threads_info = parse_perf_sample(threads_info, experiment_dir)
        client_vruntime_path = os.path.join(experiment_dir, f"iter_thread_client.log")
        server_vruntime_path = os.path.join(experiment_dir, f"iter_thread_server.log")
        threads_info = parse_vruntime(threads_info, client_vruntime_path, server_vruntime_path)

        for thread in threads_info:
            print(thread)
        # plot client scheduling latency vs perf samples
        client_sched_latencies = [thread.client_sched_latency/1e3 for thread in threads_info if thread.client_core == 32]
        # client_abs_vruntimes = [thread.client_abs_vruntime for thread in threads_info if thread.client_core == 32]
        # last_vruntime = [thread.client_vruntime[-1] for thread in threads_info if thread.client_core == 32]
        client_perf_samples = [thread.client_perf_sample for thread in threads_info if thread.client_core == 32]
        client_id = [thread.port - 10000 for thread in threads_info if thread.client_core == 32]
        plt.scatter(client_perf_samples, client_sched_latencies, label=f"{labels[index]}", marker=markers[index], color=colors[index], s=50)
        for i, txt in enumerate(client_id):
            plt.annotate(txt, (client_perf_samples[i], client_sched_latencies[i]), textcoords="offset points", xytext=(0,10), ha='center', fontsize=10)
        plt.xlabel("Cache miss samples")
        plt.ylabel("P99.9 rx_sched Latency (ms)")
        plt.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=2)
        plt.savefig(f"rx_sched_vs_cache_miss_sample_{n_thread}.pdf", bbox_inches='tight')
        plt.close()

        # plot client scheduling latency vs packet in softirq packets
        # server_sched_latencies = [thread.server_sched_latency/1e3 for thread in threads_info]
        # client_sched_latencies = [thread.client_sched_latency/1e3 for thread in threads_info]
        # throughputs = [thread.thpt/1e3 for thread in threads_info]
        # server_softirq_packets = [thread.server_softirq_packets/1e6 for thread in threads_info]
        # client_softirq_packets = [thread.client_softirq_packets/1e6 for thread in threads_info]
        # ax_latency_client.scatter(client_softirq_packets, client_sched_latencies, label=f"{labels[index]}", marker=markers[index], color=colors[index], s=50)
        # ax_latency_server.scatter(server_softirq_packets, server_sched_latencies, label=f"{labels[index]}", marker=markers[index], color=colors[index], s=50)
        # ax_throughput.scatter(server_softirq_packets, throughputs, label=f"{labels[index]}", marker=markers[index], color=colors[index], s=50)

    
    # ax_latency_client.set_xlabel("# million of packets in softIRQ processing")
    # ax_latency_client.set_ylabel("P99.9 rx_sched Latency (us)")
    # ax_latency_client.legend(loc='upper left', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
    # ax_latency_client.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=2)
    # fig_latency_client.savefig(f"sched_latency_vs_softirq_packets_client_{run}.pdf", bbox_inches='tight')

    # ax_latency_server.set_xlabel("# million of packets in softIRQ processing")
    # ax_latency_server.set_ylabel("P99.9 tx_sched Latency (us)")
    # ax_latency_server.legend(loc='upper left', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
    # ax_latency_server.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=2)
    # fig_latency_server.savefig(f"sched_latency_vs_softirq_packets_server_{run}.pdf", bbox_inches='tight')

    # ax_throughput.set_xlabel("# million of packets in softIRQ processing")
    # ax_throughput.set_ylabel("Throughput (kIOPS)")
    # ax_throughput.legend(loc='upper right', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
    # ax_throughput.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=2)
    # throughput_fig.savefig("throughput_vs_softirq_packets_server.pdf", bbox_inches='tight')

    # TODO: also consider the virtual runtime vs rx_sched latency?