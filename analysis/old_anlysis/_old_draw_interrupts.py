#!/usr/bin/env python3
import os
import numpy as np
from itertools import product
from statistics import stdev
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.colors as mcolors
import matplotlib.patheffects as path_effects


colors = list(mcolors.TABLEAU_COLORS.keys())



def draw_interrupts_figure():
    
    plt.figure(figsize=(6, 6*0.618))

    for experiment_index, experiment_name in enumerate(draw_interrupt_series):
        interrupts_data = os.path.join(result_dir, experiment_name, f"{saved_file_name}.data")
        data = np.loadtxt(interrupts_data, delimiter=',')

        num_apps = [int(row[0]) for row in data if int(row[0]) in draw_points[experiment_index]]
        client_interrupts = [int(row[1]) for row in data if int(row[0]) in draw_points[experiment_index]]
        server_interrupts = [int(row[2]) for row in data if int(row[0]) in draw_points[experiment_index]]

        plt.plot([i for i in range(len(num_apps))], client_interrupts, marker='o', color=colors[experiment_index*2], label=f"{draw_labels[experiment_index]} - Client")
        plt.plot([i for i in range(len(num_apps))], server_interrupts, marker='s', color=colors[experiment_index*2 + 1], label=f"{draw_labels[experiment_index]} - Server")

    plt.ylabel("Number of Interrupts")
    plt.yscale("log")
    plt.legend()
    plt.grid(True)
    plt.xticks([i for i in range(len(num_apps))], num_apps, rotation=45)
    plt.tight_layout()
    figure_file = os.path.join(result_dir, "interrupts_dimoff.pdf")
    plt.savefig(figure_file)
    plt.close()

    plt.figure(figsize=(6, 6*0.618))
    for experiment_index, experiment_name in enumerate(draw_interrupt_series):
        interrupts_data = os.path.join(result_dir, experiment_name, f"{saved_file_name}.data")
        data = np.loadtxt(interrupts_data, delimiter=',')

        latency_throughput_data = os.path.join(result_dir, experiment_name, f"{save_file_name_lat_thpt}.data")
        lat_thpt_data = np.loadtxt(latency_throughput_data, delimiter=',')

        num_apps = [int(row[0]) for row in data if int(row[0]) in draw_points[experiment_index]]
        client_interrupts = [int(row[1]) for row in data if int(row[0]) in draw_points[experiment_index]]
        server_interrupts = [int(row[2]) for row in data if int(row[0]) in draw_points[experiment_index]]

        throughput = [row[2] for row in lat_thpt_data if int(row[0]) in draw_points[experiment_index]]

        client_interrupts_per_miops = [c / t if t != 0 else 0 for c, t in zip(client_interrupts, throughput)]
        server_interrupts_per_miops = [s / t if t != 0 else 0 for s, t in zip(server_interrupts, throughput)]

        plt.plot([i for i in range(len(num_apps))], client_interrupts_per_miops, marker='o', color=colors[experiment_index*2], label=f"{draw_labels[experiment_index]} - Client")
        plt.plot([i for i in range(len(num_apps))], server_interrupts_per_miops, marker='s', color=colors[experiment_index*2 + 1], label=f"{draw_labels[experiment_index]} - Server")

    plt.ylabel("Interrupts per MIOPS")
    plt.yscale("log")
    plt.legend()
    plt.grid(True)
    plt.xticks([i for i in range(len(num_apps))], num_apps, rotation=45)
    plt.tight_layout()
    figure_file = os.path.join(result_dir, "interrupts_per_miops_dimoff.pdf")
    plt.savefig(figure_file)
    plt.close()


if __name__ == "__main__":
    result_dir = "/data0/projects/latency/"
    experiments = ["nirq_breakdown_1_1", "airq_breakdown_1_1", "dirq_breakdown_1_1"]
    saved_file_name = "interrupts_dimoff"

    num_apps = [8]
    flowsize = [64]
    iodepth = [1]
    dim = [0]
    pin = [1]
    permute = [1]
    hrtick = [0]
    sched = [0]
    cores = [1]
    runs = [0, 1, 2, 3, 4]

    for experiment_index, experiment_name in enumerate(experiments):
        interrupts_dimoff_path = os.path.join(result_dir, experiment_name, "interrupts_dimoff.data")
        interrupts_dimon_path = os.path.join(result_dir, experiment_name, "interrupts_dimon.data")

        parse_experiment(experiment_name)