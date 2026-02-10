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
                        'rx_sleep_enter': rx_sleep, # to calculate the hidden accounted time: second's rx_sleep_enter - first's tx_finish
                        'rx_data_copy': rx_data_copy,
                        'rx_return': rx_return,
                        'tx_write': tx_write,
                        'tx_tcp': tx_tcp,
                        'tx_ip': tx_ip,
                        'tx_queue': tx_queue,
                        'tx_xmit': tx_xmit,
                        'tx_finish': tx_finish
                    })
                count[port] += 1  # We skip the first two packets for each port to avoid initialization effects 

    accounted_latency = {}

    for port, port_samples in samples.items():
        accounted_latency[port] = {'rx_data_copy': [],
                                   'app': [],
                                   'tx_data_copy': [],
                                   'tx_tcp': [],
                                   'tx_ip': [],
                                   'tx_queue': [],
                                   'tx_xmit': [],
                                   'app_hidden': [],
                                   'rx_data_copy_90th': 0,
                                   'avg_90th': 0,
                                   'number_90th': 0,
                                   'total': 0,
                                   'avg_500ns': 0,
                                   'number_500ns': 0,
                                   'avg_800ns': 0,
                                   'number_800ns': 0,
                                   'avg_1000ns': 0,
                                   'number_1000ns': 0,
                                   }

        for idx, ts in enumerate(port_samples):
            accounted_latency[port]['rx_data_copy'].append(ts['rx_return'] - ts['rx_data_copy'])
            accounted_latency[port]['app'].append(ts['tx_write'] - ts['rx_return'])
            accounted_latency[port]['tx_data_copy'].append(ts['tx_tcp'] - ts['tx_write'])
            accounted_latency[port]['tx_tcp'].append(ts['tx_ip'] - ts['tx_tcp'])
            accounted_latency[port]['tx_ip'].append(ts['tx_queue'] - ts['tx_ip'])
            accounted_latency[port]['tx_queue'].append(ts['tx_xmit'] - ts['tx_queue'])
            accounted_latency[port]['tx_xmit'].append(ts['tx_finish'] - ts['tx_xmit'])
            if idx % 2 == 0:
                last_xmit = ts['tx_finish']
            else:
                accounted_latency[port]['app_hidden'].append(ts['rx_sleep_enter'] - last_xmit if ts['rx_sleep_enter'] > last_xmit else 0)

    return accounted_latency 


def client_sched_parser(breakdown_log_path):
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
                        'rx_sleep_enter': rx_sleep,
                        'rx_data_copy': rx_data_copy,
                        'rx_return': rx_return,
                        'tx_write': tx_write,
                        'tx_tcp': tx_tcp,
                        'tx_ip': tx_ip,
                        'tx_queue': tx_queue,
                        'tx_xmit': tx_xmit,
                        'tx_finish': tx_finish
                    })
                count[port] += 1  # We skip the first two packets for each port to avoid initialization effects
    
    accounted_latency = {}
    for port, port_samples in samples.items():
        accounted_latency[port] = {'rx_data_copy': [],
                                   'app': [],
                                   'tx_data_copy': [],
                                   'tx_tcp': [],
                                   'tx_ip': [],
                                   'tx_queue': [],
                                   'tx_xmit': [],
                                   'app_hidden': [],
                                   'rx_data_copy_90th': 0,
                                   'avg_90th': 0,
                                   'number_90th': 0,
                                   'total': 0,
                                   'avg_500ns': 0,
                                   'number_500ns': 0,
                                   'avg_800ns': 0,
                                   'number_800ns': 0,
                                   'avg_1000ns': 0,
                                   'number_1000ns': 0,
                                   }

        for idx, ts in enumerate(port_samples):
            accounted_latency[port]['rx_data_copy'].append(ts['rx_return'] - ts['rx_data_copy'])
            accounted_latency[port]['app'].append(ts['tx_write'] - ts['rx_return'])
            accounted_latency[port]['tx_data_copy'].append(ts['tx_tcp'] - ts['tx_write'])
            accounted_latency[port]['tx_tcp'].append(ts['tx_ip'] - ts['tx_tcp'])
            accounted_latency[port]['tx_ip'].append(ts['tx_queue'] - ts['tx_ip'])
            accounted_latency[port]['tx_queue'].append(ts['tx_xmit'] - ts['tx_queue'])
            accounted_latency[port]['tx_xmit'].append(ts['tx_finish'] - ts['tx_xmit'])
            if idx % 2 == 0:
                last_xmit = ts['tx_finish']
            else:
                accounted_latency[port]['app_hidden'].append(ts['rx_sleep_enter'] - last_xmit if ts['rx_sleep_enter'] > last_xmit else 0)

    return accounted_latency


def process_experiment(result_dir, experiment, n_thread, save_id):
    print(f"[PID {os.getpid()}] Processing experiment: {experiment} with {n_thread} threads")

    experiment_dir = os.path.join(result_dir, experiment)
    client_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}.log")
    server_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}-server.log")

    client_accounted = client_sched_parser(client_breakdown_path)
    server_accounted = server_sched_parser(server_breakdown_path)

    for port in client_accounted.keys():
        client_accounted[port]['avg_90th'] = 0
        for serie in series:
            client_data = client_accounted[port][serie]
            client_data.sort()
            if serie == 'rx_data_copy':
                rx_data_copy_90th = sum(client_data[:int(len(client_data)*0.9)]) / (len(client_data)*0.9)
                client_accounted[port]['rx_data_copy_90th'] = rx_data_copy_90th
            client_accounted[port]['avg_90th'] += sum(client_data[:int(len(client_data)*0.9)])/(len(client_data)*0.9)
            client_data_500ns = [v for v in client_data if v <= 500]
            client_accounted[port]['avg_500ns'] += sum(client_data_500ns)/len(client_data_500ns) if len(client_data_500ns)>0 else -9999
            client_data_800ns = [v for v in client_data if v <= 800]
            client_accounted[port]['avg_800ns'] += sum(client_data_800ns)/len(client_data_800ns) if len(client_data_800ns)>0 else -9999
            client_data_1000ns = [v for v in client_data if v <= 1000]
            client_accounted[port]['avg_1000ns'] += sum(client_data_1000ns)/len(client_data_1000ns) if len(client_data_1000ns)>0 else -9999
            client_accounted[port]['total'] += sum(client_data)
            client_accounted[port][serie] = sum(client_data[:int(len(client_data)*0.9)])

    for port in server_accounted.keys():
        server_accounted[port]['avg_90th'] = 0
        for serie in series:
            server_data = server_accounted[port][serie]
            server_data.sort()
            server_accounted[port]['avg_90th'] += sum(server_data[:int(len(server_data)*0.9)])/(len(server_data)*0.9)
            server_data_500ns = [v for v in server_data if v <= 500]
            server_accounted[port]['avg_500ns'] += sum(server_data_500ns)/len(server_data_500ns) if len(server_data_500ns)>0 else -9999
            server_data_800ns = [v for v in server_data if v <= 800]
            server_accounted[port]['avg_800ns'] += sum(server_data_800ns)/len(server_data_800ns) if len(server_data_800ns)>0 else -9999
            server_data_1000ns = [v for v in server_data if v <= 1000]
            server_accounted[port]['avg_1000ns'] += sum(server_data_1000ns)/len(server_data_1000ns) if len(server_data_1000ns)>0 else -9999
            server_accounted[port]['total'] += sum(server_data)
            server_accounted[port][serie] = sum(server_data[:int(len(server_data)*0.9)])

    # Save results
    client_save_path = os.path.join(experiment_dir, f"breakdown_sum_p90_client.txt")
    server_save_path = os.path.join(experiment_dir, f"breakdown_sum_p90_server.txt")
    with open(client_save_path, "w") as f:
        f.write("port avg_90th 500 800 1000 rx_data_copy_90th\n")
        for port, data in client_accounted.items():
            f.write(f"{port} {data['avg_90th']} {data['avg_500ns']} {data['avg_800ns']} {data['avg_1000ns']} {data['rx_data_copy_90th']}\n")
    with open(server_save_path, "w") as f:
        f.write("port avg_90th 500 800 1000\n")
        for port, data in server_accounted.items():
            f.write(f"{port} {data['avg_90th']} {data['avg_500ns']} {data['avg_800ns']} {data['avg_1000ns']}\n")

    # For each port, draw CDF for app_hidden
    # plt.figure(figsize=(10, 6))
    # for port in client_accounted.keys():
    #     client_app_hidden_data = client_accounted[port]['app_hidden']
    #     client_app_hidden_data.sort()
    #     cdf = [i/len(client_app_hidden_data) for i in range(len(client_app_hidden_data))]
    #     plt.plot(client_app_hidden_data, cdf, label=f'Port {port}')
    # plt.xlabel('App Hidden Latency (ns)')
    # plt.ylabel('CDF')
    # plt.xscale('log')
    # plt.grid(True)
    # # plt.legend()
    # plt.tight_layout()
    # plt.savefig("app_hidden_cdf_client.pdf")
    # plt.close()

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
    ]
    result_dir = "/data0/projects/latency/"
    experiments = [
        # "airq_add_up_3_1/52_64_1_1_1_1_0_0_1_0",
        # "airq_add_up_3_1/52_64_1_1_1_1_0_0_1_1",
        # "airq_add_up_3_1/52_64_1_1_1_1_0_0_1_2",
        # "airq_add_up_3_1/52_64_1_1_1_1_0_0_1_3",
        # "airq_add_up_3_1/52_64_1_1_1_1_0_0_1_4",
        # "airq_sched_accounting_1_1/52_64_1_1_1_1_0_0_1_1",
        # "sirq_breakdown_5_2/52_64_1_2_1_1_0_0_1_0",
        # "airq_run_to_complete_1_1/64_64_1_1_1_1_0_0_1_0",
        # "airq_run_to_complete_1_1/64_64_1_2_1_1_0_0_1_0",
        # "sirq_breakdown_6_2/52_64_1_1_1_1_0_0_1_0"
        "sirq_understanding_1_1/52_64_1_1_1_1_0_0_1_0",
        "sirq_understanding_1_1/52_64_1_1_1_1_0_0_1_1",
        "sirq_understanding_1_1/52_64_1_1_1_1_0_0_1_2",
        "sirq_understanding_1_1/52_64_1_1_1_1_0_0_1_3",
        "sirq_understanding_1_1/52_64_1_1_1_1_0_0_1_4",
        
    ]
    n_threads = [
        52, 52, 52, 52, 52
    ]
    save_id = [0, 1, 2, 3, 4]

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