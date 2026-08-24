#!/usr/bin/env python3
import os
import re
import sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import matplotlib.pyplot as plt

# enum stage_invalid_bit {
	# STAGE_HIDDEN_APP_CSW_BIT = 0,
	# STAGE_SLEEP_PREPARE_CSW_BIT,
	# STAGE_SLEEP_WAKE_UP_CSW_BIT,
	# STAGE_RX_DATA_COPY_CSW_BIT,
	# STAGE_APPLICATION_CSW_BIT,
	# STAGE_TX_DATA_COPY_CSW_BIT,
	# STAGE_TX_TCP_PROC_CSW_BIT,
	# STAGE_TX_IP_PROC_CSW_BIT,
	# STAGE_TX_QUEUE_CSW_BIT,
	# STAGE_TX_XMIT_CSW_BIT,
    # STAGE_INVALID_BIT_MAX
# };

stage_bits = {
    'app_hidden': 0,
    'sleep_prepare': 1,
    'sleep_wake_up': 2,
    'rx_data_copy': 3,
    'app': 4,
    'tx_data_copy': 5,
    'tx_tcp': 6,
    'tx_ip': 7,
    'tx_queue': 8,
    'tx_xmit': 9
}


def is_valid(stage_invalid_bitmask, stage_bit):
    return (stage_invalid_bitmask & (1 << stage_bit)) == 0


def norm_list(input, offset=0):
    if len(input) == 0:
        return []
    min_val = min([v for v in input if v > 0], default=0)
    normed = []
    for v in input:
        normed.append(v - min_val + offset if v > 0 else offset)
    return normed


def server_sched_parser(breakdown_log_path):
    with open(breakdown_log_path, "r") as file:
        lines = file.readlines()

    pattern = re.compile(
        r".*source port: ([0-9]+) destination port: ([0-9]+) "
        r"-- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) "
        r"napi: ([0-9]+) gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) "
        r"read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) wakeup: ([0-9]+) "
        r"data copy: ([0-9]+) return: ([0-9]+) "
        r"-- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) "
        r"tcp: ([0-9]+) ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+) "
        r"-- last_xmit_finish: ([0-9]+) valid: ([0-9]+) "
        r"1: ([0-9]+) 2: ([0-9]+) 3: ([0-9]+) 4: ([0-9]+) 5: ([0-9]+) "
        r"6: ([0-9]+) 7: ([0-9]+) 8: ([0-9]+) 9: ([0-9]+) 10: ([0-9]+) "
        r"p0: ([0-9]+) p1: ([0-9]+) p2: ([0-9]+).* p3: ([0-9]+) "
        r"p4: ([0-9]+) p5: ([0-9]+) p6: ([0-9]+) p7: ([0-9]+) p8: ([0-9]+).*"
    )

    samples = {}
    count = {}

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 44:
                _, port, rx_hw, rx_alloc, rx_irq, rx_napi, rx_gro, rx_ip, rx_tcp, rx_read, rx_sleep,\
                rx_ready, rx_wake_up, rx_data_copy, rx_return, tx_alloc, tx_write, tx_data_copy, \
                tx_tcp, tx_ip, tx_queue, tx_xmit, tx_finish, last_xmit_finish, valid, \
                hidden_app_loss, sleep_prepare_loss, sleep_wake_up_loss, rx_data_copy_loss, app_loss, \
                tx_data_copy_loss, tx_tcp_loss, tx_ip_loss, tx_queue_loss, tx_xmit_loss, \
                p0, p1, p2, p3, p4, p5, p6, p7, p8 = timestamps

                if port not in samples:
                    samples[port] = []
                    count[port] = 0

                if not count[port] < 1000: # We skip first 2 packets to avoid zero time stamp and migration.
                    samples[port].append({
                        'rx_read_enter': rx_read,
                        'rx_sleep_enter': rx_sleep,
                        'rx_wake_up': rx_wake_up,
                        'rx_data_copy': rx_data_copy,
                        'rx_return': rx_return,
                        'tx_write': tx_write,
                        'tx_tcp': tx_tcp,
                        'tx_ip': tx_ip,
                        'tx_queue': tx_queue,
                        'tx_xmit': tx_xmit,
                        'tx_finish': tx_finish,
                        'last_xmit_finish': last_xmit_finish,
                        'valid': valid,
                        'hidden_app_loss': hidden_app_loss,
                        'sleep_prepare_loss': sleep_prepare_loss,
                        'sleep_wake_up_loss': sleep_wake_up_loss,
                        'rx_data_copy_loss': rx_data_copy_loss,
                        'app_loss': app_loss,
                        'tx_data_copy_loss': tx_data_copy_loss,
                        'tx_tcp_loss': tx_tcp_loss,
                        'tx_ip_loss': tx_ip_loss,
                        'tx_queue_loss': tx_queue_loss,
                        'tx_xmit_loss': tx_xmit_loss,
                        'rxc_l1_load_miss': p0,
                        'rxc_l2_load_miss': p1,
                        'rxc_llc_load_miss': p2,
                        'app_l1_load_miss': p3,
                        'app_l2_load_miss': p4,
                        'app_llc_load_miss': p5,
                        'txc_l1_load_miss': p6,
                        'txc_l2_load_miss': p7,
                        'txc_llc_load_miss': p8,
                    })
                count[port] += 1  # We skip the first two packets for each port to avoid initialization effects 

    accounted_latency = {}

    for port, port_samples in samples.items():
        accounted_latency[port] = {
                                    'app': [],
                                    'rx_data_copy': [],
                                    'tx_data_copy': [],
                                    'rxc_l1_load_miss': [],
                                    'rxc_l2_load_miss': [],
                                    'rxc_llc_load_miss': [],
                                    'app_l1_load_miss': [],
                                    'app_l2_load_miss': [],
                                    'app_llc_load_miss': [],
                                    'txc_l1_load_miss': [],
                                    'txc_l2_load_miss': [],
                                    'txc_llc_load_miss': [],
                                    'app_invalidated': 0,
                                    'rx_data_copy_invalidated': 0,
                                    'tx_data_copy_invalidated': 0,
                                }

        for idx, ts in enumerate(port_samples):
            if is_valid(ts['valid'], stage_bits['rx_data_copy']):
                accounted_latency[port]['rx_data_copy'].append(ts['rx_return'] - ts['rx_data_copy'] - ts['rx_data_copy_loss'])
                accounted_latency[port]['rxc_l1_load_miss'].append(ts['rxc_l1_load_miss'])
                accounted_latency[port]['rxc_l2_load_miss'].append(ts['rxc_l2_load_miss'])
                accounted_latency[port]['rxc_llc_load_miss'].append(ts['rxc_llc_load_miss'])
            else:
                accounted_latency[port]['rx_data_copy_invalidated'] += 1

            if is_valid(ts['valid'], stage_bits['app']):
                accounted_latency[port]['app'].append(ts['tx_write'] - ts['rx_return'] - ts['app_loss'])
                accounted_latency[port]['app_l1_load_miss'].append(ts['app_l1_load_miss'])
                accounted_latency[port]['app_l2_load_miss'].append(ts['app_l2_load_miss'])
                accounted_latency[port]['app_llc_load_miss'].append(ts['app_llc_load_miss'])
            else:
                accounted_latency[port]['app_invalidated'] += 1

            if is_valid(ts['valid'], stage_bits['tx_data_copy']):
                accounted_latency[port]['tx_data_copy'].append(ts['tx_tcp'] - ts['tx_write'] - ts['tx_data_copy_loss'])
                accounted_latency[port]['txc_l1_load_miss'].append(ts['txc_l1_load_miss'])
                accounted_latency[port]['txc_l2_load_miss'].append(ts['txc_l2_load_miss'])
                accounted_latency[port]['txc_llc_load_miss'].append(ts['txc_llc_load_miss'])
            else:
                accounted_latency[port]['tx_data_copy_invalidated'] += 1

    return accounted_latency 


def client_sched_parser(breakdown_log_path):
    with open(breakdown_log_path, "r") as file:
        lines = file.readlines()

    pattern = re.compile(
        r".*source port: ([0-9]+) destination port: ([0-9]+) "
        r"-- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) "
        r"napi: ([0-9]+) gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) "
        r"read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) wakeup: ([0-9]+) "
        r"data copy: ([0-9]+) return: ([0-9]+) "
        r"-- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) "
        r"tcp: ([0-9]+) ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+) "
        r"-- last_xmit_finish: ([0-9]+) valid: ([0-9]+) "
        r"1: ([0-9]+) 2: ([0-9]+) 3: ([0-9]+) 4: ([0-9]+) 5: ([0-9]+) "
        r"6: ([0-9]+) 7: ([0-9]+) 8: ([0-9]+) 9: ([0-9]+) 10: ([0-9]+) "
        r"p0: ([0-9]+) p1: ([0-9]+) p2: ([0-9]+) p3: ([0-9]+) p4: ([0-9]+) "
        r"p5: ([0-9]+) p6: ([0-9]+) p7: ([0-9]+) p8: ([0-9]+).*"
    )

    samples = {}
    count = {}

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 44:
                port, _, rx_hw, rx_alloc, rx_irq, rx_napi, rx_gro, rx_ip, rx_tcp, rx_read, rx_sleep,\
                rx_ready, rx_wake_up, rx_data_copy, rx_return, tx_alloc, tx_write, tx_data_copy, \
                tx_tcp, tx_ip, tx_queue, tx_xmit, tx_finish, last_xmit_finish, valid, \
                hidden_app_loss, sleep_prepare_loss, sleep_wake_up_loss, rx_data_copy_loss, app_loss, \
                tx_data_copy_loss, tx_tcp_loss, tx_ip_loss, tx_queue_loss, tx_xmit_loss, \
                p0, p1, p2, p3, p4, p5, p6, p7, p8 = timestamps

                if port not in samples:
                    samples[port] = []
                    count[port] = 0

                if not count[port] < 2: # We skip first two packets to avoid zero time stamp issue.
                    samples[port].append({
                        'rx_read_enter': rx_read,
                        'rx_sleep_enter': rx_sleep,
                        'rx_wake_up': rx_wake_up,
                        'rx_data_copy': rx_data_copy,
                        'rx_return': rx_return,
                        'tx_write': tx_write,
                        'tx_tcp': tx_tcp,
                        'tx_ip': tx_ip,
                        'tx_queue': tx_queue,
                        'tx_xmit': tx_xmit,
                        'tx_finish': tx_finish,
                        'last_xmit_finish': last_xmit_finish,
                        'valid': valid,
                        'hidden_app_loss': hidden_app_loss,
                        'sleep_prepare_loss': sleep_prepare_loss,
                        'sleep_wake_up_loss': sleep_wake_up_loss,
                        'rx_data_copy_loss': rx_data_copy_loss,
                        'app_loss': app_loss,
                        'tx_data_copy_loss': tx_data_copy_loss,
                        'tx_tcp_loss': tx_tcp_loss,
                        'tx_ip_loss': tx_ip_loss,
                        'tx_queue_loss': tx_queue_loss,
                        'tx_xmit_loss': tx_xmit_loss,
                        'rxc_l1_load_miss': p0,
                        'rxc_l2_load_miss': p1,
                        'rxc_llc_load_miss': p2,
                        'app_l1_load_miss': p3,
                        'app_l2_load_miss': p4,
                        'app_llc_load_miss': p5,
                        'txc_l1_load_miss': p6,
                        'txc_l2_load_miss': p7,
                        'txc_llc_load_miss': p8,
                    })
                count[port] += 1  # We skip the first two packets for each port to avoid initialization effects
    
    accounted_latency = {}
    for port, port_samples in samples.items():
        accounted_latency[port] = {
                                    'app': [],
                                    'rx_data_copy': [],
                                    'tx_data_copy': [],
                                    'rxc_l1_load_miss': [],
                                    'rxc_l2_load_miss': [],
                                    'rxc_llc_load_miss': [],
                                    'app_l1_load_miss': [],
                                    'app_l2_load_miss': [],
                                    'app_llc_load_miss': [],
                                    'txc_l1_load_miss': [],
                                    'txc_l2_load_miss': [],
                                    'txc_llc_load_miss': [],
                                    'app_invalidated': 0,
                                    'rx_data_copy_invalidated': 0,
                                    'tx_data_copy_invalidated': 0,
                                }

        for idx, ts in enumerate(port_samples):
            if is_valid(ts['valid'], stage_bits['rx_data_copy']):
                accounted_latency[port]['rx_data_copy'].append(ts['rx_return'] - ts['rx_data_copy'] - ts['rx_data_copy_loss'])
                accounted_latency[port]['rxc_l1_load_miss'].append(ts['rxc_l1_load_miss'])
                accounted_latency[port]['rxc_l2_load_miss'].append(ts['rxc_l2_load_miss'])
                accounted_latency[port]['rxc_llc_load_miss'].append(ts['rxc_llc_load_miss'])
            else:
                accounted_latency[port]['rx_data_copy_invalidated'] += 1

            if is_valid(ts['valid'], stage_bits['app']):
                accounted_latency[port]['app'].append(ts['tx_write'] - ts['rx_return'] - ts['app_loss'])
                accounted_latency[port]['app_l1_load_miss'].append(ts['app_l1_load_miss'])
                accounted_latency[port]['app_l2_load_miss'].append(ts['app_l2_load_miss'])
                accounted_latency[port]['app_llc_load_miss'].append(ts['app_llc_load_miss'])
            else:
                accounted_latency[port]['app_invalidated'] += 1

            if is_valid(ts['valid'], stage_bits['tx_data_copy']):
                accounted_latency[port]['tx_data_copy'].append(ts['tx_tcp'] - ts['tx_write'] - ts['tx_data_copy_loss'])
                accounted_latency[port]['txc_l1_load_miss'].append(ts['txc_l1_load_miss'])
                accounted_latency[port]['txc_l2_load_miss'].append(ts['txc_l2_load_miss'])
                accounted_latency[port]['txc_llc_load_miss'].append(ts['txc_llc_load_miss'])
            else:
                accounted_latency[port]['tx_data_copy_invalidated'] += 1

    return accounted_latency


def process_experiment(result_dir, experiment, n_thread, save_id):
    print(f"[PID {os.getpid()}] Processing experiment: {experiment} with {n_thread} threads")

    experiment_dir = os.path.join(result_dir, experiment)
    client_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}.log")
    server_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}-server.log")

    client_accounted = client_sched_parser(client_breakdown_path)
    server_accounted = server_sched_parser(server_breakdown_path)

    client_results = []
    server_results = []

    for port in client_accounted.keys():
        client_results.append({
            "port": port,
        })
        
        client_app_time = [x for x in client_accounted[port]['app']]
        client_app_l1dcache_load = [x for x in client_accounted[port]['app_l1_load_miss']]
        client_app_l2dcache_load = [x for x in client_accounted[port]['app_l2_load_miss']]
        client_app_llc_data_load = [x for x in client_accounted[port]['app_llc_load_miss']]
        client_rxc_time = [x for x in client_accounted[port]['rx_data_copy']]
        client_rxc_l1dcache_load = [x for x in client_accounted[port]['rxc_l1_load_miss']]
        client_rxc_l2dcache_load = [x for x in client_accounted[port]['rxc_l2_load_miss']]
        client_rxc_llc_data_load = [x for x in client_accounted[port]['rxc_llc_load_miss']]
        client_txc_time = [x for x in client_accounted[port]['tx_data_copy']]
        client_txc_l1dcache_load = [x for x in client_accounted[port]['txc_l1_load_miss']]
        client_txc_l2dcache_load = [x for x in client_accounted[port]['txc_l2_load_miss']]
        client_txc_llc_data_load = [x for x in client_accounted[port]['txc_llc_load_miss']]
        client_results[-1]['app_avg'] = sum(client_app_time)/len(client_app_time) if len(client_app_time)>0 else -9999
        client_results[-1]['app_l1_load_miss_total'] = sum(client_app_l1dcache_load)
        client_results[-1]['app_l2_load_miss_total'] = sum(client_app_l2dcache_load)
        client_results[-1]['app_llc_load_miss_total'] = sum(client_app_llc_data_load)
        client_results[-1]['rxc_avg'] = sum(client_rxc_time)/len(client_rxc_time) if len(client_rxc_time)>0 else -9999
        client_results[-1]['rxc_l1_load_miss_total'] = sum(client_rxc_l1dcache_load)
        client_results[-1]['rxc_l2_load_miss_total'] = sum(client_rxc_l2dcache_load)
        client_results[-1]['rxc_llc_load_miss_total'] = sum(client_rxc_llc_data_load)
        client_results[-1]['txc_avg'] = sum(client_txc_time)/len(client_txc_time) if len(client_txc_time)>0 else -9999
        client_results[-1]['txc_l1_load_miss_total'] = sum(client_txc_l1dcache_load)
        client_results[-1]['txc_l2_load_miss_total'] = sum(client_txc_l2dcache_load)
        client_results[-1]['txc_llc_load_miss_total'] = sum(client_txc_llc_data_load)
        client_results[-1]['total_avg'] = client_results[-1]['app_avg'] + client_results[-1]['rxc_avg'] + client_results[-1]['txc_avg']
        client_results[-1]['total_l1_load_miss'] = client_results[-1]['app_l1_load_miss_total'] + client_results[-1]['rxc_l1_load_miss_total'] + client_results[-1]['txc_l1_load_miss_total']
        client_results[-1]['total_l2_load_miss'] = client_results[-1]['app_l2_load_miss_total'] + client_results[-1]['rxc_l2_load_miss_total'] + client_results[-1]['txc_l2_load_miss_total']
        client_results[-1]['total_llc_load_miss'] = client_results[-1]['app_llc_load_miss_total'] + client_results[-1]['rxc_llc_load_miss_total'] + client_results[-1]['txc_llc_load_miss_total']
        client_results[-1]['app_invalidated'] = client_accounted[port]['app_invalidated']
        client_results[-1]['rx_data_copy_invalidated'] = client_accounted[port]['rx_data_copy_invalidated']
        client_results[-1]['tx_data_copy_invalidated'] = client_accounted[port]['tx_data_copy_invalidated']
        client_results[-1]['total_invalidated'] = client_results[-1]['app_invalidated'] + client_results[-1]['rx_data_copy_invalidated'] + client_results[-1]['tx_data_copy_invalidated']


    for port in server_accounted.keys():
        server_results.append({
            "port": port,
        })
        server_app_time = [x for x in server_accounted[port]['app']]
        server_app_l1dcache_load = [x for x in server_accounted[port]['app_l1_load_miss']]
        server_app_l2dcache_load = [x for x in server_accounted[port]['app_l2_load_miss']]
        server_app_llc_data_load = [x for x in server_accounted[port]['app_llc_load_miss']]
        server_rxc_time = [x for x in server_accounted[port]['rx_data_copy']]
        server_rxc_l1dcache_load = [x for x in server_accounted[port]['rxc_l1_load_miss']]
        server_rxc_l2dcache_load = [x for x in server_accounted[port]['rxc_l2_load_miss']]
        server_rxc_llc_data_load = [x for x in server_accounted[port]['rxc_llc_load_miss']]
        server_txc_time = [x for x in server_accounted[port]['tx_data_copy']]
        server_txc_l1dcache_load = [x for x in server_accounted[port]['txc_l1_load_miss']]
        server_txc_l2dcache_load = [x for x in server_accounted[port]['txc_l2_load_miss']]
        server_txc_llc_data_load = [x for x in server_accounted[port]['txc_llc_load_miss']]

        server_results[-1]['app_avg'] = sum(server_app_time)/len(server_app_time) if len(server_app_time)>0 else -9999
        server_results[-1]['app_l1_load_miss_total'] = sum(server_app_l1dcache_load)
        server_results[-1]['app_l2_load_miss_total'] = sum(server_app_l2dcache_load)
        server_results[-1]['app_llc_load_miss_total'] = sum(server_app_llc_data_load)
        server_results[-1]['rxc_avg'] = sum(server_rxc_time)/len(server_rxc_time) if len(server_rxc_time)>0 else -9999
        server_results[-1]['rxc_l1_load_miss_total'] = sum(server_rxc_l1dcache_load)
        server_results[-1]['rxc_l2_load_miss_total'] = sum(server_rxc_l2dcache_load)
        server_results[-1]['rxc_llc_load_miss_total'] = sum(server_rxc_llc_data_load)
        server_results[-1]['txc_avg'] = sum(server_txc_time)/len(server_txc_time) if len(server_txc_time)>0 else -9999
        server_results[-1]['txc_l1_load_miss_total'] = sum(server_txc_l1dcache_load)
        server_results[-1]['txc_l2_load_miss_total'] = sum(server_txc_l2dcache_load)
        server_results[-1]['txc_llc_load_miss_total'] = sum(server_txc_llc_data_load)
        server_results[-1]['total_avg'] = server_results[-1]['app_avg'] + server_results[-1]['rxc_avg'] + server_results[-1]['txc_avg']
        server_results[-1]['total_l1_load_miss'] = server_results[-1]['app_l1_load_miss_total'] + server_results[-1]['rxc_l1_load_miss_total'] + server_results[-1]['txc_l1_load_miss_total']
        server_results[-1]['total_l2_load_miss'] = server_results[-1]['app_l2_load_miss_total'] + server_results[-1]['rxc_l2_load_miss_total'] + server_results[-1]['txc_l2_load_miss_total']
        server_results[-1]['total_llc_load_miss'] = server_results[-1]['app_llc_load_miss_total'] + server_results[-1]['rxc_llc_load_miss_total'] + server_results[-1]['txc_llc_load_miss_total']
        server_results[-1]['app_invalidated'] = server_accounted[port]['app_invalidated']
        server_results[-1]['rx_data_copy_invalidated'] = server_accounted[port]['rx_data_copy_invalidated']
        server_results[-1]['tx_data_copy_invalidated'] = server_accounted[port]['tx_data_copy_invalidated']
        server_results[-1]['total_invalidated'] = server_results[-1]['app_invalidated'] + server_results[-1]['rx_data_copy_invalidated'] + server_results[-1]['tx_data_copy_invalidated']

    # Save results
    client_save_path = os.path.join(experiment_dir, f"rdpmc_client.txt")
    server_save_path = os.path.join(experiment_dir, f"rdpmc_server.txt")
    with open(client_save_path, "w") as f:
        f.write("port rxc_avg rxc_l1 rxc_l2 rxc_llc app_avg app_l1 app_l2 app_llc txc_avg txc_l1 txc_l2 txc_llc total_avg total_l1 total_l2 total_llc app_invalidated rx_data_copy_invalidated tx_data_copy_invalidated total_invalidated\n")
        for res in client_results:
            f.write(f"{res['port']} {res['rxc_avg']} {res['rxc_l1_load_miss_total']} {res['rxc_l2_load_miss_total']} {res['rxc_llc_load_miss_total']} "
                    f"{res['app_avg']} {res['app_l1_load_miss_total']} {res['app_l2_load_miss_total']} {res['app_llc_load_miss_total']} "
                    f"{res['txc_avg']} {res['txc_l1_load_miss_total']} {res['txc_l2_load_miss_total']} {res['txc_llc_load_miss_total']} "
                    f"{res['total_avg']} {res['total_l1_load_miss']} {res['total_l2_load_miss']} {res['total_llc_load_miss']} "
                    f"{res['app_invalidated']} {res['rx_data_copy_invalidated']} {res['tx_data_copy_invalidated']} {res['total_invalidated']}\n")
    with open(server_save_path, "w") as f:
        f.write("port rxc_avg rxc_l1 rxc_l2 rxc_llc app_avg app_l1 app_l2 app_llc txc_avg txc_l1 txc_l2 txc_llc total_avg total_l1 total_l2 total_llc app_invalidated rx_data_copy_invalidated tx_data_copy_invalidated total_invalidated\n")
        for res in server_results:
            f.write(f"{res['port']} {res['rxc_avg']} {res['rxc_l1_load_miss_total']} {res['rxc_l2_load_miss_total']} {res['rxc_llc_load_miss_total']} "
                    f"{res['app_avg']} {res['app_l1_load_miss_total']} {res['app_l2_load_miss_total']} {res['app_llc_load_miss_total']} "
                    f"{res['txc_avg']} {res['txc_l1_load_miss_total']} {res['txc_l2_load_miss_total']} {res['txc_llc_load_miss_total']} "
                    f"{res['total_avg']} {res['total_l1_load_miss']} {res['total_l2_load_miss']} {res['total_llc_load_miss']} "
                    f"{res['app_invalidated']} {res['rx_data_copy_invalidated']} {res['tx_data_copy_invalidated']} {res['total_invalidated']}\n")
    return experiment


if __name__ == "__main__":
    result_dir = "/data0/projects/latency/"
    experiments = [
        "sirq_rdpmc_l3_2_1/48_64_1_1_1_1_0_0_1_0",
        "sirq_rdpmc_l3_2_1/48_64_1_1_1_1_0_0_1_1",
        "sirq_rdpmc_l3_2_1/48_64_1_1_1_1_0_0_1_2",
        "sirq_rdpmc_l3_2_1/48_64_1_1_1_1_0_0_1_3",
        "sirq_rdpmc_l3_2_1/48_64_1_1_1_1_0_0_1_4",
        "sirq_rdpmc_l3_2_1/48_64_1_1_1_1_0_0_1_5",
        "sirq_rdpmc_l3_2_1/48_64_1_1_1_1_0_0_1_6",
        "sirq_rdpmc_l3_2_1/48_64_1_1_1_1_0_0_1_7",
        "sirq_rdpmc_l3_2_1/48_64_1_1_1_1_0_0_1_8",
        "sirq_rdpmc_l3_2_1/48_64_1_1_1_1_0_0_1_9",
    ]
    n_threads = [
        48, 48, 48, 48, 48, 48, 48, 48, 48, 48,
    ]
    save_id = [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
    ]

    tasks = list(zip(experiments, n_threads, save_id))

    # Use as many workers as you like; os.cpu_count() is a good default
    max_workers = min(len(tasks), os.cpu_count() or 1)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_experiment, result_dir, exp, th, sid)
            for (exp, th, sid) in tasks
        ]

        for fut in as_completed(futures):
            # This will raise if any worker crashed, which is helpful for debugging
            exp_done = fut.result()
            print(f"[MAIN] Finished experiment: {exp_done}")