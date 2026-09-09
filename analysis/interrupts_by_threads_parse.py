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
    path = "/data1/projects/latency/sirq_heter_1_1/48_64_1_1_1_1_0_0_1_0"
    parse_by_path(path)