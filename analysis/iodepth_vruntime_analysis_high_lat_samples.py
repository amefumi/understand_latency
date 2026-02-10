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

# fm.fontManager.addfont("/home/ame/GillSans.ttc")

# # ---------- style (global) ----------
# mpl.rcParams.update({
#     # font
#     "font.family": "Gill Sans",
#     "font.size": 14,

#     # sizes
#     "axes.titlesize": 14,
#     "axes.labelsize": 14,
#     "xtick.labelsize": 14,
#     "ytick.labelsize": 14,

#     # lines and markers
#     "lines.linewidth": 2.5,
#     "lines.markersize": 4,
    
#     # thick frame and ticks
#     "axes.linewidth": 2,
#     "xtick.major.width": 1,
#     "xtick.major.size": 3,
#     "ytick.major.width": 1,
#     "ytick.major.size": 3,
#     "xtick.minor.width": 2,
#     "xtick.minor.size": 2,
#     "ytick.minor.width": 2,
#     "ytick.minor.size": 2,
#     "xtick.direction": "in",
#     "ytick.direction": "in",
    
#     # grid
#     "grid.linestyle": ":",
#     "grid.linewidth": 2,
#     "grid.color": "black",
#     "grid.alpha": 1,
#     "axes.axisbelow": True,

#     # legend
#     "legend.fontsize": 12,
# })

colors1 = plt.cm.tab20b(np.linspace(0, 1, 20))
colors2 = plt.cm.tab20c(np.linspace(0, 1, 20))
colors = np.vstack((colors1, colors2))


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
        self.client_high_rx_sched_ts = []
        self.client_high_rx_sched = []
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
        self.server_high_rx_sched_ts = []
        self.server_high_rx_sched = []
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

    for thread in threads_info:
        i = thread.port - 10000
        client_samples_path = os.path.join(experiment_dir, f"netperf-{i}_high_client_rx_sched.log")
        with open(client_samples_path, "r") as client_samples_log:
            lines = client_samples_log.readlines()
            for line in lines:
                items = line.split()
                if len(items) < 2:
                    continue
                thread.client_high_rx_sched_ts.append(int(items[0])/1e9) # ns to s
                thread.client_high_rx_sched.append(int(items[1])/1e3) # ns to us

        server_samples_path = os.path.join(experiment_dir, f"netperf-{i}_high_server_rx_sched.log")
        with open(server_samples_path, "r") as server_samples_log:
            lines = server_samples_log.readlines()
            for line in lines:
                items = line.split()
                if len(items) < 2:
                    continue
                thread.server_high_rx_sched_ts.append(int(items[0])/1e9) # ns to s
                thread.server_high_rx_sched.append(int(items[1])/1e3) # ns to us

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


if __name__ == "__main__":

    NETFILTER_COUNT = 30

    result_dir = "/data0/projects/latency/"
    experiments = [
        # "sirq_vruntime_iodepth_1_1/48_64_1_1_1_1_0_0_1_0",
        # "sirq_vruntime_iodepth_1_1/48_64_1_1_1_1_0_0_1_1",
        # "sirq_vruntime_iodepth_1_1/48_64_1_1_1_1_0_0_1_2",
        # "sirq_vruntime_iodepth_1_1/48_64_1_1_1_1_0_0_1_3",
        # "sirq_vruntime_iodepth_1_1/48_64_8_1_1_1_0_0_1_0",
        # "sirq_vruntime_iodepth_1_1/48_64_8_1_1_1_0_0_1_1",
        # "sirq_vruntime_iodepth_1_1/48_64_8_1_1_1_0_0_1_2",
        # "sirq_vruntime_iodepth_1_1/48_64_8_1_1_1_0_0_1_3",
        # "sirq_vruntime_iodepth_1_1/48_64_16_1_1_1_0_0_1_0",
        # "sirq_vruntime_iodepth_1_1/48_64_16_1_1_1_0_0_1_1",
        # "sirq_vruntime_iodepth_1_1/48_64_16_1_1_1_0_0_1_2",
        # "sirq_vruntime_iodepth_1_1/48_64_16_1_1_1_0_0_1_3",
        # "sirq_vruntime_iodepth_1_1/48_64_24_1_1_1_0_0_1_0",
        # "sirq_vruntime_iodepth_1_1/48_64_24_1_1_1_0_0_1_1",
        # "sirq_vruntime_iodepth_1_1/48_64_24_1_1_1_0_0_1_2",
        # "sirq_vruntime_iodepth_1_1/48_64_24_1_1_1_0_0_1_3",

        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_5",
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_6",
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_7",
        "sirq_vruntime_iodepth_2_1/48_64_32_1_1_1_0_0_1_8",
    ]

    n_threads = [
        48, 48, 48, 48,
        48, 48, 48, 48,
        48, 48, 48, 48,
        48, 48, 48, 48,
    ]

    labels = [
        # "sirq_vruntime_48_1_0",
        # "sirq_vruntime_48_1_1",
        # "sirq_vruntime_48_1_2",
        # "sirq_vruntime_48_1_3",
        # "sirq_vruntime_48_8_0",
        # "sirq_vruntime_48_8_1",
        # "sirq_vruntime_48_8_2",
        # "sirq_vruntime_48_8_3",
        # "sirq_vruntime_48_16_0",
        # "sirq_vruntime_48_16_1",
        # "sirq_vruntime_48_16_2",
        # "sirq_vruntime_48_16_3",
        # "sirq_vruntime_48_24_0",
        # "sirq_vruntime_48_24_1",
        # "sirq_vruntime_48_24_2",
        # "sirq_vruntime_48_24_3",
        "sirq_high_latency_sample_32_0",
        "sirq_high_latency_sample_32_1",
        "sirq_high_latency_sample_32_2",
        "sirq_high_latency_sample_32_3",
    ]


    for index, experiment, n_thread, label in zip(range(len(experiments)), experiments, n_threads, labels):
        experiment_dir = os.path.join(result_dir, experiment)
        threads_info = parse_all_thread_info(experiment_dir, n_thread)
        threads_info = parse_netfilter(threads_info, experiment_dir)
        threads_info = parse_vruntime(threads_info, experiment_dir)
        for thread in threads_info:
            print(thread)

        # # Draw relative vruntime for client and server

        # client_normed_vruntimes = [[] for _ in range(n_thread//2)]
        # server_normed_vruntimes = [[] for _ in range(n_thread//2)]

        # for t in range(len(threads_info[0].server_vruntime)):
        #     vruntime_clients = [thread.client_vruntime[t] for thread in threads_info if thread.client_core == 32]
        #     vruntime_servers = [thread.server_vruntime[t] for thread in threads_info if thread.server_core == 32]
            
        #     normed_clients = norm_vruntime(vruntime_clients, base_value=1)
        #     normed_servers = norm_vruntime(vruntime_servers, base_value=1)
        #     for i in range(n_thread//2):
        #         client_normed_vruntimes[i].append(normed_clients[i])
        #         server_normed_vruntimes[i].append(normed_servers[i])

        # # max_client_vruntime_last = max([normed_clients[-1] for normed_clients in client_normed_vruntimes])*1.1
        # # max_server_vruntime_last = max([normed_servers[-1] for normed_servers in server_normed_vruntimes])*1.1

        # client_lines = []
        # server_lines = []

        # plt.figure(figsize=(6, 6*0.618))
        # for i in range(n_thread//2):
        #     plt.plot(range(300), client_normed_vruntimes[i], color=colors[i % len(colors)], linestyle='--')
        #     client_lines.append((i, client_normed_vruntimes[i][-1]))
        # client_lines.sort(key=lambda x: x[1])
        # # for rank, (i, _) in enumerate(client_lines):
        # #     plt.text(310, rank* max_client_vruntime_last/(n_thread//2), f"{i}", color=colors[i % len(colors)], fontsize=10,
        # #              path_effects=[path_effects.withStroke(linewidth=1, foreground="black")])
        # #     # draw a line to connect the last point of client_normed_vruntimes to the text
        # #     plt.plot([299, 310], [client_normed_vruntimes[i][-1], rank* max_client_vruntime_last/(n_thread//2)], color="black", linewidth=0.5)
        # # plt.ylim(0, max_client_vruntime_last)
        # plt.tight_layout()
        # plt.savefig(f"client_vruntime_{label}.pdf")
        # plt.close()

        # plt.figure(figsize=(6, 6*0.618))
        # for i in range(n_thread//2):
        #     plt.plot(range(300), server_normed_vruntimes[i], color=colors[i % len(colors)], linestyle='--')
        #     server_lines.append((i, server_normed_vruntimes[i][-1]))
        # server_lines.sort(key=lambda x: x[1])
        # # for rank, (i, _) in enumerate(server_lines):
        # #     plt.text(310, rank* max_server_vruntime_last/(n_thread//2), f"{i}", color=colors[i % len(colors)], fontsize=10,
        # #              path_effects=[path_effects.withStroke(linewidth=1, foreground="black")])
        # #     # draw a line to connect the last point of server_normed_vruntimes to the text
        # #     plt.plot([299, 310], [server_normed_vruntimes[i][-1], rank* max_server_vruntime_last/(n_thread//2)], color="black", linewidth=0.5)
        # # plt.ylim(0, max_server_vruntime_last)
        # plt.tight_layout()
        # plt.savefig(f"server_vruntime_{label}.pdf")
        # plt.close()

        # # For each thread, calculate the frequency of client and server's high latency ts, and plot the frequency vs value for each thread

        interested_threads = [thread for thread in threads_info if thread.client_core == 96]

        # plt.figure(figsize=(6, 6*0.618))
        # for thread in interested_threads:
        #     plt.scatter(thread.client_high_rx_sched_ts, thread.client_high_rx_sched, color=colors[(thread.port-10024) % len(colors)], marker='o')
        # plt.ylabel("rx_sched >800 (us)")
        # plt.tight_layout()
        # plt.savefig(f"client_high_lat_samples_{label}.pdf")

        # plt.figure(figsize=(6, 6*0.618))
        # for thread in interested_threads:
        #     plt.scatter(thread.server_high_rx_sched_ts, thread.server_high_rx_sched, color=colors[(thread.port-10024) % len(colors)], marker='o')
        # plt.ylabel("rx_sched >800 (us)")
        # plt.tight_layout()
        # plt.savefig(f"server_high_lat_samples_{label}.pdf")

        server_throughput = [thread.thpt/1e3 for thread in interested_threads]
        client_throughput = [thread.thpt/1e3 for thread in interested_threads]

        plt.figure(figsize=(4, 3*0.618))
        plt.bar(range(len(interested_threads)), server_throughput, color=colors[:len(interested_threads)])
        plt.ylabel("Throughput (kIOPS)")
        plt.xticks(range(len(interested_threads)), [f"{thread.port - 10024}" for thread in interested_threads], rotation=45)
        plt.tight_layout()
        plt.savefig(f"server_throughput_{label}.pdf")

        plt.figure(figsize=(4, 3*0.618))
        plt.bar(range(len(interested_threads)), client_throughput, color=colors[:len(interested_threads)])
        plt.ylabel("Throughput (kIOPS)")
        plt.xticks(range(len(interested_threads)), [f"{thread.port - 10024}" for thread in interested_threads], rotation=45)
        plt.tight_layout()
        plt.savefig(f"client_throughput_{label}.pdf")