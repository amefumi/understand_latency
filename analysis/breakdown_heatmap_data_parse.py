#!/usr/bin/env python3
import os
import re
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.font_manager as fm

fm.fontManager.addfont("/home/ame/GillSans.ttc")

# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.family": "Gill Sans",
    "font.size": 14,
    "font.weight": "bold",
    "axes.labelweight": "bold",
    "axes.titleweight": "bold",

    # sizes
    "axes.titlesize": 14,
    "axes.labelsize": 14,
    "xtick.labelsize": 14,
    "ytick.labelsize": 8,

    # lines and markers
    "lines.linewidth": 2.5,
    "lines.markersize": 4,
    
    # thick frame and ticks
    "axes.linewidth": 2,
    "xtick.major.width": 2,
    "xtick.major.size": 4,
    "ytick.major.width": 2,
    "ytick.major.size": 4,
    "xtick.minor.width": 1,
    "ytick.minor.width": 1,
    "xtick.direction": "in",
    "ytick.direction": "in",

    # grid
    "grid.linestyle": ":",
    "grid.linewidth": 2,
    "grid.color": "black",
    "grid.alpha": 1,
    "axes.axisbelow": True,
})

def server_breakdown_parser(breakdown_log_path, n_thread):
    with open(breakdown_log_path, "r") as file:
        lines = file.readlines()

    pattern = re.compile(r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) napi: ([0-9]+) gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) wakeup: ([0-9]+) data copy: ([0-9]+) return: ([0-9]+) -- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) tcp: ([0-9]+) ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+).*")

    samples = {}
    count = {}

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 23:
                _, port, rx_hw, rx_alloc, rx_irq, rx_napi, rx_gro, rx_ip, rx_tcp, rx_read, rx_sleep, rx_ready, rx_wake_up, rx_data_copy, rx_return, tx_alloc, tx_write, tx_data_copy, tx_tcp, tx_ip, tx_queue, tx_xmit, tx_finish = timestamps

                if port not in samples:
                    samples[port] = []
                    count[port] = 0

                if not count[port] < 2: # We skip first two packets to avoid zero time stamp issue.
                    samples[port].append({
                        'rx_hw': rx_hw,
                        'rx_alloc': rx_alloc,
                        'rx_irq': rx_irq,
                        'rx_napi': rx_napi,
                        'rx_gro': rx_gro,
                        'rx_ip': rx_ip,
                        'rx_tcp': rx_tcp,
                        'rx_read': rx_read,
                        'rx_sleep': rx_sleep,
                        'rx_ready': rx_ready,
                        'rx_wake_up': rx_wake_up,
                        'rx_data_copy': rx_data_copy,
                        'rx_return': rx_return,
                        'tx_alloc': tx_alloc,
                        'tx_write': tx_write,
                        'tx_data_copy': tx_data_copy,
                        'tx_tcp': tx_tcp,
                        'tx_ip': tx_ip,
                        'tx_queue': tx_queue,
                        'tx_xmit': tx_xmit,
                        'tx_finish': tx_finish,
                    })
                count[port] += 1  # We skip the first two packets for each port to avoid initialization effects 

    latencies = {}

    for port, port_samples in samples.items():
        latencies[port] = []
        for ts in port_samples:
            if ts['rx_ready'] >  ts['rx_wake_up']:
                ts['rx_wake_up'] = ts['rx_ready']

            latencies[port].append({
                'rx_hw': ts['rx_hw'],
                'rx_irq': ts['rx_alloc'] - ts['rx_hw'],
                'rx_napi': ts['rx_gro'] - ts['rx_alloc'],
                'rx_ip': ts['rx_tcp'] - ts['rx_gro'],
                'rx_tcp': ts['rx_ready'] - ts['rx_tcp'],
                'rx_sched': ts['rx_data_copy'] - ts['rx_ready'],
                'rx_data_copy': ts['rx_return'] - ts['rx_data_copy'],
                'app': ts['tx_write'] - ts['rx_return'],
                'tx_data_copy': ts['tx_tcp'] - ts['tx_write'],
                'tx_tcp': ts['tx_ip'] - ts['tx_tcp'],
                'tx_ip': ts['tx_queue'] - ts['tx_ip'],
                'tx_queue': ts['tx_xmit'] - ts['tx_queue'],
                'tx_xmit': ts['tx_finish'] - ts['tx_xmit'],
                'full': ts['tx_finish'] - ts['rx_hw'],
            })

    return latencies


def client_breakdown_parser(breakdown_log_path, n_thread):
    with open(breakdown_log_path, "r") as file:
        lines = file.readlines()

    pattern = re.compile(r".*source port: ([0-9]+) destination port: ([0-9]+) -- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) napi: ([0-9]+) gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) wakeup: ([0-9]+) data copy: ([0-9]+) return: ([0-9]+) -- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) tcp: ([0-9]+) ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+).*")

    samples = {}
    count = {}

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 23:
                port, _, rx_hw, rx_alloc, rx_irq, rx_napi, rx_gro, rx_ip, rx_tcp, rx_read, rx_sleep, rx_ready, rx_wake_up, rx_data_copy, rx_return, tx_alloc, tx_write, tx_data_copy, tx_tcp, tx_ip, tx_queue, tx_xmit, tx_finish = timestamps

                if port not in samples:
                    samples[port] = []
                    count[port] = 0

                if not count[port] < 2: # We skip first two packets to avoid zero time stamp issue.
                    samples[port].append({
                        'rx_hw': rx_hw,
                        'rx_alloc': rx_alloc,
                        'rx_irq': rx_irq,
                        'rx_napi': rx_napi,
                        'rx_gro': rx_gro,
                        'rx_ip': rx_ip,
                        'rx_tcp': rx_tcp,
                        'rx_read': rx_read,
                        'rx_sleep': rx_sleep,
                        'rx_ready': rx_ready,
                        'rx_wake_up': rx_wake_up,
                        'rx_data_copy': rx_data_copy,
                        'rx_return': rx_return,
                        'tx_alloc': tx_alloc,
                        'tx_write': tx_write,
                        'tx_data_copy': tx_data_copy,
                        'tx_tcp': tx_tcp,
                        'tx_ip': tx_ip,
                        'tx_queue': tx_queue,
                        'tx_xmit': tx_xmit,
                        'tx_finish': tx_finish
                    })
                count[port] += 1  # We skip the first two packets for each port to avoid initialization effects

    latencies = {}
    
    for port, port_samples in samples.items():
        latencies[port] = []
        for ts in port_samples:
            latencies[port].append({
                'rx_hw': ts['rx_hw'],
                'rx_irq': ts['rx_alloc'] - ts['rx_hw'],
                'rx_napi': ts['rx_gro'] - ts['rx_alloc'],
                'rx_ip': ts['rx_tcp'] - ts['rx_gro'],
                'rx_tcp': ts['rx_ready'] - ts['rx_tcp'],
                'rx_sched': ts['rx_data_copy'] - ts['rx_ready'],
                'rx_data_copy': ts['rx_return'] - ts['rx_data_copy'],
                'app': ts['tx_write'] - ts['rx_return'],
                'tx_data_copy': ts['tx_tcp'] - ts['tx_write'],
                'tx_tcp': ts['tx_ip'] - ts['tx_tcp'],
                'tx_ip': ts['tx_queue'] - ts['tx_ip'],
                'tx_queue': ts['tx_xmit'] - ts['tx_queue'],
                'tx_xmit': ts['tx_finish'] - ts['tx_xmit'],
                'phase_1': ts['rx_return'] - ts['rx_hw'],
                'phase_2': ts['tx_finish'] - ts['rx_return'],
                'full': ts['tx_finish'] - ts['rx_hw'],
            })

    return latencies

def combine_breakdown_e2e(client_latencies, server_latencies):
    combined_latencies = []
    for port in client_latencies.keys():
        if port in server_latencies:
            client_samples = client_latencies[port]
            server_samples = server_latencies[port]
            # NOTE: We are trying an end-to-end matching here:
            #       Sender 1 {app, ..., tx_ximit} --> Receiver 1 {rx_hw, ..., tx_xmit} --> Sender 2 {rx_hw, ..., rx_data_copy}
            #       If we need to attribute app to another part, we can change the attribution of phase_1 and phase_2 in client_breakdown_parser function later.
            num_samples = min(len(client_samples), len(server_samples))//2
            for i in range(num_samples):
                sender_1_index = i * 2
                receiver_1_index = i * 2
                sender_2_index = i * 2 + 1
                combined_latencies.append({
                    'client_app': client_samples[sender_1_index]['app']/1e3,
                    'client_tx_data_copy': client_samples[sender_1_index]['tx_data_copy']/1e3,
                    'client_tx_tcp': client_samples[sender_1_index]['tx_tcp']/1e3,
                    'client_tx_ip': client_samples[sender_1_index]['tx_ip']/1e3,
                    'client_tx_queue': client_samples[sender_1_index]['tx_queue']/1e3,
                    'client_tx_xmit': client_samples[sender_1_index]['tx_xmit']/1e3,
                    'server_rx_irq': server_samples[receiver_1_index]['rx_irq']/1e3,
                    'server_rx_napi': server_samples[receiver_1_index]['rx_napi']/1e3,
                    'server_rx_ip': server_samples[receiver_1_index]['rx_ip']/1e3,
                    'server_rx_tcp': server_samples[receiver_1_index]['rx_tcp']/1e3,
                    'server_rx_sched': server_samples[receiver_1_index]['rx_sched']/1e3,
                    'server_rx_data_copy': server_samples[receiver_1_index]['rx_data_copy']/1e3,
                    'server_app': server_samples[receiver_1_index]['app']/1e3,
                    'server_tx_data_copy': server_samples[receiver_1_index]['tx_data_copy']/1e3,
                    'server_tx_tcp': server_samples[receiver_1_index]['tx_tcp']/1e3,
                    'server_tx_ip': server_samples[receiver_1_index]['tx_ip']/1e3,
                    'server_tx_queue': server_samples[receiver_1_index]['tx_queue']/1e3,
                    'server_tx_xmit': server_samples[receiver_1_index]['tx_xmit']/1e3,
                    'client_rx_irq': client_samples[sender_2_index]['rx_irq']/1e3,
                    'client_rx_napi': client_samples[sender_2_index]['rx_napi']/1e3,
                    'client_rx_ip': client_samples[sender_2_index]['rx_ip']/1e3,
                    'client_rx_tcp': client_samples[sender_2_index]['rx_tcp']/1e3,
                    'client_rx_sched': client_samples[sender_2_index]['rx_sched']/1e3,
                    'client_rx_data_copy': client_samples[sender_2_index]['rx_data_copy']/1e3,
                    'total_full': (client_samples[sender_1_index]['phase_2']/1e3 + server_samples[receiver_1_index]['full']/1e3 + client_samples[sender_2_index]['phase_1']/1e3),
                })
    
    return combined_latencies

def heatmap_tail_parser_e2e(latencies):
    latencies.sort(key=lambda x: x['total_full'])
    tail_latencies = latencies[int(len(latencies)*0.998):]
    heatmap = np.array([
        [
            sample['client_rx_irq'],
            sample['client_rx_napi'],
            sample['client_rx_ip'],
            sample['client_rx_tcp'],
            sample['client_rx_sched'],
            sample['client_rx_data_copy'],
            sample['client_app'],
            sample['client_tx_data_copy'],
            sample['client_tx_tcp'],
            sample['client_tx_ip'],
            sample['client_tx_queue'],
            sample['client_tx_xmit'],
            sample['server_rx_irq'],
            sample['server_rx_napi'],
            sample['server_rx_ip'],
            sample['server_rx_tcp'],
            sample['server_rx_sched'],
            sample['server_rx_data_copy'],
            sample['server_app'],
            sample['server_tx_data_copy'],
            sample['server_tx_tcp'],
            sample['server_tx_ip'],
            sample['server_tx_queue'],
            sample['server_tx_xmit'],
        ] for sample in tail_latencies
    ]).T  # Transpose to get desired shape

    return heatmap


def breakdown_heatmap(runs, dim, n_thread, result_dir):
    combined_latencies = []
    for run in runs:
        breakdown_file_client = os.path.join(result_dir, f"{n_thread}_64_1_{dim}_1_1_0_0_1_{run}", f"latencies-{n_thread}.log")
        breakdown_file_server = os.path.join(result_dir, f"{n_thread}_64_1_{dim}_1_1_0_0_1_{run}", f"latencies-{n_thread}-server.log")
        client_latencies = client_breakdown_parser(breakdown_file_client, n_thread)
        server_latencies = server_breakdown_parser(breakdown_file_server, n_thread)
        combined_latencies.extend(combine_breakdown_e2e(client_latencies, server_latencies)) # in ordered, us format
    tail_latencies = heatmap_tail_parser_e2e(combined_latencies)
    return tail_latencies


if __name__ == "__main__":
    # Analysis parameters
    result_dir = "/data0/projects/latency/"
    experiments = ["sirq_pcbs_breakdown_1_1"]
    threads = [64]
    runs = [0, 1, 2, 3, 4]
    dim = 1

    # Plotting parameters
    heatmap_labels = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue','tx_xmit']*2
    heatmap_cap = 1500


    for experiment in experiments:
        for n_thread in threads:
            experiment_dir = os.path.join(result_dir, experiment)
            heatmap_path = os.path.join(experiment_dir, f"heatmap_{experiment}_{n_thread}.npy")

            tail_latencies = breakdown_heatmap(runs, dim, n_thread, experiment_dir)
            np.save(heatmap_path, tail_latencies)
            print(f"Generated breakdown heatmap for {experiment} with {n_thread} threads.")