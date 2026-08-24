#!/usr/bin/env python3
import os
import numpy as np
from itertools import product
from statistics import stdev


def get_interrupt_arr(file_path):
    result = []
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines:
            if "mlx5_comp" in line:
                elements = line.split()
                total_sum = 0
                for element in elements[1:]:
                    try:
                        number = int(element)
                        total_sum += number
                    except ValueError:
                        break
                result.append(total_sum)
    return result


def calculate_difference(array1, array2):
    difference = [a - b for a, b in zip(array1, array2)]
    return difference


def parse_experiment(experiment_name):

    experiment_data = np.zeros((len(num_apps), 3))
    data_index = 0

    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores)
    for n, f, i, d, p, perm, h, s, core in combinations:
        client_total_interrupts = 0
        server_total_interrupts = 0

        for run in runs:
            experiment_dir = os.path.join(result_dir, experiment_name, f"{n}_{f}_{i}_{d}_{p}_{perm}_{h}_{s}_{core}_{run}")
            assert os.path.exists(os.path.join(experiment_dir, "netperf-0_thpt.log")), f"Results for experiment {experiment_dir} does not exist"


            client_interrupt_0 = os.path.join(experiment_dir, "interrupt_before")
            client_interrupt_1 = os.path.join(experiment_dir, "interrupt_after")
            server_interrupt_0 = os.path.join(experiment_dir, "interrupt_before_server")
            server_interrupt_1 = os.path.join(experiment_dir, "interrupt_after_server")

            client_arr_before = get_interrupt_arr(client_interrupt_0)
            client_arr_after = get_interrupt_arr(client_interrupt_1)
            server_arr_before = get_interrupt_arr(server_interrupt_0)
            server_arr_after = get_interrupt_arr(server_interrupt_1)

            client_diff = calculate_difference(client_arr_after, client_arr_before)
            server_diff = calculate_difference(server_arr_after, server_arr_before)
            client_diff.sort(reverse=True)
            server_diff.sort(reverse=True)
            client_total_interrupts += client_diff[0] + client_diff[1] # NOTE: Qizhe uses average for top 2 interrupts, but I just use sum.
            server_total_interrupts += server_diff[0] + server_diff[1]
        experiment_data[data_index, :] = [n, client_total_interrupts/len(runs), server_total_interrupts/len(runs)]
        data_index += 1
        print(f"Experiment {experiment_name}, n={n}, client interrupts: {client_total_interrupts}, server interrupts: {server_total_interrupts}")   
    # Save the data to a file
    data_file = os.path.join(result_dir, experiment_name, f"{saved_file_name}.data")
    np.savetxt(data_file, experiment_data, delimiter=',', fmt='%.5f')
    print(f"Saved data to {data_file}")


def parse_by_path(experiment_dir):
    client_total_interrupts = 0
    server_total_interrupts = 0

    client_interrupt_0 = os.path.join(experiment_dir, "interrupt_before")
    client_interrupt_1 = os.path.join(experiment_dir, "interrupt_after")
    server_interrupt_0 = os.path.join(experiment_dir, "interrupt_before_server")
    server_interrupt_1 = os.path.join(experiment_dir, "interrupt_after_server")

    client_arr_before = get_interrupt_arr(client_interrupt_0)
    client_arr_after = get_interrupt_arr(client_interrupt_1)
    server_arr_before = get_interrupt_arr(server_interrupt_0)
    server_arr_after = get_interrupt_arr(server_interrupt_1)

    client_diff = calculate_difference(client_arr_after, client_arr_before)
    server_diff = calculate_difference(server_arr_after, server_arr_before)
    # client_diff.sort(reverse=True)
    # server_diff.sort(reverse=True)

    print(client_diff)
    print(server_diff)

    client_total_interrupts += client_diff[0] + client_diff[1] # NOTE: Qizhe uses average for top 2 interrupts, but I just use sum.
    server_total_interrupts += server_diff[0] + server_diff[1]
    print(f"Experiment {experiment_dir}, client interrupts: {client_total_interrupts}, server interrupts: {server_total_interrupts}")



if __name__ == "__main__":
    result_dir = "/data0/projects/latency/"
    # experiments = ["nirq_breakdown_1_1", "dirq_breakdown_1_1","sirq_breakdown_1_1", "sirq_pcbs_breakdown_1_1"]
    experiments = ["dim_tuning_autodim_1"]
    saved_file_name = "interrupts_dimon"

    num_apps = [44, 48, 52, 64]
    flowsize = [64]
    iodepth = [1]
    dim = [2]
    pin = [1]
    permute = [1]
    hrtick = [0]
    sched = [0]
    cores = [1]
    runs = [0, 1, 2, 3, 4]

    # for experiment_index, experiment_name in enumerate(experiments):
    #     interrupts_data = os.path.join(result_dir, experiment_name, f"{saved_file_name}.data")
    #     parse_experiment(experiment_name)

    # path = "/data0/projects/latency/nirq_eevdf_flamegraph_2_1/32_64_1_1_1_1_0_0_1_0"
    path = "/data1/projects/latency/sirq_heter_1_1/48_64_1_1_1_1_0_0_1_0"
    parse_by_path(path)