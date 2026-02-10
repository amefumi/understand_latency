#!/usr/bin/env python3
import re
import sys
import csv
import matplotlib.pyplot as plt
import numpy as np
    
cpu = [32, 96]

NET_DIM_RX_CQE_PROFILES = [
    (2, 256),
    (8, 128),
    (16, 64),
    (32, 64),
    (64, 64)
]

NET_DIM_TX_CQE_PROFILES = [
    (1, 128),
    (8, 128),
    (32, 128),
    (64, 128),
    (128, 128)
]

LINE_RE = re.compile(
    r"""^\s*
        (?P<task>[^\s-]+(?:/[^\s-]+|<\.\.\.>)?)  # task name (e.g. kworker/96:2 or <...>)
        -(?P<pid>\d+)\s+                         # -PID
        \[(?P<cpu>\d+)\]\s+                      # [CPU]
        [\.!NHSr\s]+                             # flags
        (?P<ts>\d+\.\d+):\s+                     # TIMESTAMP
        mlx5_cq_mod:\s+.*?                       # event name
        cqn=(?P<cqn>\d+)\s+                      # cqn=NUM
        period=(?P<period>\d+)\s+                # period=NUM
        count=(?P<count>\d+)                     # count=NUM
        """,
    re.VERBOSE
)


def analyze_dim_series(path: str):
    """Analyze DIM series from ftrace log file.
    Args:
        path (str): Path to ftrace log file.
    Returns:
        dict: Dictionary of CQN information with CQN as keys. Each value is a dictionary containing:
            - total (int): Total number of DIM decisions for this CQN.
            - cpu (int): CPU number where this CQN is located.
            - dim_items (list): List of DIM decision items, each item is a dictionary with:
                - ts (float): Timestamp of the DIM decision.
                - cq_mod (tuple): Tuple of (period, count) for the DIM decision.
            - type (str): Type of the CQN, either 'rx', 'tx', or 'UNKNOWN'.
            - cq_mod_time (dict): Dictionary with keys 'rx' and 'tx', each containing a dictionary of cq_mod to total time spent.
            - cq_mod_count (dict): Dictionary with keys 'rx' and 'tx', each containing a dictionary of cq_mod to count of occurrences.
    """

    cqn_list = {}
    first_ts = None
    last_ts = None

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "mlx5_cq_mod" not in line:
                continue
            m = LINE_RE.search(line)
            if not m:
                continue
            
            line_dict = m.groupdict()
            if first_ts is None:
                first_ts = float(line_dict["ts"])
            last_ts = float(line_dict["ts"])
            cqn = int(line_dict["cqn"])
            if cqn not in cqn_list:
                cqn_list[cqn] = {
                    "total": 0,
                    "cpu": int(line_dict["cpu"]),
                    "dim_items": [],
                }

            cqn_list[cqn]["total"] += 1
            cqn_list[cqn]["dim_items"].append({
                "ts": float(line_dict["ts"]),
                "cq_mod": (int(line_dict["period"]), int(line_dict["count"]))
            })

    # Filter out CQNs that are not on the expected CPU list
    cqn_list = {cqn: info for cqn, info in cqn_list.items() if info["cpu"] in cpu}

    # Sort dim_items by timestamp in each cqn
    for cqn in cqn_list:
        cqn_list[cqn]["dim_items"].sort(key=lambda x: x["ts"])
    
    # Judge the type of each cqn based on period and count values: if all DIMs match RX profiles, then RX; if all DIMs match TX profiles, then TX; otherwise UNKNOWN
    for cqn in cqn_list:
        dim_items = cqn_list[cqn]["dim_items"]
        is_rx = all([item["cq_mod"] in NET_DIM_RX_CQE_PROFILES for item in dim_items])
        is_tx = all([item["cq_mod"] in NET_DIM_TX_CQE_PROFILES for item in dim_items])

        assert not (is_rx and is_tx), f"CQN {cqn} matches both RX and TX profiles, which is unexpected. Too little DIM decision made?"
        if is_rx:
            cqn_list[cqn]["type"] = "rx"
        elif is_tx:
            cqn_list[cqn]["type"] = "tx"
        else:
            cqn_list[cqn]["type"] = "UNKNOWN"


    # Print the total DIM count, continued time for each cq_mod, and numbers of different cq_mod for each cqn
    for cqn in sorted(cqn_list.keys()):
        assert cqn_list[cqn]["type"] in ["rx", "tx"], f"CQN {cqn} has undefined type"

        # print(f"CQN: {cqn}, CPU: {cqn_list[cqn]['cpu']}, Total DIMs: {cqn_list[cqn]['total']}, Type: {cqn_list[cqn]['type']}")
        cqn_list[cqn]["cq_mod_time"] = {
            "rx": {cq_mod: 0.0 for cq_mod in NET_DIM_RX_CQE_PROFILES},
            "tx": {cq_mod: 0.0 for cq_mod in NET_DIM_TX_CQE_PROFILES},
        }
        cqn_list[cqn]["cq_mod_count"] = {
            "rx": {cq_mod: 0 for cq_mod in NET_DIM_RX_CQE_PROFILES},
            "tx": {cq_mod: 0 for cq_mod in NET_DIM_TX_CQE_PROFILES},
        }

        cqn_item = cqn_list[cqn]
        dim_items = cqn_item["dim_items"]

        for i in range(1, len(dim_items)):
            prev_item = dim_items[i - 1]
            curr_item = dim_items[i]
            delta_t = curr_item["ts"] - prev_item["ts"]
            cq_mod = prev_item["cq_mod"]

            cqn_list[cqn]["cq_mod_time"][cqn_list[cqn]["type"]][cq_mod] += delta_t
            cqn_list[cqn]["cq_mod_count"][cqn_list[cqn]["type"]][cq_mod] += 1

        # for the last item, we get its cq_mod, and add last_ts - last_item.ts to its time. This won't affect the count.
        last_cq_mod = dim_items[-1]["cq_mod"]
        cqn_list[cqn]["cq_mod_time"][cqn_list[cqn]["type"]][last_cq_mod] += last_ts - dim_items[-1]["ts"]

        # print("  CQ Mod Counts and Times:")
        for cq_mod in cqn_list[cqn]["cq_mod_count"][cqn_list[cqn]["type"]]:
            count = cqn_list[cqn]["cq_mod_count"][cqn_list[cqn]["type"]][cq_mod]
            total_time = cqn_list[cqn]["cq_mod_time"][cqn_list[cqn]["type"]][cq_mod]
            # if count > 0:
                # print(f"    CQ Mod {cq_mod}: Count = {count}, Total Time = {total_time:.6f} s")
    
    print(f"Analyzed DIM series from {path}, total duration: {last_ts - first_ts:.6f} s")

    return cqn_list


def parse_throughput(experiment_dir, threads, run):
    throughput = []
    for t in threads:
        path = f"{experiment_dir}/{t}_64_1_2_1_1_0_0_1_{run}/linux_latency"
        with open(path, "r") as throughput_log:
            throughput.append(float(throughput_log.readlines()[1].split()[0]))
    return throughput

def parse_latency(experiment_dir, threads, run):
    latency = []
    for t in threads:
        path = f"{experiment_dir}/{t}_64_1_2_1_1_0_0_1_{run}/latency.log"
        with open(path, "r") as latency_log:
            latency.append(float(latency_log.readlines()[0].split()[-1]))
    return latency


if __name__ == "__main__":

    # TODO: NOTE: now we only focus on a single run!!

    experiment_dir = "/data0/projects/latency/nirq_dim_ftrace+breakdown_1"
    threads = [34, 36]
    run = 0

    throughput = parse_throughput(experiment_dir, threads, run)
    latency = parse_latency(experiment_dir, threads, run)

    print("Throughput:", throughput)

    rx_counts = []
    tx_counts = []
    rx_times = {
        (2, 256): [],
        (8, 128): [],
        (16, 64): [],
        (32, 64): [],
        (64, 64): []
    }
    tx_times = {
        (1, 128): [],
        (8, 128): [],
        (32, 128): [],
        (64, 128): [],
        (128, 128): []
    }

    for t in threads:
        path = f"{experiment_dir}/{t}_64_1_2_1_1_0_0_1_{run}/dim.log"
        cqn_list = analyze_dim_series(path)

        # Aggregate counts and times
        total_rx_count = 0
        total_tx_count = 0
        for key, value in rx_times.items():
            rx_times[key].append(0.0)
        for key, value in tx_times.items():
            tx_times[key].append(0.0)

        for cqn, info in cqn_list.items():
            if info["type"] == "rx":
                total_rx_count += info["total"]
                for cq_mod, time in info["cq_mod_time"]["rx"].items():
                    rx_times[cq_mod][-1] += time
            elif info["type"] == "tx":
                total_tx_count += info["total"]
                for cq_mod, time in info["cq_mod_time"]["tx"].items():
                    tx_times[cq_mod][-1] += time
        rx_counts.append(total_rx_count)
        tx_counts.append(total_tx_count)

    # Plot 1: For left y-axis, draw RX DIM count, TX DIM counts, and total DIM count vs number of threads; for right y-axis, draw latency vs number of threads
    fig, ax1 = plt.subplots(figsize=(6, 6*0.618))
    ax2 = ax1.twinx()
    ax1.plot(threads, rx_counts, 'g-', marker='o', label='RX DIM Count')
    ax1.plot(threads, tx_counts, 'b-', marker='s', label='TX DIM Count')
    ax1.plot(threads, [rx + tx for rx, tx in zip(rx_counts, tx_counts)], 'r-', marker='^', label='Total DIM Count')
    ax2.plot(threads, latency, 'k--', marker='x', label='Latency (us)')
    ax1.set_xlabel('Number of Threads')
    ax1.set_ylabel('DIM Count')
    ax2.set_ylabel('Latency (us)')
    ax1.set_title('DIM Counts and Latency vs Number of Threads (Linux Default)')
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')
    plt.tight_layout()
    plt.savefig(f'dim_counts_{run}_txoff.pdf', dpi=300)

    # Plot 2: x-axis is thread numbers (equal spacing), for each thread number, draw a stacked bar chart of RX DIM times for different cq_mods
    fig, ax = plt.subplots(figsize=(6, 6*0.618))
    bottom_rx = np.zeros(len(threads))
    bottom_tx = np.zeros(len(threads))
    for cq_mod, times in rx_times.items():
        ax.bar(threads, times, bottom=bottom_rx, label=f'RX {cq_mod}')
        bottom_rx += np.array(times)

    ax.set_xlabel('Number of Threads')
    ax.set_ylabel('Total DIM Time (s)')
    ax.set_title('RX and TX DIM Times by CQ Mod vs Number of Threads (Linux Default)')
    ax.legend()
    plt.tight_layout()
    plt.savefig(f'dim_rx_time_{run}_txoff.pdf', dpi=300)

    # and for TX
    fig, ax = plt.subplots(figsize=(6, 6*0.618))
    for cq_mod, times in tx_times.items():
        ax.bar(threads, times, bottom=bottom_tx, label=f'TX {cq_mod}')
        bottom_tx += np.array(times)
    ax.set_xlabel('Number of Threads')
    ax.set_ylabel('Total DIM Time (s)')
    ax.set_title('TX DIM Times by CQ Mod vs Number of Threads (Linux Default)')
    ax.legend()
    plt.tight_layout()
    plt.savefig(f'dim_tx_time_{run}_txoff.pdf', dpi=300)