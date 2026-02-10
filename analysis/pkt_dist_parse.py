#!/usr/bin/env python3
import os
import numpy as np
from itertools import product


result_dir = "/data0/projects/latency"
experiments = ["dim_tuning_autodim_1"]
saved_file_name = "latency_throughput_autodim"

num_apps = [1, 2, 4, 8, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72]
flowsize = [64]
iodepth = [1]
dim = [2]
pin = [1]
permute = [1]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 1, 2, 3, 4]
total_bin = 96

def combine_histograms(hist_list):
    combined_hist = np.zeros(total_bin, dtype=np.uint64)
    for hist in hist_list:
        assert len(hist) == total_bin, f"Expected {total_bin} entries, got {len(hist)}"
        combined_hist += hist
    return combined_hist


def parse_histogram(histogram):
    assert len(histogram) == total_bin, f"Expected {total_bin} entries, got {len(histogram)}"
    total_samples = np.sum(histogram, dtype=np.uint64)
    cumulative = np.cumsum(histogram)
    p999_latency_us = np.searchsorted(cumulative, total_samples * 0.999)
    bins = np.arange(total_bin, dtype=np.float64)
    mean_latency_us = float(np.dot(histogram.astype(np.float64), bins) / float(total_samples))
    return mean_latency_us, p999_latency_us


def parse_experiment(experiment_dir, n_thread, iodepth, dim, runs):

    hist_client = [0] * total_bin
    hist_server = [0] * total_bin

    for run in runs:
        # /data0/projects/latency/sirq_pcbs_segdist_iodepth_1_1/2_64_64_1_1_1_0_0_1_0
        run_dir = os.path.join(experiment_dir, f"{n_thread}_64_{iodepth}_{dim}_1_1_0_0_1_{run}")
        assert os.path.exists(run_dir), f"Results for experiment {run_dir} does not exist"

        client_hist_path = os.path.join(run_dir, "pkt_dist_client.log")
        server_hist_path = os.path.join(run_dir, "pkt_dist_server.log")

        with open(client_hist_path, "r") as client_hist_file:
            client_lines = client_hist_file.readlines()

            # find the last line that has "Loading filter module", and read from the next line
            start_index = 0
            for i, line in enumerate(client_lines):
                if "Loading filter module" in line:
                    start_index = i + 1
            for line in client_lines[start_index:]:
                if "Histogram:" not in line:
                    continue
                parts = line.strip().split()
                bin_start_index = parts.index("Histogram:") + 1
                for i in range(len(parts) - bin_start_index):
                    hist_client[i] += int(parts[bin_start_index + i])
        with open(server_hist_path, "r") as server_hist_file:
            server_lines = server_hist_file.readlines()

            # find the last line that has "Loading filter module", and read from the next line
            start_index = 0
            for i, line in enumerate(server_lines):
                if "Loading filter module" in line:
                    start_index = i + 1
            for line in server_lines[start_index:]:
                if "Histogram:" not in line:
                    continue
                parts = line.strip().split()
                bin_start_index = parts.index("Histogram:") + 1
                for i in range(len(parts) - bin_start_index):
                    hist_server[i] += int(parts[bin_start_index + i])

    # Get CDF of client and server histograms, and normalize to 0-1
    cdf_client = np.cumsum(hist_client) / np.sum(hist_client)
    cdf_server = np.cumsum(hist_server) / np.sum(hist_server)

    client_save_path = os.path.join(experiment_dir, f"pkt_dist_client_{n_thread}_{iodepth}_{dim}.data")
    server_save_path = os.path.join(experiment_dir, f"pkt_dist_server_{n_thread}_{iodepth}_{dim}.data")
    with open(client_save_path, "w") as client_save_file:
        for size, count in enumerate(cdf_client):
            client_save_file.write(f"{size} {count}\n")

    with open(server_save_path, "w") as server_save_file:
        for size, count in enumerate(cdf_server):
            server_save_file.write(f"{size} {count}\n")

if __name__ == "__main__":
    experiment_dir = "/data0/projects/latency/sirq_pcbs_segdist_iodepth_1_1/"
    n_thread = 2
    iodepth = 96
    dim = 1
    runs = [0, 1, 2]
    parse_experiment(experiment_dir, n_thread, iodepth, dim, runs)