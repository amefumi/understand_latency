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
        self.client_pid = client_pid
        self.client_core = client_core
        self.client_softirq_packets = client_softirq_packets
        self.server_pid = server_pid
        self.server_core = server_core
        self.server_softirq_packets = server_softirq_packets
        self.thpt = thpt
        self.latency = latency
        self.server_vruntime = []
        self.normed_server_vruntime = []
        self.client_vruntime = []
        self.normed_client_vruntime = []
        self.server_on_rq = []
        self.client_on_rq = []
        self.client_abs_vruntime = 0
        self.server_abs_vruntime = 0
        self.client_cache_reference = 0
        self.client_cache_misses = 0
        self.client_cache_miss_rate = 0
        self.client_cache_miss_rate_total = 0
        self.server_cache_reference = 0
        self.server_cache_misses = 0
        self.server_cache_miss_rate = 0
        self.server_cache_miss_rate_total = 0

    def __str__(self):
        return (f"Port: {self.port}, Client: {self.client_pid}@{self.client_core}, "
                f"C#Packets: {self.client_softirq_packets}, "
                f"Server: {self.server_pid}@{self.server_core}, "
                f"S#Packets: {self.server_softirq_packets}, "
                f"Throughput: {self.thpt}, Latency: {self.latency}, "
                f"#C_vruntime: {len(self.client_vruntime)}, #S_vruntime: {len(self.server_vruntime)}, "
                f"#C_on_rq: {len(self.client_on_rq)}, #S_on_rq: {len(self.server_on_rq)}, "
                f"#C_abs_vruntime: {self.client_abs_vruntime}, #S_abs_vruntime: {self.server_abs_vruntime}, "
                f"#C_cache: {self.client_cache_reference}*{self.client_cache_miss_rate*100:.2f}%, "
                f"#S_cache: {self.server_cache_reference}*{self.server_cache_miss_rate*100:.2f}%")

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

    # Sort thread by port number
    threads_info.sort(key=lambda x: x.port)

    return threads_info


def parse_netfilter_log(log_path):
    with open(log_path, "r") as log:
        lines = log.readlines()
        softirq_packets = {}
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
            if "Core:" in line and "PIDs" in line and counts < NETFILTER_COUNT:  # TODO: The count mechanism is not actually working here
                start_index = line.split().index("PIDs:")
                pid_items = [int(item) for item in line.split()[start_index + 1:]]
                count_line = lines[line_index + 1]
                start_index = count_line.split().index("Counts:")
                count_items = [int(item) for item in count_line.split()[start_index + 1:]]
                for pid, count in zip(pid_items, count_items):
                    if pid in softirq_packets:
                        softirq_packets[pid] += count
                    else:
                        softirq_packets[pid] = count
                line_index += 2
            else:
                line_index += 1
    return softirq_packets


def parse_cache(threads_info, client_cache_path, server_cache_path):
    ref_re = re.compile(
        r'(?P<thread>\S+)\s+(?P<refs>[\d,]+)\s+cache-references'
    )
    miss_re = re.compile(
        r'(?P<thread>\S+)\s+(?P<misses>[\d,]+)\s+cache-misses.*?#\s*(?P<rate>[\d.]+)\s*%'
    )
    
    with open(client_cache_path, "r") as client_log:
        lines = client_log.readlines()
        for line in lines:
            ref_match = ref_re.search(line)
            miss_match = miss_re.search(line)
            if ref_match:
                thread_name = ref_match.group("thread")
                refs = int(ref_match.group("refs").replace(",", ""))
                for thread in threads_info:
                    if f"netdriver_test_-{thread.client_pid}" == thread_name:
                        thread.client_cache_reference = refs
            if miss_match:
                thread_name = miss_match.group("thread")
                misses = int(miss_match.group("misses").replace(",", ""))
                miss_rate = float(miss_match.group("rate")) / 100.0
                for thread in threads_info:
                    if f"netdriver_test_-{thread.client_pid}" == thread_name:
                        thread.client_cache_misses = misses
                        thread.client_cache_miss_rate_total = miss_rate

    with open(server_cache_path, "r") as server_log:
        lines = server_log.readlines()
        for line in lines:
            ref_match = ref_re.search(line)
            miss_match = miss_re.search(line)
            if ref_match:
                thread_name = ref_match.group("thread")
                refs = int(ref_match.group("refs").replace(",", ""))
                for thread in threads_info:
                    if f"pingpong_server-{thread.server_pid}" == thread_name:
                        thread.server_cache_reference = refs
            if miss_match:
                thread_name = miss_match.group("thread")
                misses = int(miss_match.group("misses").replace(",", ""))
                miss_rate = float(miss_match.group("rate")) / 100.0
                for thread in threads_info:
                    if f"pingpong_server-{thread.server_pid}" == thread_name:
                        thread.server_cache_misses = misses
                        thread.server_cache_miss_rate_total = miss_rate

    for thread in threads_info:
        if thread.client_cache_reference > 0:
            thread.client_cache_miss_rate = thread.client_cache_misses / thread.client_cache_reference
        else:
            thread.client_cache_miss_rate = 0
        if thread.server_cache_reference > 0:
            thread.server_cache_miss_rate = thread.server_cache_misses / thread.server_cache_reference
        else:
            thread.server_cache_miss_rate = 0
    
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
                    thread.client_on_rq.append(1 if thread.client_pid in thread_pids_on_rq else 0)
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
                    thread.server_on_rq.append(1 if thread.server_pid in thread_pids_on_rq else 0)
                line_index += 4
            else:
                line_index += 1
    
    # Normalize vruntime: normed_vruntime = vruntime - min(vruntime) + 1.
    # 1. Get vruntime at time i for all threads, find the min value (non zero) among all threads at time i.
    # 2. For each thread, normed_vruntime[i] = vruntime[i] - min_vruntime + 1 if vruntime[i] > 0 else 1
    n_times = len(threads_info[0].client_vruntime)
    for time_index in range(n_times):
        client_virtual_runtimes_non_zero = [thread.client_vruntime[time_index] for thread in threads_info if thread.client_vruntime[time_index] > 0]
        server_virtual_runtimes_non_zero = [thread.server_vruntime[time_index] for thread in threads_info if thread.server_vruntime[time_index] > 0]    
        min_client_vruntime = min(client_virtual_runtimes_non_zero) if len(client_virtual_runtimes_non_zero) > 0 else 0
        min_server_vruntime = min(server_virtual_runtimes_non_zero) if len(server_virtual_runtimes_non_zero) > 0 else 0
        for thread in threads_info:
            if thread.client_vruntime[time_index] > 0:
                normed_client_vruntime = thread.client_vruntime[time_index] - min_client_vruntime + 1
            else:
                normed_client_vruntime = 1
            thread.normed_client_vruntime.append(normed_client_vruntime)

            if thread.server_vruntime[time_index] > 0:
                normed_server_vruntime = thread.server_vruntime[time_index] - min_server_vruntime + 1
            else:
                normed_server_vruntime = 1
            thread.normed_server_vruntime.append(normed_server_vruntime)

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

def draw_single():
    plt.figure(figsize=(6, 6*0.618))
    for index, experiment in enumerate(experiments):
        experiment_dir = os.path.join(result_dir, experiment)
        total_threads = n_threads[index]

        threads_info = parse_all_thread_info(experiment_dir, total_threads)

        # Figure 0. Draw the "latency(y)-throughput(x)" scatter plot for all threads
        latency_list = [thread.latency for thread in threads_info]
        throughput_list = [thread.thpt/1e6 for thread in threads_info]
        plt.scatter(throughput_list, latency_list, color=colors[index], marker='+')
        plt.xlabel("Throughput (mIOPS)")
        plt.ylabel("Latency (us)")
        plt.ylim(bottom=0, top=10000)
        plt.xlim(0, 0.01)
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"{save_names[index]}_latency_throughput_scatter.pdf"))

        continue

        # Stage I: Parse netfilter log to get softirq packet counts
        client_netfilter_path = os.path.join(experiment_dir, f"iter_thread_client.log")
        server_netfilter_path = os.path.join(experiment_dir, f"iter_thread_server.log")

        client_softirq_packets = parse_netfilter_log(client_netfilter_path)
        server_softirq_packets = parse_netfilter_log(server_netfilter_path)

        for thread in threads_info:
            if thread.client_pid in client_softirq_packets:
                thread.client_softirq_packets = int(client_softirq_packets[thread.client_pid])
            if thread.server_pid in server_softirq_packets:
                thread.server_softirq_packets = int(server_softirq_packets[thread.server_pid])

        client_pktirq_list = [thread.client_softirq_packets/1e6 for thread in threads_info]
        server_pktirq_list = [thread.server_softirq_packets/1e6 for thread in threads_info]
        total_pktirq_list = [(thread.client_softirq_packets + thread.server_softirq_packets)/1e6 for thread in threads_info]

        # Figure 1. Scatter plot of Latency (y-axis) vs. Client SoftIRQ Packets (x-axis)
        latency_list = [thread.latency for thread in threads_info]

        plt.figure(figsize=(6, 6*0.618))
        plt.scatter(client_pktirq_list, latency_list, color=colors[0], label='Client #Packets', marker='^')
        plt.scatter(server_pktirq_list, latency_list, color=colors[1], label='Server #Packets', marker='^')
        plt.scatter(total_pktirq_list, latency_list, color=colors[2], label='Total #Packets')
        for i in range(len(latency_list)):
            plt.annotate(int(i), (client_pktirq_list[i], latency_list[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[0],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])

            plt.annotate(int(i), (server_pktirq_list[i], latency_list[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[1],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])

            plt.annotate(int(i), (total_pktirq_list[i], latency_list[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[2],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])
        plt.legend()
        plt.xlabel("# million of packets in softIRQ processing")
        plt.ylabel("P99.9 Latency (us)")
        plt.ylim(bottom=0)
        plt.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=0)
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_latency.pdf"))
        plt.close()

        # Figure 2. Scatter plot of Throughput (y-axis) vs. Client SoftIRQ Packets (x-axis)
        throughput_list = [thread.thpt/1e6 for thread in threads_info]
        plt.figure(figsize=(6, 6*0.618))
        plt.scatter(client_pktirq_list, throughput_list, color=colors[0], label='Client #Packets', marker='^')
        plt.scatter(server_pktirq_list, throughput_list, color=colors[1], label='Server #Packets', marker='^')
        plt.scatter(total_pktirq_list, throughput_list, color=colors[2], label='Total #Packets')
        for i in range(len(throughput_list)):
            plt.annotate(int(i), (client_pktirq_list[i], throughput_list[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[0],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])

            plt.annotate(int(i), (server_pktirq_list[i], throughput_list[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[1],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])

            plt.annotate(int(i), (total_pktirq_list[i], throughput_list[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[2],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])
        plt.legend()
        plt.xlabel("# million of packets in softIRQ processing")
        plt.ylabel("Throughput (mIOPS)")
        plt.ylim(bottom=0)
        plt.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=0)
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_throughput.pdf"))
        plt.close()


        # Stage II: Parse virtual runtime for threads_info for analyzing vruntime impact
        client_vruntime_path = os.path.join(experiment_dir, f"iter_thread_client.log")
        server_vruntime_path = os.path.join(experiment_dir, f"iter_thread_server.log")
        threads_info = parse_vruntime(threads_info, client_vruntime_path, server_vruntime_path)

        # Figure 3: Draw "packet-in-softirq" vs absolute vruntime increase for client and server side, each thread is a point.
        plt.figure(figsize=(6, 6*0.618))
        client_abs_vruntime_list = [thread.client_abs_vruntime for thread in threads_info if thread.client_core == 96]
        client_pkt_list_96 = [thread.client_softirq_packets/1e6 for thread in threads_info if thread.client_core == 96]
        plt.scatter(client_pkt_list_96, client_abs_vruntime_list, color=colors[0], label='Client #Packets (Core 96)', marker='^')
        for i in range(n_threads[index]//2):
            plt.annotate(int(i+n_threads[index]//2), (client_pkt_list_96[i], client_abs_vruntime_list[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[0],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])
        server_abs_vruntime_list = [thread.server_abs_vruntime for thread in threads_info if thread.server_core == 96]
        server_pkt_list_96 = [thread.server_softirq_packets/1e6 for thread in threads_info if thread.server_core == 96]
        plt.scatter(server_pkt_list_96, server_abs_vruntime_list, color=colors[1], label='Server #Packets (Core 96)', marker='^')
        for i in range(n_threads[index]//2):
            plt.annotate(int(i+n_threads[index]//2), (server_pkt_list_96[i], server_abs_vruntime_list[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[1],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])
        plt.xlabel("# million of packets in softIRQ processing")
        plt.ylabel("Absolute Vruntime Increase")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_abs_vruntime_core96.pdf"))
        plt.close()

        # Figure 4: For client and server side, draw "packet-in-softirq" vs normalized vruntime difference in last second
        client_vruntime_last = [thread.normed_client_vruntime[-1] for thread in threads_info if thread.client_core == 96]
        client_vruntime_last_normed = norm_vruntime(client_vruntime_last)
        plt.figure(figsize=(6, 6*0.618))
        plt.scatter(client_pkt_list_96, client_vruntime_last_normed, color=colors[0], label='Client #Packets (Core 96)', marker='^')
        for i in range(n_threads[index]//2):
            plt.annotate(int(i+n_threads[index]//2), (client_pkt_list_96[i], client_vruntime_last_normed[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[0],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])
        server_vruntime_last = [thread.normed_server_vruntime[-1] for thread in threads_info if thread.server_core == 96]
        server_vruntime_last_normed = norm_vruntime(server_vruntime_last)
        plt.scatter(server_pkt_list_96, server_vruntime_last_normed, color=colors[1], label='Server #Packets (Core 96)', marker='^')
        for i in range(n_threads[index]//2):
            plt.annotate(int(i+n_threads[index]//2), (server_pkt_list_96[i], server_vruntime_last_normed[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[1],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])
        plt.xlabel("# million of packets in softIRQ processing")
        plt.ylabel("Normalized last vruntime")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_last_vruntime_core96.pdf"))
        plt.close()

        # Figure 5. For client and server side, draw "packet-in-softirq" vs starting vruntime
        client_vruntime_start = [thread.normed_client_vruntime[0] for thread in threads_info if thread.client_core == 96]
        client_vruntime_start_normed = norm_vruntime(client_vruntime_start)
        plt.figure(figsize=(6, 6*0.618))
        plt.scatter(client_pkt_list_96, client_vruntime_start_normed, color=colors[0], label='Client #Packets (Core 96)', marker='^')
        for i in range(n_threads[index]//2):
            plt.annotate(int(i+n_threads[index]//2), (client_pkt_list_96[i], client_vruntime_start_normed[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[0],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])
        server_vruntime_start = [thread.normed_server_vruntime[5] for thread in threads_info if thread.server_core == 96]
        server_vruntime_start_normed = norm_vruntime(server_vruntime_start)
        plt.scatter(server_pkt_list_96, server_vruntime_start_normed, color=colors[1], label='Server #Packets (Core 96)', marker='^')
        for i in range(n_threads[index]//2):
            plt.annotate(int(i+n_threads[index]//2), (server_pkt_list_96[i], server_vruntime_start_normed[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[1],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])
        plt.xlabel("# million of packets in softIRQ processing")
        plt.ylabel("Normalized starting vruntime")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_start_vruntime_core96.pdf"))
        plt.close()

        # Stage III: cache performance
        client_cache_path = os.path.join(experiment_dir, f"cache_client.log")
        server_cache_path = os.path.join(experiment_dir, f"cache_server.log")
        threads_info = parse_cache(threads_info, client_cache_path, server_cache_path)

        for thread in threads_info:
            print(thread)
        
        # Figure 6. For client and server side, draw "packet-in-irq" vs cache reference count
        plt.figure(figsize=(6, 6*0.618))
        client_pkt_list_96 = [thread.client_softirq_packets/1e6 for thread in threads_info if thread.client_core == 96]
        client_cache_reference_list = [thread.client_cache_reference for thread in threads_info if thread.client_core == 96]
        plt.scatter(client_pkt_list_96, client_cache_reference_list, color=colors[0], label='Client Packet-in-IRQ (Core 96)', marker='^')
        for i in range(n_threads[index]//2):
            plt.annotate(int(i+n_threads[index]//2), (client_pkt_list_96[i], client_cache_reference_list[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[0],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])
        server_pkt_list_96 = [thread.server_softirq_packets/1e6 for thread in threads_info if thread.server_core == 96]
        server_cache_reference_list = [thread.server_cache_reference for thread in threads_info if thread.server_core == 96]
        plt.scatter(server_pkt_list_96, server_cache_reference_list, color=colors[1], label='Server Packet-in-IRQ (Core 96)', marker='^')
        for i in range(n_threads[index]//2):
            plt.annotate(int(i+n_threads[index]//2), (server_pkt_list_96[i], server_cache_reference_list[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=4, color=colors[1],
                         path_effects=[path_effects.Stroke(linewidth=1, foreground='white'), path_effects.Normal()])
        plt.xlabel("# million of packets in softIRQ")
        plt.ylabel("Cache Reference Count")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_cache_pktirq_vs_reference.pdf"))
        plt.close()

        # # Figure 3, 4: For each thread with core=96, plot the vruntime on client and server side. x-axis is the index, y-axis is the normalized vruntime. Draw all threads in one single figure.
        # plt.figure(figsize=(6, 6*0.618))
        # for i, thread in enumerate(threads_info):
        #     if thread.client_core == 96:
        #         plt.plot(thread.normed_client_vruntime, label=f'Client Thread {i} (Port {thread.port})', color=colors[i%40], linestyle='-')
        # plt.xlabel("Time (second)")
        # plt.ylabel("Normalized Vruntime")
        # # plt.yscale("log")
        # plt.tight_layout()
        # plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_client_vruntime_core96.pdf"))
        # plt.close()

        # plt.figure(figsize=(6, 6*0.618))
        # for i, thread in enumerate(threads_info):
        #     if thread.server_core == 96:
        #         plt.plot(thread.client_vruntime[20:], label=f'Client Thread {i} (Port {thread.port})', color=colors[i%40], linestyle='-')
        # plt.xlabel("Time (second)")
        # plt.ylabel("Vruntime")
        # # plt.yscale("log")
        # plt.tight_layout()
        # plt.savefig(os.path.join(result_dir, f"netfilter_{save_names[index]}_client_abs_vruntime_core96.pdf"))
        # plt.close()


def draw_combined():

    plt.figure(figsize=(6, 6*0.618))

    for index, experiment in enumerate(experiments):
        experiment_dir = os.path.join(result_dir, experiment)
        total_threads = n_threads[index]

        threads_info = parse_all_thread_info(experiment_dir, total_threads)

        client_netfilter_path = os.path.join(experiment_dir, f"filter_client.log")
        server_netfilter_path = os.path.join(experiment_dir, f"filter_server.log")

        client_softirq_packets = parse_netfilter_log(client_netfilter_path)
        server_softirq_packets = parse_netfilter_log(server_netfilter_path)

        for thread in threads_info:
            if thread.client_pid in client_softirq_packets:
                thread.client_softirq_packets = int(client_softirq_packets[thread.client_pid])
            if thread.server_pid in server_softirq_packets:
                thread.server_softirq_packets = int(server_softirq_packets[thread.server_pid])

        total_pktirq_list = [(thread.client_softirq_packets + thread.server_softirq_packets)/1e6 for thread in threads_info]
        latency_list = [thread.latency for thread in threads_info]
        plt.scatter(total_pktirq_list, latency_list, color=colors[index*2], label=f'{label_names[index]}', marker='o')
    plt.legend()
    plt.xlabel("# million of packets in softIRQ processing")
    plt.ylabel("P99.9 Latency (us)")
    plt.ylim(bottom=0)
    plt.xlim(left=0)
    plt.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=0)
    plt.tight_layout()
    plt.savefig(os.path.join(result_dir, f"netfilter_combined_latency_{save_name}.pdf"))
    plt.close()

    plt.figure(figsize=(6, 6*0.618))

    for index, experiment in enumerate(experiments):
        experiment_dir = os.path.join(result_dir, experiment)
        total_threads = n_threads[index]

        threads_info = parse_all_thread_info(experiment_dir, total_threads)

        client_netfilter_path = os.path.join(experiment_dir, f"filter_client.log")
        server_netfilter_path = os.path.join(experiment_dir, f"filter_server.log")

        client_softirq_packets = parse_netfilter_log(client_netfilter_path)
        server_softirq_packets = parse_netfilter_log(server_netfilter_path)

        for thread in threads_info:
            if thread.client_pid in client_softirq_packets:
                thread.client_softirq_packets = int(client_softirq_packets[thread.client_pid])
            if thread.server_pid in server_softirq_packets:
                thread.server_softirq_packets = int(server_softirq_packets[thread.server_pid])

        total_pktirq_list = [(thread.client_softirq_packets + thread.server_softirq_packets)/1e6 for thread in threads_info]
        throughput_list = [thread.thpt/1e6 for thread in threads_info]
        plt.scatter(total_pktirq_list, throughput_list, color=colors[index*2], label=f'{label_names[index]}', marker='o')

    plt.legend()
    plt.xlabel("# million of packets in softIRQ processing")
    plt.ylabel("Throughput (mIOPS)")
    plt.ylim(bottom=0, top=0.015)
    plt.xlim(left=0)
    plt.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=0)
    plt.tight_layout()
    plt.savefig(os.path.join(result_dir, f"netfilter_combined_throughput_{save_name}.pdf"))
    plt.close()



if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"
    experiments = [
        "airq_breakdown_1_1/52_64_1_1_1_1_0_0_1_3",
        "nirq_breakdown_1_1/48_64_1_1_1_1_0_0_1_3",
    ]

    save_names = [
        "airq_breakdown",
        "nirq_breakdown",
    ]

    # experiments = [
    #     "nirq_pktirq_1_1/48_64_1_1_1_1_0_0_1_3",
    #     "airq_pktirq_1_1/52_64_1_1_1_1_0_0_1_3",
    # ]
    # label_names = [
    #     "Linux",
    #     "Linux + cIRQa"
    # ]
    # save_name = "3"

    n_threads = [52, 48]
    NETFILTER_COUNT = 12

    draw_single()

    # draw_combined()