#!/usr/bin/env python3
import os
from matplotlib import transforms
import numpy as np
from itertools import product
from statistics import stdev



if __name__ == "__main__":
    # Analysis parameters
    result_dir = "/data0/projects/latency/"
    # experiments = ["sirq_pcbs_breakdown_cores_3_1"]
    # experiments = ["sirq_pcbs_breakdown_1_1"]
    experiments = ["nirq_breakdown_1_1"]
    # experiments = ["sirq_understanding_24_1"]
    threads = [48]

    # Plotting parameters
    heatmap_labels = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue','tx_xmit']*2

    for experiment in experiments:
        for n_thread in threads:
            experiment_dir = os.path.join(result_dir, experiment)
            heatmap_path = os.path.join(experiment_dir, f"heatmap_{experiment}_{n_thread}.npy")
            # Check if processed heatmap file exists
            assert os.path.exists(heatmap_path), f"Heatmap file {heatmap_path} does not exist. Please run the breakdown analysis first."
            tail_latencies = np.load(heatmap_path)
            print(f"Loaded existing breakdown heatmap for {experiment} with {n_thread} threads.")
            rx_irq = tail_latencies[0, :]
            rx_sched = tail_latencies[4, :]
            rx_irq_2 = tail_latencies[12, :]
            rx_sched_2 = tail_latencies[16, :]

            total_irq = rx_irq + rx_irq_2
            total_rx_sched = rx_sched + rx_sched_2

            # print middle 10 values in total
            mid = len(total_irq) // 2

            print(f"P99.9 latency = {np.sum(tail_latencies[:, mid])}")

            print("Total irq at P99.9", total_irq[mid])
            print("10 total irq around P99.9:", total_irq[mid-5:mid+5])
            print("     Average:", np.mean(total_irq[mid-5:mid+5]))
            print("-------")
            print("Total rx_sched at P99.9", total_rx_sched[mid])
            print("10 total rx_sched around P99.9:", total_rx_sched[mid-5:mid+5])
            print("Average:", np.mean(total_rx_sched[mid-5:mid+5]))
