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
            if "core:" in line:
                core, pid, port = int(items[2]), int(items[4]), int(items[7])
                for thread in threads_info:
                    if thread.port == port:
                        thread.server_pid = pid
                        thread.server_core = core
            elif "start-vruntime:" in line:
                pid, start_vruntime = int(items[1]), int(items[3])
                for thread in threads_info:
                    if thread.server_pid == pid:
                        thread.server_start_vruntime = start_vruntime
    
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
                        thread.client_start_vruntime = start_vruntime
            elif "final-vruntime:" in line:
                pid, end_vruntime = int(items[1]), int(items[3])
                for thread in threads_info:
                    if thread.client_pid == pid:
                        thread.client_abs_vruntime = end_vruntime - thread.client_vruntime[0]
            else:
                continue

    # read client inflation info
    client_inflation_path = os.path.join(experiment_dir, f"valid_real_breakdown_sum_p90_client.txt")
    with open(client_inflation_path, "r") as client_inflation_log:
        lines = client_inflation_log.readlines()
        for line in lines[1:]:
            items = line.split()
            port, rx_copy, app, hidden, inflation = int(items[0]), float(items[1]), float(items[2]), float(items[-2]), float(items[-1])
            for thread in threads_info:
                if thread.port == port:
                    thread.client_inflation = inflation# rx_copy # inflation - app - hidden

    # read server inflation info
    server_inflation_path = os.path.join(experiment_dir, f"valid_real_breakdown_sum_p90_server.txt")
    with open(server_inflation_path, "r") as server_inflation_log:
        lines = server_inflation_log.readlines()
        for line in lines[1:]:
            items = line.split()
            port, rx_copy, app, hidden, inflation = int(items[0]), float(items[1]), float(items[2]), float(items[-2]), float(items[-1])
            for thread in threads_info:
                if thread.port == port:
                    thread.server_inflation = inflation #rx_copy #inflation - app - hidden

    # client_inflation_path = os.path.join(experiment_dir, f"valid_real_breakdown_sum_p90_client_samples.txt")
    # with open(client_inflation_path, "r") as client_inflation_log:
    #     lines = client_inflation_log.readlines()
    #     for line in lines[1:]:
    #         items = line.split()
    #         port, rx_copy, app, hidden, total_samples = int(items[0]), float(items[1]), float(items[2]), float(items[-2]), float(items[-1])
    #         for thread in threads_info:
    #             if thread.port == port:
    #                 thread.client_effective_samples = total_samples

    # # read server inflation info
    # server_inflation_path = os.path.join(experiment_dir, f"valid_real_breakdown_sum_p90_server_samples.txt")
    # with open(server_inflation_path, "r") as server_inflation_log:
    #     lines = server_inflation_log.readlines()
    #     for line in lines[1:]:
    #         items = line.split()
    #         port, rx_copy, app, hidden, total_samples = int(items[0]), float(items[1]), float(items[2]), float(items[-2]), float(items[-1])
    #         for thread in threads_info:
    #             if thread.port == port:
    #                 thread.server_effective_samples = total_samples

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
    subtracted = True

    result_dir = "/data0/projects/latency/"
    experiments = [       
        # "sirq_breakdown_6_2/52_64_1_1_1_1_0_0_1_0",
        # "sirq_breakdown_2_1/52_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_3_1/48_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_3_1/48_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_3_1/48_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_3_1/48_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_3_1/48_64_1_1_1_1_0_0_1_4"
        # "sirq_understanding_7_1/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_7_1/52_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_7_1/52_64_1_1_1_1_0_0_1_3"
        # "sirq_understanding_11_1/48_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_12_2/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_13_2/52_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_13_2/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_13_2/52_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_13_2/52_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_13_2/52_64_1_1_1_1_0_0_1_4",
        # "sirq_understanding_13_2/48_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_13_2/48_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_13_2/48_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_13_2/48_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_13_2/48_64_1_1_1_1_0_0_1_4",
        # "sirq_understanding_14_1/52_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_14_1/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_14_1/52_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_14_1/52_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_14_1/52_64_1_1_1_1_0_0_1_4",
        # "sirq_understanding_14_1/48_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_14_1/48_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_14_1/48_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_14_1/48_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_14_1/48_64_1_1_1_1_0_0_1_4",
        # "sirq_understanding_18_2/52_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_18_2/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_18_2/52_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_18_2/52_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_18_2/52_64_1_1_1_1_0_0_1_4",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_4",
        # "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_4",
        # "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_5",
        # "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_6",
        # "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_7",
        # "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_8",
        # "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_9",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_0",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_1",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_2",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_3",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_4",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_5",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_6",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_7",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_8",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_9",
    ]
    n_threads = [
        # 52, 52, 52, 52, 52, 52, 52, 52, 52, 52,
        48, 48, 48, 48, 48, 48, 48, 48, 48, 48,
    ]

    labels = [
        # "24_1_52_0",
        # "24_1_52_1",
        # "24_1_52_2",
        # "24_1_52_3",
        # "24_1_52_4",
        # "24_1_52_5",
        # "24_1_52_6",
        # "24_1_52_7",
        # "24_1_52_8",
        # "24_1_52_9",
        "24_1_48_0",
        "24_1_48_1",
        "24_1_48_2",
        "24_1_48_3",
        "24_1_48_4",
        "24_1_48_5",
        "24_1_48_6",
        "24_1_48_7",
        "24_1_48_8",
        "24_1_48_9",
    ]

    if subtracted:
        labels = [label + "_subtracted" for label in labels]

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
        # # Figure 1: x axis: inflation (processing time), y axis: sched_lat; for client and server, in a single plot
        # fig_inflation_sched = plt.figure(figsize=(5, 4*0.618))
        # ax_inflation_sched = fig_inflation_sched.add_axes([0.1, 0.2, 0.8, 0.7])
        # client_inflations = []
        # server_inflations = []
        # client_sched_latencies_avg = []
        # server_sched_latencies_avg = []
        # client_sched_latencies = []
        # server_sched_latencies = []
        # for idx, thread in enumerate(threads_info):
        #     if thread.client_core == 32:
        #         client_inflations.append(thread.client_inflation/1e3)
        #         server_inflations.append(thread.server_inflation/1e3)
        #         client_sched_latencies_avg.append(thread.client_sched_latency_avg/1e3)
        #         server_sched_latencies_avg.append(thread.server_sched_latency_avg/1e3)
        #         client_sched_latencies.append(thread.client_sched_latency/1e3)
        #         server_sched_latencies.append(thread.server_sched_latency/1e3)
        # ax_inflation_sched.scatter(client_inflations, client_sched_latencies_avg, label="Client, Mean", color="lightblue", marker="o")
        # ax_inflation_sched.scatter(server_inflations, server_sched_latencies_avg, label="Server, Mean", color="moccasin", marker="^")
        # ax_inflation_sched.scatter(client_inflations, client_sched_latencies, label="Client, P99.9", color="royalblue", marker="o")
        # ax_inflation_sched.scatter(server_inflations, server_sched_latencies, label="Server, P99.9", color="orange", marker="^")
        # ax_inflation_sched.set_xlabel("Per-packet Processing Time (us)")
        # ax_inflation_sched.set_ylabel("Rx_sched (us)")
        # ax_inflation_sched.legend()
        # fig_inflation_sched.savefig(f"check_inflation_vs_sched_{label}.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_inflation_sched)

        # # Figure 1.5: x axis: abs virtual runtime / pkts, y axis: sched_lat; for client and server, in a single plot
        # fig_vruntime_per_pkt_sched = plt.figure(figsize=(5, 4*0.618))
        # ax_vruntime_per_pkt_sched = fig_vruntime_per_pkt_sched.add_axes([0.1, 0.2, 0.8, 0.7])
        # client_vruntime_per_pkt = []
        # server_vruntime_per_pkt = []
        # client_sched_latencies_avg = []
        # server_sched_latencies_avg = []
        # client_sched_latencies = []
        # server_sched_latencies = []
        # for idx, thread in enumerate(threads_info):
        #     if thread.client_core == 32:
        #         if thread.packets > 0:
        #             client_vruntime_per_pkt.append(thread.client_abs_vruntime / thread.packets)
        #             server_vruntime_per_pkt.append(thread.server_abs_vruntime / thread.packets)
        #             client_sched_latencies_avg.append(thread.client_sched_latency_avg/1e3)
        #             server_sched_latencies_avg.append(thread.server_sched_latency_avg/1e3)
        #             client_sched_latencies.append(thread.client_sched_latency/1e3)
        #             server_sched_latencies.append(thread.server_sched_latency/1e3)
        # ax_vruntime_per_pkt_sched.scatter(client_vruntime_per_pkt, client_sched_latencies_avg, label="Client, Mean", color="lightblue", marker="o")
        # ax_vruntime_per_pkt_sched.scatter(server_vruntime_per_pkt, server_sched_latencies_avg, label="Server, Mean", color="moccasin", marker="^")
        # ax_vruntime_per_pkt_sched.scatter(client_vruntime_per_pkt, client_sched_latencies, label="Client, P99.9", color="royalblue", marker="o")
        # ax_vruntime_per_pkt_sched.scatter(server_vruntime_per_pkt, server_sched_latencies, label="Server, P99.9", color="orange", marker="^")
        # ax_vruntime_per_pkt_sched.set_xlabel("Per-packet Absolute Virtual Runtime")
        # ax_vruntime_per_pkt_sched.set_ylabel("Rx_sched (us)")
        # ax_vruntime_per_pkt_sched.legend()
        # fig_vruntime_per_pkt_sched.savefig(f"check_vruntime_per_pkt_vs_sched_{label}.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime_per_pkt_sched)

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
        #     if thread.client_core == 32:
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

        # # Figure 3: x axis: thread index, y axis: (1) bar chart to show abs vruntime (left y-axis); (2) line char to show inflation (right y-axis)
        # fig_vruntime_infl = plt.figure(figsize=(10, 5*0.618))
        # ax_vruntime_bar = fig_vruntime_infl.add_axes([0.1, 0.2, 0.6, 0.7])
        # ax_infl_line = ax_vruntime_bar.twinx()
        # client_abs_vruntimes = []
        # server_abs_vruntimes = []
        # client_inflations = []
        # server_inflations = []
        # thread_indices = []
        # for idx, thread in enumerate(threads_info):
        #     if thread.client_core == 32:
        #         thread_indices.append(idx)
        #         client_abs_vruntimes.append(thread.client_abs_vruntime)
        #         server_abs_vruntimes.append(thread.server_abs_vruntime)
        #         client_inflations.append(thread.client_inflation)
        #         server_inflations.append(thread.server_inflation)
        # bar_width = 0.2
        # ax_vruntime_bar.bar(np.array(thread_indices) - bar_width, client_abs_vruntimes, width=bar_width, label="Client", edgecolor="royalblue", alpha=0.7, hatch='\\\\\\', fill=False, linewidth=2)
        # ax_vruntime_bar.bar(np.array(thread_indices) + bar_width, server_abs_vruntimes, width=bar_width, label="Server", edgecolor="orange", alpha=0.7, hatch='\\\\\\', fill=False, linewidth=2)
        # ax_infl_line.plot(thread_indices, client_inflations, label="Client Inflation", color="blue", marker="o")
        # ax_infl_line.plot(thread_indices, server_inflations, label="Server Inflation", color="red", marker="^")
        # ax_vruntime_bar.set_xlabel("Thread Index")
        # ax_vruntime_bar.set_ylabel("Absolute vruntime")
        # ax_vruntime_bar.legend(loc="upper left")
        # ax_vruntime_bar.set_ylim(min(client_abs_vruntimes + server_abs_vruntimes)*0.97, max(max(client_abs_vruntimes), max(server_abs_vruntimes)) * 1.03)
        # ax_infl_line.set_ylabel("Inflation (us)")
        # ax_infl_line.legend(loc="upper right")
        # fig_vruntime_infl.savefig(f"check_inflation_{label}.pdf", dpi=300, bbox_inches='tight')
        # plt.close(fig_vruntime_infl)

        # Figure 5: x axis: thread index, y axis: abs vruntime. For each Client thread, draw two bar: (1) abs vruntime; (2) throughput*inflation*k, k is parameters.
        # Also, add a line to show packets in softirq (softirq_packets) in the same figure
        # Also, add a share x figure, x axis: thread index, y axis: client_abs_vruntime - combined_metrics bar, and line of softirq_packets
        fig_vruntime_infl_thpt = plt.figure(figsize=(14, 5*0.618))
        ax_vruntime_bar = fig_vruntime_infl_thpt.add_axes([0.05, 0.2, 0.4, 0.6])
        # ax_softirq_line = ax_vruntime_bar.twinx()
        # ax_residual = fig_vruntime_infl_thpt.add_axes([0.55, 0.2, 0.15, 0.6])
        # ax_samples = fig_vruntime_infl_thpt.add_axes([0.75, 0.2, 0.15, 0.6], sharey=ax_residual)

        fig_relative_vruntime_infl_thpt = plt.figure(figsize=(10, 5*0.618))
        ax_relative_vruntime_bar = fig_relative_vruntime_infl_thpt.add_axes([0.1, 0.2, 0.5, 0.6])
        ax_relative_vruntime_scatter = fig_relative_vruntime_infl_thpt.add_axes([0.7, 0.2, 0.2, 0.6])

        client_abs_vruntimes = []
        client_softirq_packets = []
        client_inflations = []
        client_thpts = []
        client_effective_samples = []
        client_start_vruntimes = []
        combined_metrics = []
        thread_indices = []
        client_residuals = []
        k = 1

        for idx, thread in enumerate(threads_info):
            if thread.client_core == 32:
                thread_indices.append(idx)
                client_abs_vruntimes.append(thread.client_abs_vruntime)
                client_softirq_packets.append(thread.client_softirq_packets)
                client_inflations.append(thread.client_inflation)
                client_thpts.append(thread.thpt)
                client_effective_samples.append(thread.client_effective_samples)
                client_start_vruntimes.append(thread.client_start_vruntime)

        # best_k = 300 / (1277/1024)
        best_k = 1/86

        # rates = [i * j / k for i, j, k in zip(client_thpts, client_inflations, client_abs_vruntimes)]
        # max_rate = max([r for r in rates if r > 0])
        # best_k = 1 / max_rate

        # Find the best k to minimize the MSE between client_abs_vruntimes and combined_metrics
        # best_k = 1.0
        # min_mse = float('inf')
        # for k in np.arange(0.1, 10.0, 0.01):
        #     scaled_metrics = [thread.thpt * thread.client_inflation * k for thread in threads_info if thread.client_core == 32]
        #     mse = np.mean([(a - b) ** 2 for a, b in zip(client_abs_vruntimes, scaled_metrics)])
        #     if mse < min_mse:
        #         best_k = k
        #         min_mse = mse

        # # Find the k so that max((throughput * inflation * k)/(abs_vruntime)) == 1
        # best_k = float('inf')
        # # min_packets = min([p for p in client_softirq_packets if p > 0])
        # idx = client_softirq_packets.index(min_packets)
        # best_k = client_abs_vruntimes[idx] / (client_thpts[idx] * client_inflations[idx])

        for idx, thread in enumerate(threads_info):
            if thread.client_core == 32:
                combined_value = thread.packets * thread.client_inflation * best_k
                combined_metrics.append(combined_value)
                client_residuals.append(thread.client_abs_vruntime - combined_value)

        if subtracted:
            min_residual = min(client_residuals)
            combined_metrics = [v + min_residual for v in combined_metrics]

        bar_width = 0.3
        ax_vruntime_bar.bar(np.array(thread_indices) - bar_width/2, client_abs_vruntimes, width=bar_width, label=f"Absolute virtual runtime", edgecolor="forestgreen", hatch='\\\\\\', fill=False, linewidth=2)
        ax_vruntime_bar.bar(np.array(thread_indices) + bar_width/2, combined_metrics, width=bar_width, label=f"Modeled runtime{' (subtracted)' if subtracted else ''}", edgecolor="firebrick", hatch='///', fill=False, linewidth=2)
        ax_vruntime_bar.set_xlabel("Thread Index")
        ax_vruntime_bar.set_ylabel("Absolute vruntime")
        ax_vruntime_bar.legend()
        ax_vruntime_bar.set_ylim(min(client_abs_vruntimes + combined_metrics)*0.97, max(max(client_abs_vruntimes), max(combined_metrics)) * 1.03)
        ax_vruntime_bar.set_ylim(5e7, 7e7) # sirq 52
        # ax_softirq_line.plot(thread_indices, client_inflations, label="Client Proc Time", color="purple", marker="o")
        # ax_softirq_line.set_ylabel("Proc Time (ns)")
        # ax_softirq_line.legend()
        # ax_residual.scatter(client_softirq_packets, client_residuals, label="Residual", color="black", marker="x")
        # ax_residual.set_xlabel("#Packets in SoftIRQ")
        # ax_residual.set_ylabel("Residual")
        # ax_samples.scatter(client_effective_samples, client_residuals, color="brown", marker="s")
        # ax_samples.set_xlabel("Total Effective Samples")
        # ax_samples.set_ylabel("Residual")
        for i in range(len(thread_indices)):
            residual = client_abs_vruntimes[i] - combined_metrics[i]
            ax_vruntime_bar.text(thread_indices[i] - bar_width/2, max(client_abs_vruntimes + combined_metrics)*1.01, f"{residual/1e6:.1f}e6", ha='center', va='bottom', fontsize=6)
            ax_vruntime_bar.text(thread_indices[i] - bar_width/2, max(client_abs_vruntimes + combined_metrics)*1.02, f"{(residual/client_abs_vruntimes[i]*100):.1f}%", ha='center', va='bottom', fontsize=6)
        fig_vruntime_infl_thpt.savefig(f"check_throughput_attribution_52_{label}.pdf", dpi=300, bbox_inches='tight')
        plt.close(fig_vruntime_infl_thpt)

        client_normed_abs_vruntimes = norm_vruntime(client_abs_vruntimes, 0)
        client_normed_combined_metrics = norm_vruntime(combined_metrics, 0)
        bar_width = 0.3
        ax_relative_vruntime_bar.bar(np.array(thread_indices) - bar_width/2, client_normed_abs_vruntimes, width=bar_width, label="Virtual runtime", edgecolor="forestgreen", hatch='\\\\\\', fill=False, linewidth=2)
        ax_relative_vruntime_bar.bar(np.array(thread_indices) + bar_width/2, client_normed_combined_metrics, width=bar_width, label=f"Modeled runtime", edgecolor="firebrick", hatch='///', fill=False, linewidth=2)
        # Plot client_start_vruntime as a line
        ax_relative_vruntime_bar.plot(thread_indices, norm_vruntime(client_start_vruntimes, 0), label="Start vruntime", color="blue", marker="o")
        ax_relative_vruntime_bar.set_xlabel("Thread Index")
        ax_relative_vruntime_bar.set_ylabel("Relative time")
        ax_relative_vruntime_bar.legend()
        # ax_relative_vruntime_bar.set_ylim(min(client_normed_abs_vruntimes + client_normed_combined_metrics)*0.9, max(max(client_normed_abs_vruntimes), max(client_normed_combined_metrics)) * 1.1)
        ax_relative_vruntime_bar.set_ylim(0, 5e6)
        for i in range(len(thread_indices)):
            residual = client_normed_abs_vruntimes[i] - client_normed_combined_metrics[i]
            ax_relative_vruntime_bar.text(thread_indices[i] - bar_width/2, max(client_normed_abs_vruntimes + client_normed_combined_metrics)*1.01, f"{residual/1e5:.1f}e5", ha='center', va='bottom', fontsize=5)
        ax_relative_vruntime_scatter.scatter(client_normed_combined_metrics, client_normed_abs_vruntimes, marker="x")
        ax_relative_vruntime_scatter.set_xlabel("Processing Time")
        ax_relative_vruntime_scatter.set_ylabel("Virtual Runtime")
        fig_relative_vruntime_infl_thpt.savefig(f"check_normed_throughput_attribution_52_{label}.pdf", dpi=300, bbox_inches='tight')
        plt.close(fig_relative_vruntime_infl_thpt)


        # Figure 6: x axis: thread index, y axis: abs vruntime. For each Server thread, draw two bar: (1) abs vruntime; (2) throughput*inflation*k, k is parameters.
        fig_vruntime_infl_thpt = plt.figure(figsize=(14, 5*0.618))
        ax_vruntime_bar = fig_vruntime_infl_thpt.add_axes([0.05, 0.2, 0.4, 0.6])
        # ax_softirq_line = ax_vruntime_bar.twinx()
        # ax_residual = fig_vruntime_infl_thpt.add_axes([0.55, 0.2, 0.15, 0.6])
        # ax_samples = fig_vruntime_infl_thpt.add_axes([0.75, 0.2, 0.15, 0.6], sharey=ax_residual)

        fig_relative_vruntime_infl_thpt = plt.figure(figsize=(10, 5*0.618))
        ax_relative_vruntime_bar = fig_relative_vruntime_infl_thpt.add_axes([0.1, 0.2, 0.5, 0.6])
        ax_relative_vruntime_scatter = fig_relative_vruntime_infl_thpt.add_axes([0.7, 0.2, 0.2, 0.6])

        server_abs_vruntimes = []
        server_thpts = []
        server_inflations = []
        server_softirq_packets = []
        server_effective_samples = []
        server_start_vruntimes = []
        combined_metrics = []
        thread_indices = []
        server_residuals = []

        # Find the best k to minimize the MSE between server_abs_vruntimes and combined_metrics
        for idx, thread in enumerate(threads_info):
            if thread.client_core == 32:
                thread_indices.append(idx)
                server_abs_vruntimes.append(thread.server_abs_vruntime)
                server_thpts.append(thread.thpt)
                server_inflations.append(thread.server_inflation)
                server_softirq_packets.append(thread.server_softirq_packets)
                server_effective_samples.append(thread.server_effective_samples)
                server_start_vruntimes.append(thread.server_start_vruntime)
        
        # best_k = 300 / (1277/1024)
        best_k = 1/86
        # rates = [i * j / k for i, j, k in zip(server_thpts, server_inflations, server_abs_vruntimes)]
        # max_rate = max([r for r in rates if r > 0])
        # best_k = 1 / max_rate

        # best_k = 1.0
        # min_mse = float('inf')
        # for k in np.arange(0.1, 10.0, 0.01):
        #     scaled_metrics = [thread.thpt * thread.server_inflation * k for thread in threads_info if thread.client_core == 32]
        #     mse = np.mean([(a - b) ** 2 for a, b in zip(server_abs_vruntimes, scaled_metrics)])
        #     if mse < min_mse:
        #         min_mse = mse
        #         best_k = k
        
        # best_k = float('inf')
        # min_packets = min([p for p in server_softirq_packets if p > 0])
        # idx = server_softirq_packets.index(min_packets)
        # best_k = server_abs_vruntimes[idx] / (server_thpts[idx] * server_inflations[idx])

        for idx, thread in enumerate(threads_info):
            if thread.client_core == 32:
                combined_value = thread.packets * thread.server_inflation * best_k
                combined_metrics.append(combined_value)
                server_residuals.append(thread.server_abs_vruntime - combined_value)

        if subtracted:
            min_residual = min(server_residuals)
            combined_metrics = [v + min_residual for v in combined_metrics]

        bar_width = 0.3
        ax_vruntime_bar.bar(np.array(thread_indices) - bar_width/2, server_abs_vruntimes, width=bar_width, label="Absolute virtual runtime", edgecolor="forestgreen", hatch='\\\\\\', fill=False, linewidth=2)
        ax_vruntime_bar.bar(np.array(thread_indices) + bar_width/2, combined_metrics, width=bar_width, label=f"Modeled runtime{' (subtracted)' if subtracted else ''}", edgecolor="firebrick", hatch='///', fill=False, linewidth=2)
        ax_vruntime_bar.set_xlabel("Thread Index")
        ax_vruntime_bar.set_ylabel("Absolute vruntime")
        ax_vruntime_bar.legend()
        ax_vruntime_bar.set_ylim(min(server_abs_vruntimes + combined_metrics)*0.97, max(max(server_abs_vruntimes), max(combined_metrics)) * 1.03)
        ax_vruntime_bar.set_ylim(5e7, 7e7) # sirq 52
        # ax_softirq_line.plot(thread_indices, server_inflations, label="Server Proc Time", color="purple", marker="o")
        # ax_softirq_line.set_ylabel("Proc Time (ns)")
        # ax_softirq_line.legend()
        # ax_residual.scatter(server_softirq_packets, [a - b for a, b in zip(server_abs_vruntimes, combined_metrics)], label="Residual", color="black", marker="x")
        # ax_residual.set_xlabel("#Packets in SoftIRQ")
        # ax_residual.set_ylabel("Residual")
        # ax_samples.scatter(server_effective_samples, [a - b for a, b in zip(server_abs_vruntimes, combined_metrics)], color="brown", marker="s")
        # ax_samples.set_xlabel("Total Effective Samples")
        # ax_samples.set_ylabel("Residual")
        for i in range(len(thread_indices)):
            residual = server_abs_vruntimes[i] - combined_metrics[i]
            ax_vruntime_bar.text(thread_indices[i] - bar_width/2, max(server_abs_vruntimes + combined_metrics)*1.01, f"{residual/1e6:.1f}e6", ha='center', va='bottom', fontsize=6)
            ax_vruntime_bar.text(thread_indices[i] - bar_width/2, max(server_abs_vruntimes + combined_metrics)*1.02, f"{(residual/server_abs_vruntimes[i]*100):.1f}%", ha='center', va='bottom', fontsize=6)
        fig_vruntime_infl_thpt.savefig(f"check_throughput_attribution_52_server_{label}.pdf", dpi=300, bbox_inches='tight')
        plt.close(fig_vruntime_infl_thpt)

        server_normed_abs_vruntimes = norm_vruntime(server_abs_vruntimes, 0)
        server_normed_combined_metrics = norm_vruntime(combined_metrics, 0)
        bar_width = 0.3
        ax_relative_vruntime_bar.bar(np.array(thread_indices) - bar_width/2, server_normed_abs_vruntimes, width=bar_width, label="Virtual runtime", edgecolor="forestgreen", hatch='\\\\\\', fill=False, linewidth=2)
        ax_relative_vruntime_bar.bar(np.array(thread_indices) + bar_width/2, server_normed_combined_metrics, width=bar_width, label=f"Modeled processing time", edgecolor="firebrick", hatch='///', fill=False, linewidth=2)
        # Plot server_start_vruntime as a line
        ax_relative_vruntime_bar.plot(thread_indices, norm_vruntime(server_start_vruntimes, 0), label="Start vruntime", color="blue", marker="o")
        ax_relative_vruntime_bar.set_xlabel("Thread Index")
        ax_relative_vruntime_bar.set_ylabel("Relative time")
        ax_relative_vruntime_bar.legend()
        # ax_relative_vruntime_bar.set_ylim(min(server_normed_abs_vruntimes + server_normed_combined_metrics)*0.9, max(max(server_normed_abs_vruntimes), max(server_normed_combined_metrics)) * 1.1)
        ax_relative_vruntime_bar.set_ylim(0, 5e6)
        for i in range(len(thread_indices)):
            residual = server_normed_abs_vruntimes[i] - server_normed_combined_metrics[i]
            ax_relative_vruntime_bar.text(thread_indices[i] - bar_width/2, max(server_normed_abs_vruntimes + server_normed_combined_metrics)*1.01, f"{residual/1e5:.1f}e5", ha='center', va='bottom', fontsize=5)
        ax_relative_vruntime_scatter.scatter(server_normed_combined_metrics, server_normed_abs_vruntimes, marker="x")
        ax_relative_vruntime_scatter.set_xlabel("Processing Time")
        ax_relative_vruntime_scatter.set_ylabel("Virtual Runtime")
        fig_relative_vruntime_infl_thpt.savefig(f"check_normed_throughput_attribution_52_server_{label}.pdf", dpi=300, bbox_inches='tight')
        plt.close(fig_relative_vruntime_infl_thpt)


        # –––––––––––––––––––––––––––––––––––––––––––––––––––––––
        # Figure 7: x axis: thread index, y axis: for each threads, draw two bars: (1) client inflation (2) per-packet virtual runtime
        fig_inflation_vruntime = plt.figure(figsize=(10, 5*0.618))
        ax_inflation_bar = fig_inflation_vruntime.add_axes([0.1, 0.2, 0.5, 0.6])
        ax_inflation_scatter = fig_inflation_vruntime.add_axes([0.7, 0.2, 0.2, 0.6])
        client_inflations = []
        client_per_packet_vruntimes = []
        thread_indices = []
        for idx, thread in enumerate(threads_info):
            if thread.client_core == 32:
                thread_indices.append(idx)
                client_inflations.append(thread.client_inflation)
                if thread.packets > 0:
                    client_per_packet_vruntimes.append(thread.client_abs_vruntime * 86 / thread.packets)
                    # client_per_packet_vruntimes.append(thread.client_abs_vruntime / thread.packets)
                else:
                    client_per_packet_vruntimes.append(0)
        bar_width = 0.3
        ax_inflation_bar.bar(np.array(thread_indices) - bar_width/2, client_inflations, width=bar_width, label="Per-packet processing time (ns)", edgecolor="royalblue", alpha=0.7, hatch='\\\\\\', fill=False, linewidth=2)
        ax_inflation_bar.bar(np.array(thread_indices) + bar_width/2, client_per_packet_vruntimes, width=bar_width, label="Per-packet accounted runtime (ns)", edgecolor="orange", alpha=0.7, hatch='///', fill=False, linewidth=2)
        ax_inflation_bar.set_xlabel("Thread Index")
        ax_inflation_bar.set_ylabel("Time (ns)")
        ax_inflation_bar.legend()
        ax_inflation_bar.set_ylim(min(client_inflations + client_per_packet_vruntimes)*0.9, max(max(client_inflations), max(client_per_packet_vruntimes)) * 1.1)
        for i in range(len(thread_indices)):
            diff = client_per_packet_vruntimes[i] - client_inflations[i]
            ax_inflation_bar.text(thread_indices[i] - bar_width/2, max(client_inflations + client_per_packet_vruntimes)*1.01, f"{diff:.0f}", ha='center', va='bottom', fontsize=5)
            if client_per_packet_vruntimes[i] > 0:
                ax_inflation_bar.text(thread_indices[i] - bar_width/2, max(client_inflations + client_per_packet_vruntimes)*1.02, f"{(diff/client_per_packet_vruntimes[i]*100):.1f}%", ha='center', va='bottom', fontsize=5)
        ax_inflation_scatter.scatter(client_inflations, client_per_packet_vruntimes, color="green", marker="o")
        ax_inflation_scatter.set_xlabel("Processing Time (ns)")
        ax_inflation_scatter.set_ylabel("Accounted Runtime (ns)")
        fig_inflation_vruntime.savefig(f"check_per_packet_{label}.pdf", dpi=300, bbox_inches='tight')
        plt.close(fig_inflation_vruntime)

        # Figure 8: Figure similar to Figure 7, but for Server threads
        fig_inflation_vruntime = plt.figure(figsize=(10, 5*0.618))
        ax_inflation_bar = fig_inflation_vruntime.add_axes([0.1, 0.2, 0.5, 0.6])
        ax_inflation_scatter = fig_inflation_vruntime.add_axes([0.7, 0.2, 0.2, 0.6])
        server_inflations = []
        server_per_packet_vruntimes = []
        thread_indices = []
        for idx, thread in enumerate(threads_info):
            if thread.client_core == 32:
                thread_indices.append(idx)
                server_inflations.append(thread.server_inflation)
                if thread.packets > 0:
                    server_per_packet_vruntimes.append(thread.server_abs_vruntime * 86 / thread.packets)
                    # server_per_packet_vruntimes.append(thread.server_abs_vruntime / thread.packets)
                else:
                    server_per_packet_vruntimes.append(0)
        bar_width = 0.3
        ax_inflation_bar.bar(np.array(thread_indices) - bar_width/2, server_inflations, width=bar_width, label="Per-packet processing time (ns)", edgecolor="royalblue", alpha=0.7, hatch='\\\\\\', fill=False, linewidth=2)
        ax_inflation_bar.bar(np.array(thread_indices) + bar_width/2, server_per_packet_vruntimes, width=bar_width, label="Per-packet accounted runtime (ns)", edgecolor="orange", alpha=0.7, hatch='///', fill=False, linewidth=2)
        ax_inflation_bar.set_xlabel("Thread Index")
        ax_inflation_bar.set_ylabel("Time (ns)")
        ax_inflation_bar.legend()
        ax_inflation_bar.set_ylim(min(server_inflations + server_per_packet_vruntimes)*0.9, max(max(server_inflations), max(server_per_packet_vruntimes)) * 1.1)
        for i in range(len(thread_indices)): 
            diff = server_per_packet_vruntimes[i] - server_inflations[i]
            ax_inflation_bar.text(thread_indices[i] - bar_width/2, max(server_inflations + server_per_packet_vruntimes)*1.01, f"{diff:.0f}", ha='center', va='bottom', fontsize=5)
            if server_per_packet_vruntimes[i] > 0:
                ax_inflation_bar.text(thread_indices[i] - bar_width/2, max(server_inflations + server_per_packet_vruntimes)*1.02, f"{(diff/server_per_packet_vruntimes[i]*100):.1f}%", ha='center', va='bottom', fontsize=5)
        ax_inflation_scatter.scatter(server_inflations, server_per_packet_vruntimes, color="green", marker="o")
        ax_inflation_scatter.set_xlabel("Processing Time (ns)")
        ax_inflation_scatter.set_ylabel("Accounted Runtime (ns)")
        fig_inflation_vruntime.savefig(f"check_per_packet_server_{label}.pdf", dpi=300, bbox_inches='tight')
        plt.close(fig_inflation_vruntime)
