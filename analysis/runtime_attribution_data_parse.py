#!/usr/bin/env python3
import os
import re
import sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
import matplotlib.pyplot as plt

# 20 distinct colors for plotting
colors = [
    'blue', 'orange', 'green', 'red', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan',
    'magenta', 'yellow', 'teal', 'lavender', 'turquoise', 'tan', 'salmon', 'gold', 'navy', 'maroon'
]


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
        r"6: ([0-9]+) 7: ([0-9]+) 8: ([0-9]+) 9: ([0-9]+) 10: ([0-9]+).*"
    )

    samples = {}
    count = {}

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 35:
                _, port, rx_hw, rx_alloc, rx_irq, rx_napi, rx_gro, rx_ip, rx_tcp, rx_read, rx_sleep,\
                rx_ready, rx_wake_up, rx_data_copy, rx_return, tx_alloc, tx_write, tx_data_copy, \
                tx_tcp, tx_ip, tx_queue, tx_xmit, tx_finish, last_xmit_finish, valid, \
                hidden_app_loss, sleep_prepare_loss, sleep_wake_up_loss, rx_data_copy_loss, app_loss, \
                tx_data_copy_loss, tx_tcp_loss, tx_ip_loss, tx_queue_loss, tx_xmit_loss  = timestamps

                if port not in samples:
                    samples[port] = []
                    count[port] = 0

                if not count[port] < 2: # We skip first 2 packets to avoid zero time stamp and migration.
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
                    })
                count[port] += 1  # We skip the first two packets for each port to avoid initialization effects 

    accounted_latency = {}

    for port, port_samples in samples.items():
        accounted_latency[port] = {
                                    'app_hidden': [],
                                    'sleep_prepare': [],
                                    'sleep_wake_up': [],
                                    'insomonia': [],
                                    'total_slept': 0,
                                    'total_insomnia': 0,
                                    'rx_data_copy': [],
                                    'app': [],
                                    'tx_data_copy': [],
                                    'tx_tcp': [],
                                    'tx_ip': [],
                                    'tx_queue': [],
                                    'tx_xmit': [],
                                }

        for idx, ts in enumerate(port_samples):
            # app_hidden
            if is_valid(ts['valid'], stage_bits['app_hidden']) and ts['rx_read_enter'] >= ts['last_xmit_finish'] and idx%2 == 1:
                accounted_latency[port]['app_hidden'].append(ts['rx_read_enter'] - ts['last_xmit_finish'] - ts['hidden_app_loss'])

            # app_hidden_2
            if ts['rx_sleep_enter'] == 0:
                accounted_latency[port]['total_insomnia'] += 1
                if is_valid(ts['valid'], stage_bits['sleep_wake_up']):
                    accounted_latency[port]['insomonia'].append(ts['rx_data_copy'] - ts['rx_read_enter'] - ts['sleep_wake_up_loss'])
            else:
                accounted_latency[port]['total_slept'] += 1
                if is_valid(ts['valid'], stage_bits['sleep_prepare']):
                    accounted_latency[port]['sleep_prepare'].append(ts['rx_sleep_enter'] - ts['rx_read_enter'] - ts['sleep_prepare_loss'])
                if is_valid(ts['valid'], stage_bits['sleep_wake_up']):
                    accounted_latency[port]['sleep_wake_up'].append(ts['rx_data_copy'] - ts['rx_wake_up'] - ts['sleep_wake_up_loss'])

            # other parts
            if is_valid(ts['valid'], stage_bits['rx_data_copy']):
                accounted_latency[port]['rx_data_copy'].append(ts['rx_return'] - ts['rx_data_copy'] - ts['rx_data_copy_loss'])
            if is_valid(ts['valid'], stage_bits['app']):
                accounted_latency[port]['app'].append(ts['tx_write'] - ts['rx_return'] - ts['app_loss'])
            if is_valid(ts['valid'], stage_bits['tx_data_copy']):
                accounted_latency[port]['tx_data_copy'].append(ts['tx_tcp'] - ts['tx_write'] - ts['tx_data_copy_loss'])
            if is_valid(ts['valid'], stage_bits['tx_tcp']):
                accounted_latency[port]['tx_tcp'].append(ts['tx_ip'] - ts['tx_tcp'] - ts['tx_tcp_loss'])
            if is_valid(ts['valid'], stage_bits['tx_ip']):
                accounted_latency[port]['tx_ip'].append(ts['tx_queue'] - ts['tx_ip'] - ts['tx_ip_loss'])
            if is_valid(ts['valid'], stage_bits['tx_queue']):
                accounted_latency[port]['tx_queue'].append(ts['tx_xmit'] - ts['tx_queue'] - ts['tx_queue_loss'])
            if is_valid(ts['valid'], stage_bits['tx_xmit']):
                accounted_latency[port]['tx_xmit'].append(ts['tx_finish'] - ts['tx_xmit'] - ts['tx_xmit_loss'])

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
        r"6: ([0-9]+) 7: ([0-9]+) 8: ([0-9]+) 9: ([0-9]+) 10: ([0-9]+).*"
    )

    samples = {}
    count = {}

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 35:
                port, _, rx_hw, rx_alloc, rx_irq, rx_napi, rx_gro, rx_ip, rx_tcp, rx_read, rx_sleep,\
                rx_ready, rx_wake_up, rx_data_copy, rx_return, tx_alloc, tx_write, tx_data_copy, \
                tx_tcp, tx_ip, tx_queue, tx_xmit, tx_finish, last_xmit_finish, valid, \
                hidden_app_loss, sleep_prepare_loss, sleep_wake_up_loss, rx_data_copy_loss, app_loss, \
                tx_data_copy_loss, tx_tcp_loss, tx_ip_loss, tx_queue_loss, tx_xmit_loss  = timestamps

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
                    })
                count[port] += 1  # We skip the first two packets for each port to avoid initialization effects
    
    accounted_latency = {}
    for port, port_samples in samples.items():
        accounted_latency[port] = {
                                    'app_hidden': [],
                                    'sleep_prepare': [],
                                    'sleep_wake_up': [],
                                    'insomonia': [],
                                    'total_slept': 0,
                                    'total_insomnia': 0,
                                    'rx_data_copy': [],
                                    'app': [],
                                    'tx_data_copy': [],
                                    'tx_tcp': [],
                                    'tx_ip': [],
                                    'tx_queue': [],
                                    'tx_xmit': [],
                                }

        for idx, ts in enumerate(port_samples):
            # app_hidden
            #   why can ts['rx_read_enter'] < ts['last_xmit_finish']? A possible reason is that other thread called mlx5_txwqe_complete?
            if is_valid(ts['valid'], stage_bits['app_hidden']) and ts['rx_read_enter'] >= ts['last_xmit_finish'] and idx%2 == 1:
                accounted_latency[port]['app_hidden'].append(ts['rx_read_enter'] - ts['last_xmit_finish'] - ts['hidden_app_loss'])
            
            # app_hidden_2
            if ts['rx_sleep_enter'] == 0:
                accounted_latency[port]['total_insomnia'] += 1
                if is_valid(ts['valid'], stage_bits['sleep_wake_up']):
                    accounted_latency[port]['insomonia'].append(ts['rx_data_copy'] - ts['rx_read_enter'] - ts['sleep_wake_up_loss'])
            else:
                accounted_latency[port]['total_slept'] += 1
                if is_valid(ts['valid'], stage_bits['sleep_prepare']):
                    accounted_latency[port]['sleep_prepare'].append(ts['rx_sleep_enter'] - ts['rx_read_enter'] - ts['sleep_prepare_loss'])
                if is_valid(ts['valid'], stage_bits['sleep_wake_up']):
                    accounted_latency[port]['sleep_wake_up'].append(ts['rx_data_copy'] - ts['rx_wake_up'] - ts['sleep_wake_up_loss'])
            
            # other parts
            if is_valid(ts['valid'], stage_bits['rx_data_copy']):
                accounted_latency[port]['rx_data_copy'].append(ts['rx_return'] - ts['rx_data_copy'] - ts['rx_data_copy_loss'])
            if is_valid(ts['valid'], stage_bits['app']):
                accounted_latency[port]['app'].append(ts['tx_write'] - ts['rx_return'] - ts['app_loss'])
            if is_valid(ts['valid'], stage_bits['tx_data_copy']):
                accounted_latency[port]['tx_data_copy'].append(ts['tx_tcp'] - ts['tx_write'] - ts['tx_data_copy_loss'])
            if is_valid(ts['valid'], stage_bits['tx_tcp']):
                accounted_latency[port]['tx_tcp'].append(ts['tx_ip'] - ts['tx_tcp'] - ts['tx_tcp_loss'])
            if is_valid(ts['valid'], stage_bits['tx_ip']):
                accounted_latency[port]['tx_ip'].append(ts['tx_queue'] - ts['tx_ip'] - ts['tx_ip_loss'])
            if is_valid(ts['valid'], stage_bits['tx_queue']): 
                accounted_latency[port]['tx_queue'].append(ts['tx_xmit'] - ts['tx_queue'] - ts['tx_queue_loss'])
            if is_valid(ts['valid'], stage_bits['tx_xmit']):
                accounted_latency[port]['tx_xmit'].append(ts['tx_finish'] - ts['tx_xmit'] - ts['tx_xmit_loss'])

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
        for serie in series:
            if serie == 'app_hidden_2':
                client_insomnia_data = [x for x in client_accounted[port]['insomonia']]
                average_insomnia = sum(client_insomnia_data)/len(client_insomnia_data) if len(client_insomnia_data)>0 else 0
                total_insomnia = client_accounted[port]['total_insomnia']

                client_sleep_prepare_data = [x for x in client_accounted[port]['sleep_prepare']]
                average_sleep_prepare = sum(client_sleep_prepare_data)/len(client_sleep_prepare_data) if len(client_sleep_prepare_data)>0 else 0
                client_sleep_wake_up_data = [x for x in client_accounted[port]['sleep_wake_up']]
                average_sleep_wake_up = sum(client_sleep_wake_up_data)/len(client_sleep_wake_up_data) if len(client_sleep_wake_up_data)>0 else 0
                average_slept = average_sleep_prepare + average_sleep_wake_up
                total_slept = client_accounted[port]['total_slept']

                client_results[-1][f"{serie}_avg"] = (average_insomnia * total_insomnia + average_slept * total_slept) / (total_insomnia + total_slept) if (total_insomnia + total_slept) > 0 else 0

            else:
                client_data = [x for x in client_accounted[port][serie]]
                client_results[-1][f"{serie}_avg"] = sum(client_data)/len(client_data) if len(client_data)>0 else -9999
        client_results[-1]["total_avg"] = sum([client_results[-1][f"{serie}_avg"] for serie in series])

    for port in server_accounted.keys():
        server_results.append({
            "port": port,
        })
        for serie in series:
            if serie == 'app_hidden_2':
                server_insomonia_data = [x for x in server_accounted[port]['insomonia']]
                average_insomnia = sum(server_insomonia_data)/len(server_insomonia_data) if len(server_insomonia_data)>0 else 0
                total_insomnia = server_accounted[port]['total_insomnia']

                server_sleep_prepare_data = [x for x in server_accounted[port]['sleep_prepare']]
                average_sleep_prepare = sum(server_sleep_prepare_data)/len(server_sleep_prepare_data) if len(server_sleep_prepare_data)>0 else 0
                server_sleep_wake_up_data = [x for x in server_accounted[port]['sleep_wake_up']]
                average_sleep_wake_up = sum(server_sleep_wake_up_data)/len(server_sleep_wake_up_data) if len(server_sleep_wake_up_data)>0 else 0
                average_slept = average_sleep_prepare + average_sleep_wake_up
                total_slept = server_accounted[port]['total_slept']

                server_results[-1][f"{serie}_avg"] = (average_insomnia * total_insomnia + average_slept * total_slept) / (total_insomnia + total_slept) if (total_insomnia + total_slept) > 0 else 0
            else:
                server_data = [x for x in server_accounted[port][serie]]
                server_results[-1][f"{serie}_avg"] = sum(server_data)/len(server_data) if len(server_data)>0 else -9999
        server_results[-1]["total_avg"] = sum([server_results[-1][f"{serie}_avg"] for serie in series])

    # Save results
    client_save_path = os.path.join(experiment_dir, f"valid_real_breakdown_sum_p90_client.txt")
    server_save_path = os.path.join(experiment_dir, f"valid_real_breakdown_sum_p90_server.txt")
    with open(client_save_path, "w") as f:
        f.write("port app_hidden app_hidden_2 rx_data_copy app tx_data_copy tx_tcp tx_ip tx_queue tx_xmit total_avg\n")
        for res in client_results:
            f.write(f"{res['port']} ")
            for serie in series:
                f.write(f"{res[f'{serie}_avg']:.2f} ")
            f.write(f"{res['total_avg']:.2f}\n")

    with open(server_save_path, "w") as f:
        f.write("port app_hidden app_hidden_2 rx_data_copy app tx_data_copy tx_tcp tx_ip tx_queue tx_xmit total_avg\n")
        for res in server_results:
            f.write(f"{res['port']} ")
            for serie in series:
                f.write(f"{res[f'{serie}_avg']:.2f} ")
            f.write(f"{res['total_avg']:.2f}\n")

    # # For each series, for each port, draw CDF for app_hidden
    # for serie in ['app_hidden']:  # only app_hidden
    #     plt.figure(figsize=(10, 6))
    #     for port in client_accounted.keys():
    #         client_app_hidden_data = client_accounted[port][serie]
    #         client_app_hidden_data.sort()
    #         cdf = [i/len(client_app_hidden_data) for i in range(len(client_app_hidden_data))]
    #         plt.plot(client_app_hidden_data, cdf, label=f'Port {port}')
    #     plt.xlabel(f'{serie} (ns)')
    #     plt.ylabel('CDF')
    #     # plt.xscale('log')
    #     plt.ylim(0, 1)
    #     plt.grid(True)
    #     # plt.legend()
    #     plt.tight_layout()
    #     plt.savefig(f"valid_insomnia_recover_{serie}_cdf_client.pdf")
    #     plt.close()
    #     plt.figure(figsize=(10, 6))
    #     for port in server_accounted.keys():
    #         server_app_hidden_data = server_accounted[port][serie]
    #         server_app_hidden_data.sort()
    #         cdf = [i/len(server_app_hidden_data) for i in range(len(server_app_hidden_data))]
    #         plt.plot(server_app_hidden_data, cdf, label=f'Port {port}')
    #     plt.xlabel(f'{serie} (ns)')
    #     plt.ylabel('CDF')
    #     # plt.xscale('log')
    #     plt.ylim(0, 1)
    #     plt.grid(True)
    #     # plt.legend()
    #     plt.tight_layout()
    #     plt.savefig(f"valid_insomnia_recover_{serie}_cdf_server.pdf")
    #     plt.close()

    # client ={serie: [] for serie in series}
    # server ={serie: [] for serie in series}
    # client["port"] = []
    # server["port"] = []
    # client["avg_90th"] = []
    # server["avg_90th"] = []
    # for port in range(10000, 10000 + n_thread):
    #     client["port"].append(port)
    #     for serie in series:
    #         client[serie].append(client_accounted[port][serie])
    #     client["avg_90th"].append(client_accounted[port]["avg_90th"])
    # for port in range(10000, 10000 + n_thread):
    #     server["port"].append(port)
    #     for serie in series:
    #         server[serie].append(server_accounted[port][serie])
    #     server["avg_90th"].append(server_accounted[port]["avg_90th"])

    # # norm the data
    # for serie in series:
    #     client[serie] = norm_list(client[serie], offset=1)
    #     server[serie] = norm_list(server[serie], offset=1)
    
    # print(f"[PID {os.getpid()}] {client}, {server}")
    # # sort client and server by port number
    # draw_breakdown_sum_treand(client, f"client_{save_id}")
    # draw_breakdown_sum_treand(server, f"server_{save_id}")

    return experiment


if __name__ == "__main__":
    series = [
        'app_hidden',
        'app_hidden_2',
        'rx_data_copy',
        'app',
        'tx_data_copy',
        'tx_tcp',
        'tx_ip',
        'tx_queue',
        'tx_xmit',
    ]
    result_dir = "/data0/projects/latency/"
    experiments = [
        # "sirq_understanding_6_1/52_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_6_1/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_6_1/52_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_6_1/52_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_6_1/52_64_1_1_1_1_0_0_1_4",
        # "sairq_understanding_9_1/48_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_12_1/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_13_2/48_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_13_2/48_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_13_2/48_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_13_2/48_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_13_2/48_64_1_1_1_1_0_0_1_4",
        # "sirq_understanding_13_2/52_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_13_2/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_13_2/52_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_13_2/52_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_13_2/52_64_1_1_1_1_0_0_1_4",
        # "sirq_understanding_18_2/52_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_18_2/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_18_2/52_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_18_2/52_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_18_2/52_64_1_1_1_1_0_0_1_4",

        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_4",
        "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_0",
        "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_1",
        "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_2",
        "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_3",
        "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_4",
        "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_5",
        "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_6",
        "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_7",
        "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_8",
        "sirq_understanding_24_1/52_64_1_1_1_1_0_0_1_9",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_0",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_1",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_2",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_3",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_4",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_5",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_6",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_7",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_8",
        "sirq_understanding_24_1/48_64_1_1_1_1_0_0_1_9",
    ]
    n_threads = [
        52, 52, 52, 52, 52, 52, 52, 52, 52, 52,
        48, 48, 48, 48, 48, 48, 48, 48, 48, 48,
    ]
    save_id = [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
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