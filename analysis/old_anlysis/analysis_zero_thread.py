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


def parse_thread_pids(experiment_dir):
    client_pids = []
    server_pids = []
    client_log_path = os.path.join(experiment_dir, f"client.log")
    server_log_path = os.path.join(experiment_dir, f"server.log")
    with open(client_log_path, "r") as f:
        lines = f.readlines()
        for line in lines:
            items = line.split()
            if len(items) < 5:
                continue
            pid = int(items[4])
            if pid not in client_pids:
                client_pids.append(pid)

    with open(server_log_path, "r") as f:
        lines = f.readlines()
        for line in lines:
            items = line.split()
            if len(items) < 5:
                continue
            pid = int(items[4])
            if pid not in server_pids:
                server_pids.append(pid)

    return client_pids, server_pids


def parse_netfilter_log(log_path):
    pktirq_core_32 = []
    pktirq_core_64 = []

    with open(log_path, "r") as f:
        lines = f.readlines()
        line_index = 0
        while line_index < len(lines):
            if "Core:32 PIDs:" in lines[line_index]:
                items = lines[line_index].split()
                pid_index = items.index("PIDs:") + 1
                pids = [int(x) for x in items[pid_index:]]
                pktirq_items = lines[line_index + 1].split()
                pktirq_index = pktirq_items.index("Counts:") + 1
                pktirqs = [int(x) for x in pktirq_items[pktirq_index:]]
                pktirq_core_32_dict = {}
                for pid, pktirq in zip(pids, pktirqs):
                    if pid in pktirq_core_32_dict:
                        pktirq_core_32_dict[pid] += pktirq
                    else:
                        pktirq_core_32_dict[pid] = pktirq
                line_index += 2
                pktirq_core_32.append(pktirq_core_32_dict)

            elif "Core:96 PIDs:" in lines[line_index]:
                items = lines[line_index].split()
                pid_index = items.index("PIDs:") + 1
                pids = [int(x) for x in items[pid_index:]]
                pktirq_items = lines[line_index + 1].split()
                pktirq_index = pktirq_items.index("Counts:") + 1
                pktirqs = [int(x) for x in pktirq_items[pktirq_index:]]
                pktirq_core_64_dict = {}
                for pid, pktirq in zip(pids, pktirqs):
                    if pid in pktirq_core_64_dict:
                        pktirq_core_64_dict[pid] += pktirq
                    else:
                        pktirq_core_64_dict[pid] = pktirq
                pktirq_core_64.append(pktirq_core_64_dict)
                line_index += 2
            else:
                line_index += 1

    return pktirq_core_32, pktirq_core_64


def draw_single():

    for index, experiment in enumerate(experiments):
        experiment_dir = os.path.join(result_dir, experiment)

        client_netfilter_path = os.path.join(experiment_dir, f"iter_thread_client.log")
        server_netfilter_path = os.path.join(experiment_dir, f"iter_thread_server.log")

        client_32, client_96 = parse_netfilter_log(client_netfilter_path)
        server_32, server_96 = parse_netfilter_log(server_netfilter_path)

        client_pids, server_pids = parse_thread_pids(experiment_dir)

        client_32_results = {
            "client_pid": [],
            "zero_pid": [],
            "other_pid": [],
        }

        client_96_results = {
            "client_pid": [],
            "zero_pid": [],
            "other_pid": [],
        }

        server_32_results = {
            "server_pid": [],
            "zero_pid": [],
            "other_pid": [],
        }

        server_96_results = {
            "server_pid": [],
            "zero_pid": [],
            "other_pid": [],
        }

        # For each time slice in client_32, client_96, server_32, server_96, accumulate pktirq counts according to pid type:
        # 1. server/client pid: the pid belongs to the server/client threads
        # 2. zero pid: pid is 0
        # 3. other pid: pid is neither server/client pid nor 0
        for time_slice in client_32:
            client_32_results["client_pid"].append(
                sum([time_slice[pid] for pid in time_slice if pid in client_pids])
            )
            client_32_results["zero_pid"].append(
                time_slice[0] if 0 in time_slice else 0
            )
            client_32_results["other_pid"].append(
                sum([time_slice[pid] for pid in time_slice if pid not in client_pids and pid != 0])
            )
        
        for time_slice in client_96:
            client_96_results["client_pid"].append(
                sum([time_slice[pid] for pid in time_slice if pid in client_pids])
            )
            client_96_results["zero_pid"].append(
                time_slice[0] if 0 in time_slice else 0
            )
            client_96_results["other_pid"].append(
                sum([time_slice[pid] for pid in time_slice if pid not in client_pids and pid != 0])
            )

        for time_slice in server_32:
            server_32_results["server_pid"].append(
                sum([time_slice[pid] for pid in time_slice if pid in server_pids])
            )
            server_32_results["zero_pid"].append(
                time_slice[0] if 0 in time_slice else 0
            )
            server_32_results["other_pid"].append(
                sum([time_slice[pid] for pid in time_slice if pid not in server_pids and pid != 0])
            )

        for time_slice in server_96:
            server_96_results["server_pid"].append(
                sum([time_slice[pid] for pid in time_slice if pid in server_pids])
            )
            server_96_results["zero_pid"].append(
                time_slice[0] if 0 in time_slice else 0
            )
            server_96_results["other_pid"].append(
                sum([time_slice[pid] for pid in time_slice if pid not in server_pids and pid != 0])
            )
        
        # Plot the results for client:
        plt.figure(figsize=(6, 6*0.618))
        plt.plot(client_32_results["client_pid"], label="Clients, Core 32", color="royalblue")
        plt.plot(client_32_results["zero_pid"], label="Idle, Core 32", color="orange")
        plt.plot(client_32_results["other_pid"], label="Other, Core 32", color="green")
        plt.plot(client_96_results["client_pid"], label="Clients, Core 96", color="deepskyblue", linestyle="--")
        plt.plot(client_96_results["zero_pid"], label="Idle, Core 96", color="darkorange", linestyle="--")
        plt.plot(client_96_results["other_pid"], label="Other, Core 96", color="limegreen", linestyle="--")
        plt.xlabel("Time (10s)")
        plt.ylabel("#Packet Processed in softIRQ")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"{save_names[index]}_client_pktirq_distribution.pdf"))
        plt.close()

        # Plot the results for server:
        plt.figure(figsize=(6, 6*0.618))
        plt.plot(server_32_results["server_pid"], label="Servers, Core 32", color="royalblue")
        plt.plot(server_32_results["zero_pid"], label="Idle, Core 32", color="orange")
        plt.plot(server_32_results["other_pid"], label="Other, Core 32", color="green")
        plt.plot(server_96_results["server_pid"], label="Servers, Core 96", color="deepskyblue", linestyle="--")
        plt.plot(server_96_results["zero_pid"], label="Idle, Core 96", color="darkorange", linestyle="--")
        plt.plot(server_96_results["other_pid"], label="Other, Core 96", color="limegreen", linestyle="--")
        plt.xlabel("Time (10s)")
        plt.ylabel("#Packet Processed in softIRQ")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"{save_names[index]}_server_pktirq_distribution.pdf"))
        plt.close()

if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"
    experiments = [
        "airq_pktirq_allthread_1_1/52_64_1_1_1_1_0_0_1_0",
    ]

    save_names = [
        "airq_pktirq_allthread_0",
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

    n_threads = [52]
    NETFILTER_COUNT = 12

    draw_single()

    # draw_combined()