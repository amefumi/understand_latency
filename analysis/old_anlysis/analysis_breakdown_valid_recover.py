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
# 	STAGE_HIDDEN_APP_BIT = 0,
#     STAGE_RX_DATA_COPY_BIT,
#     STAGE_APPLICATION_BIT,
#     STAGE_TX_DATA_COPY_BIT,
#     STAGE_TX_TCP_PROC_BIT,
#     STAGE_TX_IP_PROC_BIT,
#     STAGE_TX_QUEUE_BIT,
#     STAGE_TX_XMIT_BIT,
#     STAGE_INVALID_BIT_MAX
# };

stage_bits = {
    'app_hidden': 0,
    'rx_data_copy': 1,
    'app': 2,
    'tx_data_copy': 3,
    'tx_tcp': 4,
    'tx_ip': 5,
    'tx_queue': 6,
    'tx_xmit': 7
}

# client_threshold = {
#     'app_hidden': 2000,
#     'rx_data_copy': 350,
#     'app': 700,
#     'tx_data_copy': 500,
#     'tx_tcp': 200,
#     'tx_ip': 250,
#     'tx_queue': 200,
#     'tx_xmit': 200
# }

# server_threshold = {
#     'app_hidden': 2000,
#     'rx_data_copy': 300,
#     'app': 600,
#     'tx_data_copy': 500,
#     'tx_tcp': 200,
#     'tx_ip': 150,
#     'tx_queue': 200,
#     'tx_xmit': 200
# }

# #define STAGE_HIDDEN_APP_INVALID 	(1ULL << STAGE_HIDDEN_APP_BIT)
# #define STAGE_RX_DATA_COPY_INVALID  (1ULL << STAGE_RX_DATA_COPY_BIT)
# #define STAGE_APPLICATION_INVALID   (1ULL << STAGE_APPLICATION_BIT)
# #define STAGE_TX_DATA_COPY_INVALID  (1ULL << STAGE_TX_DATA_COPY_BIT)
# #define STAGE_TX_TCP_PROC_INVALID   (1ULL << STAGE_TX_TCP_PROC_BIT)
# #define STAGE_TX_IP_PROC_INVALID    (1ULL << STAGE_TX_IP_PROC_BIT)
# #define STAGE_TX_QUEUE_INVALID      (1ULL << STAGE_TX_QUEUE_BIT)
# #define STAGE_TX_XMIT_INVALID       (1ULL << STAGE_TX_XMIT_BIT)

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
        r"1: ([0-9]+) 2: ([0-9]+) 3: ([0-9]+) 4: ([0-9]+) "
        r"5: ([0-9]+) 6: ([0-9]+) 7: ([0-9]+) 8: ([0-9]+).*"
    )

    samples = {}
    count = {}

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 33:
                _, port, rx_hw, rx_alloc, rx_irq, rx_napi, rx_gro, rx_ip, rx_tcp, rx_read, rx_sleep,\
                rx_ready, rx_wake_up, rx_data_copy, rx_return, tx_alloc, tx_write, tx_data_copy, \
                tx_tcp, tx_ip, tx_queue, tx_xmit, tx_finish, last_xmit_finish, valid, \
                hidden_app_loss, rx_data_copy_loss, app_loss, tx_data_copy_loss, \
                tx_tcp_loss, tx_ip_loss, tx_queue_loss, tx_xmit_loss  = timestamps

                if port not in samples:
                    samples[port] = []
                    count[port] = 0

                if not count[port] < 2: # We skip first 2 packets to avoid zero time stamp and migration.
                    samples[port].append({
                        'rx_sleep_enter': rx_sleep, # to calculate the hidden accounted time: second's rx_sleep_enter - first's tx_finish
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
                                    'hidden_app': [],
                                    'rx_data_copy': [],
                                    'app': [],
                                    'tx_data_copy': [],
                                    'tx_tcp': [],
                                    'tx_ip': [],
                                    'tx_queue': [],
                                    'tx_xmit': [],
                                    'app_hidden': [],
                                }

        for idx, ts in enumerate(port_samples):
            if is_valid(ts['valid'], stage_bits['rx_data_copy']):
                accounted_latency[port]['rx_data_copy'].append(ts['rx_return'] - ts['rx_wake_up'] - ts['rx_data_copy_loss'])
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
            if is_valid(ts['valid'], stage_bits['app_hidden']) and idx % 2 == 1 and ts['rx_sleep_enter'] > ts['last_xmit_finish']:
                accounted_latency[port]['app_hidden'].append(ts['rx_sleep_enter'] - ts['last_xmit_finish'] - ts['hidden_app_loss'])

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
        r"1: ([0-9]+) 2: ([0-9]+) 3: ([0-9]+) 4: ([0-9]+) "
        r"5: ([0-9]+) 6: ([0-9]+) 7: ([0-9]+) 8: ([0-9]+).*"
    )

    samples = {}
    count = {}

    for line in lines:
        m = pattern.match(line)
        if m is not None:
            timestamps = list(map(int, m.groups()))
            if len(timestamps) == 33:
                port, _, rx_hw, rx_alloc, rx_irq, rx_napi, rx_gro, rx_ip, rx_tcp, rx_read, rx_sleep,\
                rx_ready, rx_wake_up, rx_data_copy, rx_return, tx_alloc, tx_write, tx_data_copy, \
                tx_tcp, tx_ip, tx_queue, tx_xmit, tx_finish, last_xmit_finish, valid, \
                hidden_app_loss, rx_data_copy_loss, app_loss, tx_data_copy_loss, \
                tx_tcp_loss, tx_ip_loss, tx_queue_loss, tx_xmit_loss  = timestamps

                if port not in samples:
                    samples[port] = []
                    count[port] = 0

                if not count[port] < 2: # We skip first two packets to avoid zero time stamp issue.
                    samples[port].append({
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
                                    'rx_data_copy': [],
                                    'app': [],
                                    'tx_data_copy': [],
                                    'tx_tcp': [],
                                    'tx_ip': [],
                                    'tx_queue': [],
                                    'tx_xmit': [],
                                    'app_hidden': [],
                                }

        for idx, ts in enumerate(port_samples):
            if is_valid(ts['valid'], stage_bits['rx_data_copy']):
                accounted_latency[port]['rx_data_copy'].append(ts['rx_return'] - ts['rx_wake_up'] - ts['rx_data_copy_loss'])
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
            if is_valid(ts['valid'], stage_bits['app_hidden']) and idx % 2 == 1 and ts['rx_sleep_enter'] > ts['last_xmit_finish']:
                accounted_latency[port]['app_hidden'].append(ts['rx_sleep_enter'] - ts['last_xmit_finish'] - ts['hidden_app_loss'])

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
            client_data = [x for x in client_accounted[port][serie]]
            client_results[-1][f"{serie}_avg"] = sum(client_data)/len(client_data) if len(client_data)>0 else -9999
            # client_results[-1][f"{serie}_samples"] = len(client_data)
        client_results[-1]["total_avg"] = sum([client_results[-1][f"{serie}_avg"] for serie in series])
        # client_results[-1]["total_samples"] = sum([client_results[-1][f"{serie}_samples"] for serie in series])

    for port in server_accounted.keys():
        server_results.append({
            "port": port,
        })
        for serie in series:
            server_data = [x for x in server_accounted[port][serie]]
            server_results[-1][f"{serie}_avg"] = sum(server_data)/len(server_data) if len(server_data)>0 else -9999
            # server_results[-1][f"{serie}_samples"] = len(server_data)
        server_results[-1]["total_avg"] = sum([server_results[-1][f"{serie}_avg"] for serie in series])
        # server_results[-1]["total_samples"] = sum([server_results[-1][f"{serie}_samples"] for serie in series])

    # Save results
    client_save_path = os.path.join(experiment_dir, f"valid_real_breakdown_sum_p90_client.txt")
    server_save_path = os.path.join(experiment_dir, f"valid_real_breakdown_sum_p90_server.txt")
    with open(client_save_path, "w") as f:
        f.write("port rx_data_copy app tx_data_copy tx_tcp tx_ip tx_queue tx_xmit app_hidden total_avg\n")
        for result in client_results:
            f.write(f"{result['port']} {result['rx_data_copy_avg']:.3f} {result['app_avg']:.3f} {result['tx_data_copy_avg']:.3f} {result['tx_tcp_avg']:.3f} {result['tx_ip_avg']:.3f} {result['tx_queue_avg']:.3f} {result['tx_xmit_avg']:.3f} {result['app_hidden_avg']:.3f} {result['total_avg']:.3f}\n")

    with open(server_save_path, "w") as f:
        f.write("port rx_data_copy app tx_data_copy tx_tcp tx_ip tx_queue tx_xmit app_hidden total_avg\n")
        for result in server_results:
            f.write(f"{result['port']} {result['rx_data_copy_avg']:.3f} {result['app_avg']:.3f} {result['tx_data_copy_avg']:.3f} {result['tx_tcp_avg']:.3f} {result['tx_ip_avg']:.3f} {result['tx_queue_avg']:.3f} {result['tx_xmit_avg']:.3f} {result['app_hidden_avg']:.3f} {result['total_avg']:.3f}\n")

    # client_save_path = os.path.join(experiment_dir, f"valid_real_breakdown_sum_p90_client_samples.txt")
    # server_save_path = os.path.join(experiment_dir, f"valid_real_breakdown_sum_p90_server_samples.txt")
    # with open(client_save_path, "w") as f:
    #     f.write("port rx_data_copy app tx_data_copy tx_tcp tx_ip tx_queue tx_xmit app_hidden total_avg\n")
    #     for result in client_results:
    #         f.write(f"{result['port']} {result['rx_data_copy_samples']} {result['app_samples']} {result['tx_data_copy_samples']} {result['tx_tcp_samples']} {result['tx_ip_samples']} {result['tx_queue_samples']} {result['tx_xmit_samples']} {result['app_hidden_samples']} {result['total_samples']}\n")

    # with open(server_save_path, "w") as f:
    #     f.write("port rx_data_copy app tx_data_copy tx_tcp tx_ip tx_queue tx_xmit app_hidden total_avg\n")
    #     for result in server_results:
    #         f.write(f"{result['port']} {result['rx_data_copy_samples']} {result['app_samples']} {result['tx_data_copy_samples']} {result['tx_tcp_samples']} {result['tx_ip_samples']} {result['tx_queue_samples']} {result['tx_xmit_samples']} {result['app_hidden_samples']} {result['total_samples']}\n")


    # For each series, for each port, draw CDF for app_hidden
    for serie in series[-1:]:  # only app_hidden
        plt.figure(figsize=(10, 6))
        for port in client_accounted.keys():
            client_app_hidden_data = client_accounted[port][serie]
            client_app_hidden_data.sort()
            cdf = [i/len(client_app_hidden_data) for i in range(len(client_app_hidden_data))]
            plt.plot(client_app_hidden_data, cdf, label=f'Port {port}')
        plt.xlabel(f'{serie} (ns)')
        plt.ylabel('CDF')
        plt.xscale('log')
        plt.ylim(0, 1)
        plt.grid(True)
        # plt.legend()
        plt.tight_layout()
        plt.savefig(f"valid_rtc_recover_{serie}_cdf_client.pdf")
        plt.close()
        plt.figure(figsize=(10, 6))
        for port in server_accounted.keys():
            server_app_hidden_data = server_accounted[port][serie]
            server_app_hidden_data.sort()
            cdf = [i/len(server_app_hidden_data) for i in range(len(server_app_hidden_data))]
            plt.plot(server_app_hidden_data, cdf, label=f'Port {port}')
        plt.xlabel(f'{serie} (ns)')
        plt.ylabel('CDF')
        plt.xscale('log')
        plt.ylim(0, 1)
        plt.grid(True)
        # plt.legend()
        plt.tight_layout()
        plt.savefig(f"valid_rtc_recover_{serie}_cdf_server.pdf")
        plt.close()

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


def draw_breakdown_sum_treand(breakdown, save_id):
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 6))
    for serie in series:
        plt.plot(breakdown[serie], label=serie)
    plt.xticks(range(len(breakdown['port'])), breakdown['port'], rotation=90, ha='right')
    plt.xlabel('Port')
    plt.ylabel('Relative P90 Sum Wall Time (ns)')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'breakdown_sum_trend_{save_id}.pdf')
    plt.close()

    # draw avg_90th
    plt.figure(figsize=(10, 6))
    plt.plot(breakdown['avg_90th'], label='avg_90th', color='black')
    plt.xticks(range(len(breakdown['port'])), breakdown['port'], rotation=90, ha='right')
    plt.xlabel('Port')
    plt.ylabel('Total P90 Sum Wall Time (ns)')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'avg_90th_trend_{save_id}.pdf')
    plt.close()



if __name__ == "__main__":
    series = [
        'rx_data_copy',
        'app',
        'tx_data_copy',
        'tx_tcp',
        'tx_ip',
        'tx_queue',
        'tx_xmit',
        'app_hidden'
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

        "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_0",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_1",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_2",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_3",
        # "sirq_understanding_18_4/52_64_1_1_1_1_0_0_1_4",
    ]
    n_threads = [
        # 48, 48, 48, 48, 48,
        52, 52, 52, 52, 52,
    ]
    save_id = [0, 1, 2, 3, 4, 0, 1, 2, 3, 4]

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