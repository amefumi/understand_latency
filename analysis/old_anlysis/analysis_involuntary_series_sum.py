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
        self.client_softirq_packets = 0
        self.client_sched_latency = 0
        self.client_nivcsw = 0
        self.client_vruntime = []
        self.client_abs_vruntime = 0
        self.client_inflation = []

        self.server_pid = server_pid
        self.server_core = server_core
        self.server_softirq_packets = 0
        self.server_sched_latency = 0
        self.server_nivcsw = 0
        self.server_vruntime = []
        self.server_abs_vruntime = 0
        self.server_inflation = []

    def __str__(self):
        return (f"---Port: {self.port}, Througput: {self.thpt}, Latency: {self.latency}, "
                f"Client: PID-{self.client_pid}, Core-{self.client_core}, "
                f"SoftIRQ-Packets-{self.client_softirq_packets}, Sched-Latency-{self.client_sched_latency}, "
                f"NIVCSW-{self.client_nivcsw}, Abs-Vruntime-{self.client_abs_vruntime}, "
                f"Inflation-{self.client_inflation}, "
                f"Server: PID-{self.server_pid}, Core-{self.server_core}, "
                f"SoftIRQ-Packets-{self.server_softirq_packets}, Sched-Latency-{self.server_sched_latency}), "
                f"NIVCSW-{self.server_nivcsw}, Abs-Vruntime-{self.server_abs_vruntime}, "
                f"Inflation-{self.server_inflation}")

    def __repr__(self):
        return f"<ThreadData port={self.port} client_pid={self.client_pid} thpt={self.thpt} latency={self.latency}>"

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
            else:
                continue

    # read server involuntary context switch count
    server_nivcsw_path = os.path.join(experiment_dir, f"server_nivcsw.log")
    with open(server_nivcsw_path, "r") as server_nivcsw_log:
        lines = server_nivcsw_log.readlines()
        for line in lines:
            items = line.split()
            if len(items) < 2:
                continue
            pid, nivcsw = int(items[0]), int(items[1])
            for thread in threads_info:
                if thread.server_pid == pid:
                    thread.server_nivcsw = nivcsw

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

    # read P90 sum time
    client_p90_path = os.path.join(experiment_dir, f"breakdown_sum_p90_client.txt")
    client_p90_port = []
    client_p90_abs = []
    client_500ns = []
    client_800ns = []
    client_1000ns = []
    with open(client_p90_path, "r") as client_p90_log:
        lines = client_p90_log.readlines()[1:]
        for line in lines:
            #split with comma
            items = line.split()
            if len(items) < 5:
                continue
            client_p90_port.append(int(items[0]))
            client_p90_abs.append(int(items[1]))
            client_500ns.append(int(float(items[2])))
            client_800ns.append(int(float(items[3])))
            client_1000ns.append(int(float(items[4])))
    client_p90 = norm_vruntime(client_p90_abs)
    client_500ns = norm_vruntime(client_500ns)
    client_800ns = norm_vruntime(client_800ns)
    client_1000ns = norm_vruntime(client_1000ns)
    for idx, port in enumerate(client_p90_port):
        for thread in threads_info:
            if thread.port == port:
                thread.client_inflation = [client_p90[idx], client_500ns[idx], client_800ns[idx], client_1000ns[idx]]
    server_p90_path = os.path.join(experiment_dir, f"breakdown_sum_p90_server.txt")
    server_p90_port = []
    server_p90_abs = []
    server_500ns = []
    server_800ns = []
    server_1000ns = []
    with open(server_p90_path, "r") as server_p90_log:
        lines = server_p90_log.readlines()[1:]
        for line in lines:
            items = line.split()
            if len(items) < 5:
                continue
            server_p90_port.append(int(items[0]))
            server_p90_abs.append(int(items[1]))
            server_500ns.append(int(float(items[2])))
            server_800ns.append(int(float(items[3])))
            server_1000ns.append(int(float(items[4])))
    server_p90 = norm_vruntime(server_p90_abs)
    server_500ns = norm_vruntime(server_500ns)
    server_800ns = norm_vruntime(server_800ns)
    server_1000ns = norm_vruntime(server_1000ns)
    for idx, port in enumerate(server_p90_port):
        for thread in threads_info:
            if thread.port == port:
                thread.server_inflation = [server_p90[idx], server_500ns[idx], server_800ns[idx], server_1000ns[idx]]

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
        "airq_involuntary_switch_1_1/52_64_1_1_1_1_0_0_1_2",
    ]

    n_threads = [52]
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

        # draw abs-vruntime vs inflation for client
        plt.figure(figsize=(6, 6*0.618))
        plt.scatter([thread.server_abs_vruntime for thread in threads_info if thread.server_core == 32], [thread.server_inflation[3] for thread in threads_info if thread.server_core == 32])
        plt.xlabel("Absolute Vruntime Increase (Server)")
        plt.ylabel("Inflation (Server 1000ns)")
        plt.grid()
        plt.tight_layout()
        plt.savefig(os.path.join("ivcsw_abs_vruntime_vs_inflation_server_1000ns.pdf"))

        # draw [abs-vruntime - inflation/86] vs ivcsw
        plt.figure(figsize=(6, 6*0.618))
        plt.scatter([thread.server_nivcsw for thread in threads_info if thread.server_core == 32],[thread.server_abs_vruntime - thread.server_inflation[3]*(100/86) for thread in threads_info if thread.server_core == 32])
        plt.ylabel("Adjusted vruntime increase")
        plt.xlabel("Involuntary Context Switches")
        plt.grid()
        plt.tight_layout()
        plt.savefig(os.path.join("ivcsw_vs_adjusted_vruntime_server_1000ns.pdf"))

        # draw [abs-vruntime - inflation/86] vs ivcsw
        plt.figure(figsize=(6, 6*0.618))
        plt.scatter([thread.server_nivcsw for thread in threads_info if thread.server_core == 32],[thread.server_abs_vruntime - thread.server_inflation[3]*(100/86) - 10*thread.server_nivcsw for thread in threads_info if thread.server_core == 32])
        plt.ylabel("Adjusted vruntime increase (with penalty)")
        plt.xlabel("Involuntary Context Switches")
        plt.grid()
        plt.tight_layout()
        plt.savefig(os.path.join("ivcsw_vs_adjusted_vruntime_server_sched_1000ns.pdf"))

        # plt.figure(figsize=(6, 6*0.618))
        # plt.scatter([thread.client_nivcsw for thread in threads_info if thread.client_core == 96],[thread.client_abs_vruntime - (1.5)*thread.client_inflation*(100/86) for thread in threads_info if thread.client_core == 96])
        # plt.ylabel("Adjusted vruntime increase (rate=1.5)")
        # plt.xlabel("Involuntary Context Switches")
        # plt.grid()
        # plt.tight_layout()
        # plt.savefig(os.path.join("ivcsw_vs_adjusted_vruntime_1.5.pdf"))

        plt.figure(figsize=(6, 6*0.618))
        plt.scatter([thread.server_nivcsw for thread in threads_info if thread.server_core == 32],[thread.server_abs_vruntime for thread in threads_info if thread.server_core == 32])
        plt.ylabel("Absolute Vruntime Increase")
        plt.xlabel("Involuntary Context Switches")
        plt.grid()
        plt.tight_layout()
        plt.savefig(os.path.join("ivcsw_vs_absolute_vruntime_server.pdf"))