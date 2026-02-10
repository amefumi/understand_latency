import os
import re
import numpy as np
from xmlrpc import server
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.colors as mcolors
from matplotlib.patches import FancyBboxPatch
import matplotlib.font_manager as fm
import matplotlib.patheffects as path_effects
from matplotlib.ticker import MultipleLocator, LogLocator, LogFormatter

fm.fontManager.addfont("/home/ame/GillSans/Gill Sans.otf")
fm.fontManager.addfont("/home/ame/GillSans/Gill Sans Medium.otf")
fm.fontManager.addfont("/home/ame/GillSans/Gill Sans Bold.otf")

# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.family": "serif",
    "font.serif": ["Gill Sans"],
    "font.weight": 500,
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
    # "ytick.minor.width": 2,
    # "ytick.minor.size": 3,
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
    "legend.fontsize": 11,

})


colors = ["#7e2097", "#364e4f", "#f09235"]
markers = [
    "1", "2"
]

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
        self.client_effective_samples = 0
        self.client_start_vruntime = 0

        self.server_pid = 0
        self.server_core = 0
        self.server_softirq_packets = 0
        self.server_sched_latency = 0
        self.server_nivcsw = 0
        self.server_nvcsw = 0
        self.server_vruntime = []
        self.server_abs_vruntime = 0
        self.server_inflation = 0
        self.server_effective_samples = 0

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

def rankinize(vruntime_line, base_value=1):
    # input an array of vruntime values, output an array of each value's rank (starting from base_value)
    if len(vruntime_line) == 0:
        return []
    sorted_vruntimes = sorted(vruntime_line)
    ranked_vruntimes = []
    for v in vruntime_line:
        rank = sorted_vruntimes.index(v) + base_value
        ranked_vruntimes.append(rank)
    return ranked_vruntimes

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
            # elif "start-vruntime:" in line:
            #     pid, start_vruntime = int(items[1]), int(items[3])
            #     for thread in threads_info:
            #         if thread.client_pid == pid:
            #             thread.client_vruntime.append(start_vruntime)
            #             thread.client_start_vruntime = start_vruntime
            # elif "final-vruntime:" in line:
            #     pid, end_vruntime = int(items[1]), int(items[3])
            #     for thread in threads_info:
            #         if thread.client_pid == pid:
            #             thread.client_abs_vruntime = end_vruntime - thread.client_vruntime[0]
            else:
                continue

    # read server involuntary context switch count
    # server_nivcsw_path = os.path.join(experiment_dir, f"server_nivcsw.log")
    # with open(server_nivcsw_path, "r") as server_nivcsw_log:
    #     lines = server_nivcsw_log.readlines()
    #     for line in lines:
    #         items = line.split()
    #         if len(items) < 3:
    #             continue
    #         pid, nivcsw, nvcsw = int(items[0]), int(items[1]), int(items[2])
    #         for thread in threads_info:
    #             if thread.server_pid == pid:
    #                 thread.server_nivcsw = int(nivcsw * (300/297))
    #                 thread.server_nvcsw = int(nvcsw * (300/297))

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


def parse_sched(threads_info, experiment_dir, n_threads):
    # client_sched = os.path.join(experiment_dir, f"sched_client_iodepth_{n_threads}.txt")
    # server_sched = os.path.join(experiment_dir, f"sched_server_iodepth_{n_threads}.txt")
    client_sched = os.path.join(experiment_dir, f"sched_client_{n_threads}.txt")
    server_sched = os.path.join(experiment_dir, f"sched_server_{n_threads}.txt")

    with open(client_sched, "r") as client_log:
        lines = client_log.readlines()
        for line in lines[1:]:
            items = line.split(',')
            if len(items) < 4:
                continue
            port, avg, mid, p999 = int(items[0]), float(items[1]), float(items[2]), float(items[3])
            for thread in threads_info:
                if thread.port == port:
                    thread.client_sched_latency = p999
    with open(server_sched, "r") as server_log:
        lines = server_log.readlines()
        for line in lines[1:]:
            items = line.split(',')
            if len(items) < 4:
                continue
            port, avg, mid, p999 = int(items[0]), float(items[1]), float(items[2]), float(items[3])
            for thread in threads_info:
                if thread.port == port:
                    thread.server_sched_latency = p999
    return threads_info


if __name__ == "__main__":

    NETFILTER_COUNT = 30

    result_dir = "/data0/projects/latency/"
    experiments = [
        # "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_4",
        "nirq_pktirq_vruntime_1_1/48_64_1_1_1_1_0_0_1_3"
    ]

    n_threads = [
        48, 48, 48, 48,
        48, 48, 48, 48,
        48, 48, 48, 48,
        48, 48, 48, 48,
    ]

    labels = [
        # "sirq_understanding_24_48_1_4",
        "nirq_pktirq_vruntime_48_1_3"
    ]


    for index, experiment, n_thread, label in zip(range(len(experiments)), experiments, n_threads, labels):
        experiment_dir = os.path.join(result_dir, experiment)
        threads_info = parse_all_thread_info(experiment_dir, n_thread)
        threads_info = parse_netfilter(threads_info, experiment_dir)
        threads_info = parse_vruntime(threads_info, experiment_dir)
        threads_info = parse_sched(threads_info, experiment_dir, n_thread)
        for thread in threads_info:
            print(thread)

        # Draw relative vruntime for client and server

        clients_ranks = [[] for _ in range(n_thread//2)]
        servers_ranks = [[] for _ in range(n_thread//2)]

        for t in range(len(threads_info[0].server_vruntime)):
            vruntime_clients = [thread.client_vruntime[t] for thread in threads_info if thread.client_core == 32]
            vruntime_servers = [thread.server_vruntime[t] for thread in threads_info if thread.server_core == 32]
            
            clients_ranks_t = rankinize(vruntime_clients, base_value=1)
            servers_ranks_t = rankinize(vruntime_servers, base_value=1)
            for i in range(n_thread//2):
                clients_ranks[i].append(clients_ranks_t[i])
                servers_ranks[i].append(servers_ranks_t[i])

        clients_avg_ranks = [np.mean(ranks) for ranks in clients_ranks]
        servers_avg_ranks = [np.mean(ranks) for ranks in servers_ranks]

        e2e_latency = [thread.latency for thread in threads_info if thread.client_core == 32]
        clients_sched = [thread.client_sched_latency for thread in threads_info if thread.client_core == 32]
        servers_sched = [thread.server_sched_latency for thread in threads_info if thread.server_core == 32]

        # draw e2e_latency vs avg server rank and avg client rank

        # Initialize figure and axis
        # y:x = 7:4
        ax_height = 2.2
        ax_width = 3.85
        fig_width = 20
        fig_height = 20

        fig = plt.figure(figsize=(fig_width, fig_height)) # Create a very big figure
        ax_width_frac = ax_width / fig_width
        ax_height_frac = ax_height / fig_height

        ax = fig.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac]) # Add axes at specific position

        # re-draw axes spines
        for spine in ax.spines.values():
            spine.set_visible(False)

        bbox = FancyBboxPatch(
            (0, 0), 1, 1,
            boxstyle="round,pad=0.0,rounding_size=0.001",
            transform=ax.transAxes,
            linewidth=2,
            edgecolor="black",
            facecolor="none",
            zorder=1,
            clip_on=False,
        )
        ax.add_patch(bbox)


        ax.scatter(clients_avg_ranks, clients_sched, marker='1', label='Client')
        ax.scatter(servers_avg_ranks, servers_sched, marker='2', label='Server')

        ax.grid(
            True,
            which="major",
            linestyle=(0, (0, 2)),
            linewidth=2,
            color="black",
            dash_capstyle="round",
            alpha=1.0,
            zorder=1,
        )

        ax.set_xlabel('Average scheduling order')
        ax.set_ylabel('P99.9 rx_sched Latency (us)')

        ax.set_xlim(0, 25)
        ax.set_xticks(np.arange(0, 25+0.05, 5), ["0", "5", "10", "15", "20", "25"])
        xticks = ax.xaxis.get_major_ticks()
        xticks[0].tick1line.set_markersize(0)
        xticks[0].tick2line.set_markersize(0)
        xticks[-1].tick1line.set_markersize(0)
        xticks[-1].tick2line.set_markersize(0)

        ax.set_ylim(-2e5, 4e6)
        ax.set_yticks(np.arange(0, 3e6+500, 1e6), ["0", "1000", "2000", "3000"])
        yticks = ax.yaxis.get_major_ticks()
        # yticks[0].tick1line.set_markersize(0)
        # yticks[0].tick2line.set_markersize(0)
        yticks[-1].tick1line.set_markersize(0)
        yticks[-1].tick2line.set_markersize(0)

        ax.tick_params(which="both", top=True, right=True)

        legend = ax.legend(loc='upper left', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)

        plt.savefig(os.path.join(f"avg_rank_vs_latency_{label}.pdf"), bbox_inches='tight')
        plt.close()