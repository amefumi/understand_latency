#!/usr/bin/env python3
import os
import numpy as np
from itertools import product


result_dir = "/data1/projects/latency"
experiments = ["sirq_iperf_bidirectional_1_1"]
# saved_file_name = "latency_throughput_40"

num_apps = [2, 4, 8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120]
flowsize = [64]
iodepth = [1]
dim = [1]
pin = [1]
permute = [1]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 1, 2]
iperf_conns = 1
total_bin = 100000

# result_dir = "/data1/projects/latency"
# experiments = ["sirq_pcbs_heter_2_1"]
# # saved_file_name = "latency_throughput_40"

# num_apps = [4, 8, 12, 16]
# flowsize = [64]
# iodepth = [1]
# dim = [0]
# pin = [1]
# permute = [1]
# hrtick = [0]
# sched = [0]
# cores = [1]
# runs = [0, 1, 2]
# total_bin = 100000

def read_histogram(file_path):
    assert os.path.exists(file_path), f"File {file_path} does not exist"
    with open(file_path, 'rb') as f:
        data = np.fromfile(f, dtype=np.uint64, count=total_bin)
    return data


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


def parse_experiment(experiment_name):

    experiment_data = np.zeros((len(num_apps), 3))
    data_index = 0

    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores)
    for n, f, i, d, p, perm, h, s, core in combinations:
        latency_bins = []
        throughput = 0

        for run in runs:
            experiment_dir = os.path.join(result_dir, experiment_name, f"{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_{iperf_conns}_{run}")
            assert os.path.exists(os.path.join(experiment_dir, "netperf-0_thpt.log")), f"Results for experiment {experiment_dir} does not exist"

            throughput_log_path = os.path.join(experiment_dir, "linux_latency") # This is not a fault though
            with open(throughput_log_path, "r") as throughput_log:
                throughput += float(throughput_log.readlines()[1].split()[0])

            latency_bin_path = os.path.join(experiment_dir, "overall_hist.bin")
            latency_bins.append(read_histogram(latency_bin_path))

        combined_hist = combine_histograms(latency_bins)
        _, latency999 = parse_histogram(combined_hist)

        throughput /= len(runs)
        throughput /= 1e6  # Convert to MIOPS

        experiment_data[data_index, :] = [f, latency999, throughput]
        data_index += 1
        # print(f"Experiment {experiment_name}, flowsize={f}, latency p999: {latency999}, throughput: {throughput}")
        print(f"{n:.5f},{latency999:.5f},{throughput:.5f}")
    
    # Save the data to a file
    # data_file = os.path.join(result_dir, experiment_name, f"{saved_file_name}.data")
    # np.savetxt(data_file, experiment_data, delimiter=',', fmt='%.5f')
    # print(f"Saved data to {data_file}")


if __name__ == "__main__":
    for experiment_name in experiments:
        parse_experiment(experiment_name)