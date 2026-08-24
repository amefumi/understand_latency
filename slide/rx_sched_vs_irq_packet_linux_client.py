import os
import re
import matplotlib as mpl
import numpy as np
from matplotlib import transforms
from matplotlib.markers import MarkerStyle
from matplotlib.patches import FancyBboxPatch
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import matplotlib.patheffects as path_effects
from matplotlib.ticker import MultipleLocator, LogLocator, LogFormatter

# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Liberation Sans", "Nimbus Sans", "Helvetica", "DejaVu Sans"],
    "font.size": 12,

    # lines and markers
    "lines.linewidth": 2,
    "lines.solid_capstyle": "round",
    "lines.solid_joinstyle": "round",

    # thick frame and ticks

    "xtick.labelsize": 12,
    "xtick.major.width": 2,
    "xtick.major.size": 6,
    "xtick.major.pad": 10,
    "xtick.minor.width": 2,
    "xtick.minor.size": 3,
    "xtick.direction": "in",

    "ytick.labelsize": 12,
    "ytick.major.width": 2,
    "ytick.major.size": 6,
    "ytick.major.pad": 6,
    "ytick.minor.width": 1,
    "ytick.minor.size": 3,
    "ytick.direction": "in",

    # grid
    "grid.linestyle": ":",
    "grid.linewidth": 2,
    "grid.color": "black",
    "grid.alpha": 1,

    # axes
    "axes.labelsize": 12,
    "axes.linewidth": 2,
    "axes.axisbelow": True,
    "axes.labelweight": 600,

    # legend
    "legend.fontsize": 12,

})

pad_left   = 0.9
pad_right  = 0.3
pad_bottom = 0.7
pad_top    = 0.25

# ---------- style (latency-throughput curve) ----------

# colors = ["#85201a", "#ef8733", "#5360c9", "#739739"]
colors = ["#85201a", "#5360c9", "#739739"]
# colors = ["#8e2c14", "#e25953", "#7b3bf1", "#739739"]
# markers = ["x", "s", "^", "+"]
markers = [
    "x", "h", "+"
]
# markers_size = [6, 6, 6, 8]
markers_size = [6, 6, 8]
markers_width = [2, 2, 2, 2]
marker_facecolor = ["none", "none", "none", "none"]
# zorder = [2, 1, 3, 4]
zorder = [3, 2, 4]

result_dir = "/data0/projects/latency/"
experiments = [       
    "nirq_pktirq_vruntime_1_1/48_64_1_1_1_1_0_0_1_5",
    "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_4",
    # "sirq_pcbs_pktirq_1_1/48_64_1_1_1_1_0_0_1_4",
]

labels = [
    "Linux",
    "Linux + ACCa",
    # "Linux + PCSched",
]

n_threads = [48, 48, 48]
NETFILTER_COUNT = 30



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

        self.server_pid = server_pid
        self.server_core = server_core
        self.server_softirq_packets = server_softirq_packets
        self.server_sched_latency = 0
        self.server_sched_latency_avg = 0

    def __str__(self):
        return (f"Port: {self.port}, Througput: {self.thpt}, Latency: {self.latency}, "
                f"Client PID: {self.client_pid}, Client Core: {self.client_core}, "
                f"Client SoftIRQ Packets: {self.client_softirq_packets}, Client Sched Latency: {self.client_sched_latency}, "
                f"Client Perf Sample: {self.client_perf_sample}, "
                f"Server PID: {self.server_pid}, Server Core: {self.server_core}, "
                f"Server SoftIRQ Packets: {self.server_softirq_packets}, Server Sched Latency: {self.server_sched_latency})")

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
    ax_height = 2
    ax_width = 2/0.618
    fig_width = 20
    fig_height = 20

    max_latency = 4000
    max_packets = 6

    fig_latency_client = plt.figure(figsize=(fig_width, fig_height))
    fig_latency_server = plt.figure(figsize=(fig_width, fig_height))
    # throughput_fig_client = plt.figure(figsize=(fig_width, fig_height))
    # throughput_fig_server = plt.figure(figsize=(fig_width, fig_height))

    ax_width_frac = ax_width / fig_width
    ax_height_frac = ax_height / fig_height

    ax_latency_client = fig_latency_client.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])
    ax_latency_server = fig_latency_server.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])

    # ax_throughput_client = throughput_fig_client.add_axes([0, 0, 1, 1])
    # ax_throughput_server = throughput_fig_server.add_axes([0, 0, 1, 1])

    for spine in ax_latency_client.spines.values():
        spine.set_visible(False)
    for spine in ax_latency_server.spines.values():
        spine.set_visible(False)

    bbox = FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.0,rounding_size=0.001",
        transform=ax_latency_client.transAxes,
        linewidth=2,
        edgecolor="black",
        facecolor="none",
        zorder=1,
        clip_on=False,
    )
    ax_latency_client.add_patch(bbox)
        
    bbox_server = FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.0,rounding_size=0.001",
        transform=ax_latency_server.transAxes,
        linewidth=2,
        edgecolor="black",
        facecolor="none",
        zorder=1,
        clip_on=False,
    )
    ax_latency_server.add_patch(bbox_server)


    for index, experiment, n_thread in zip(range(len(experiments)), experiments, n_threads):
        experiment_dir = os.path.join(result_dir, experiment)
        threads_info = parse_all_thread_info(experiment_dir, n_thread)
        threads_info = parse_netfilter(threads_info, experiment_dir)

        for thread in threads_info:
            print(thread)

        # plot client scheduling latency vs packet in softirq packets

        core_interested = 32
        server_sched_latencies = [thread.server_sched_latency/1e3 for thread in threads_info if thread.client_core == core_interested]
        client_sched_latencies = [thread.client_sched_latency/1e3 for thread in threads_info if thread.client_core == core_interested]
        throughputs = [thread.thpt/1e3 for thread in threads_info]
        server_softirq_packets = [thread.server_softirq_packets/1e6 for thread in threads_info if thread.client_core == core_interested]
        client_softirq_packets = [thread.client_softirq_packets/1e6 for thread in threads_info if thread.client_core == core_interested]
        ax_latency_client.scatter(client_softirq_packets, client_sched_latencies, label=f"{labels[index]}", marker=markers[index], color=colors[index], s=50, zorder=zorder[index])
        # print(client_softirq_packets, client_sched_latencies)
        for packet in client_softirq_packets:
            print(packet)
        print("---")

        for latency in client_sched_latencies:
            print(latency)
        ax_latency_server.scatter(server_softirq_packets, server_sched_latencies, label=f"{labels[index]}", marker=markers[index], color=colors[index], s=50, zorder=zorder[index])
        # ax_throughput_client.scatter(client_softirq_packets, throughputs, label=f"{labels[index]}", marker=markers[index], color=colors[index], s=50)
        # ax_throughput_server.scatter(server_softirq_packets, throughputs, label=f"{labels[index]}", marker=markers[index], color=colors[index], s=50)
    
    ax_latency_client.set_xlabel("# million of packets in softIRQ processing", labelpad=8)
    ax_latency_client.set_ylabel("P99.9 rx_sched (us)", labelpad=8)
    ax_latency_client.legend(loc='upper left', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
    # ax_latency_client.legend(loc='upper left', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
    ax_latency_client.grid(
        True,
        which="major",
        linestyle=(0, (0, 2)),
        linewidth=2,
        color="black",
        dash_capstyle="round",
        alpha=1.0,
        zorder=1,
    )
    ax_latency_client.set_xlim(-0.2, max_packets)
    ax_latency_client.set_ylim(-200, max_latency)
    ax_latency_client.set_yticks(range(0, max_latency+500, 1000))
    xticks = ax_latency_client.xaxis.get_major_ticks()
    xticks[0].tick1line.set_markersize(0)
    xticks[0].tick2line.set_markersize(0)
    xticks[-1].tick1line.set_markersize(0)
    xticks[-1].tick2line.set_markersize(0)
    yticks = ax_latency_client.yaxis.get_major_ticks()
    yticks[0].tick1line.set_markersize(0)
    yticks[0].tick2line.set_markersize(0)
    yticks[-1].tick1line.set_markersize(0)
    yticks[-1].tick2line.set_markersize(0)

    ax_latency_client.tick_params(which="both", top=True, right=True)
    pos = ax_latency_client.get_position()
    fig_w, fig_h = fig_latency_client.get_size_inches()
    x0 = fig_w * pos.x0
    y0 = fig_h * pos.y0
    x1 = fig_w * pos.x1
    y1 = fig_h * pos.y1
    bbox = transforms.Bbox.from_extents(
        x0 - pad_left,
        y0 - pad_bottom,
        x1 + pad_right,
        y1 + pad_top,
    )
    # bbox_inches = bbox.transformed(fig_latency_client.dpi_scale_trans.inverted())

    fig_latency_client.savefig("/home/ame/latency/slide/results/rx_sched_vs_softirq_packet_client.pdf", bbox_inches=bbox)

    ax_latency_server.set_xlabel("# million of packets in softIRQ processing", labelpad=8)
    ax_latency_server.set_ylabel("P99.9 rx_sched (us)", labelpad=8)
    ax_latency_server.legend(loc='upper left', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
    # ax_latency_server.legend(loc='upper left', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
    ax_latency_server.grid(
        True,
        which="major",
        linestyle=(0, (0, 2)),
        linewidth=2,
        color="black",
        dash_capstyle="round",
        alpha=1.0,
        zorder=1,
    )
    ax_latency_server.set_xlim(-0.2, max_packets)
    ax_latency_server.set_ylim(-400, max_latency)
    ax_latency_server.set_yticks(range(0, max_latency+500, 1000))
    xticks = ax_latency_server.xaxis.get_major_ticks()
    xticks[0].tick1line.set_markersize(0)
    xticks[0].tick2line.set_markersize(0)
    xticks[-1].tick1line.set_markersize(0)
    xticks[-1].tick2line.set_markersize(0)
    yticks = ax_latency_server.yaxis.get_major_ticks()
    yticks[0].tick1line.set_markersize(0)
    yticks[0].tick2line.set_markersize(0)
    yticks[-1].tick1line.set_markersize(0)
    yticks[-1].tick2line.set_markersize(0)
    ax_latency_server.tick_params(which="both", top=True, right=True)

    pos_server = ax_latency_server.get_position()
    fig_w_server, fig_h_server = fig_latency_server.get_size_inches()
    x0_server = fig_w_server * pos_server.x0
    y0_server = fig_h_server * pos_server.y0
    x1_server = fig_w_server * pos_server.x1
    y1_server = fig_h_server * pos_server.y1
    bbox_server = transforms.Bbox.from_extents(
        x0_server - pad_left,
        y0_server - pad_bottom,
        x1_server + pad_right,
        y1_server + pad_top,
    )
    # bbox_inches_server = bbox_server.transformed(fig_latency_server.dpi_scale_trans.inverted())

    fig_latency_server.savefig("/home/ame/latency/slide/results/rx_sched_vs_softirq_packet_server.pdf", bbox_inches=bbox_server)

    # ax_throughput_client.set_xlabel("# million of packets in softIRQ processing")
    # ax_throughput_client.set_ylabel("Throughput (kIOPS)")
    # ax_throughput_client.legend()
    # # ax_throughput_client.legend(loc='upper right', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
    # ax_throughput_client.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=2)
    # throughput_fig_client.savefig("check_throughput_attribution_sched_vs_packets_client.pdf", bbox_inches='tight')

    # ax_throughput_server.set_xlabel("# million of packets in softIRQ processing")
    # ax_throughput_server.set_ylabel("Throughput (kIOPS)")
    # ax_throughput_server.legend()
    # # ax_throughput_server.legend(loc='upper right', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
    # ax_throughput_server.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=2)
    # throughput_fig_server.savefig("check_throughput_attribution_sched_vs_packets_server.pdf", bbox_inches='tight')