#!/usr/bin/env python3
import os
import re
import sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

# 20 distinct colors for plotting
colors = [
    'blue', 'orange', 'green', 'red', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan',
    'magenta', 'yellow', 'teal', 'lavender', 'turquoise', 'tan', 'salmon', 'gold', 'navy', 'maroon'
]


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
                        'rx_ready': rx_ready,
                        'rx_wake_up': rx_wake_up,
                        'rx_data_copy': rx_data_copy,
                        'rx_return': rx_return,
                        'tx_write': tx_write,
                        'tx_tcp': tx_tcp,
                        'tx_ip': tx_ip,
                        'tx_queue': tx_queue,
                        'tx_xmit': tx_xmit,
                    })
                count[port] += 1  # We skip the first two packets for each port to avoid initialization effects 

    sched_latency = {}
    accounted_latency = {}

    for port, port_samples in samples.items():
        sched_latency[port] = {'raw': [], 'avg': 0, 'mid': 0, 'p999': 0}
        accounted_latency[port] = {'raw': [], 'avg': 0, 'mid': 0, 'p75': 0, 'p999': 0}
        for ts in port_samples:
            if ts['rx_ready'] >  ts['rx_wake_up']:
                ts['rx_wake_up'] = ts['rx_ready']

            sched_latency[port]['raw'].append(ts['rx_data_copy'] - ts['rx_ready'])
            accounted_latency[port]['raw'].append(ts['rx_return'] - ts['rx_data_copy'])
        sched_latency[port]['raw'].sort()
        sched_latency[port]['avg'] = sum(sched_latency[port]['raw']) / len(sched_latency[port]['raw'])
        sched_latency[port]['mid'] = sched_latency[port]['raw'][len(sched_latency[port]['raw']) // 2]
        sched_latency[port]['p999'] = sched_latency[port]['raw'][int(len(sched_latency[port]['raw']) * 0.999) - 1]
        accounted_latency[port]['raw'].sort()
        accounted_latency[port]['avg'] = sum(accounted_latency[port]['raw']) / len(accounted_latency[port]['raw'])
        accounted_latency[port]['mid'] = accounted_latency[port]['raw'][len(accounted_latency[port]['raw']) // 2]
        accounted_latency[port]['p999'] = accounted_latency[port]['raw'][int(len(accounted_latency[port]['raw']) * 0.999) - 1]
        # # filter processing: filter all values that are greater than mid * 3
        # accounted_latency[port]['raw'] = [x for x in accounted_latency[port]['raw'] if x <= accounted_latency[port]['mid'] * 3]
        # accounted_latency[port]['raw'].sort()
        # accounted_latency[port]['avg'] = sum(accounted_latency[port]['raw']) / len(accounted_latency[port]['raw'])
        # accounted_latency[port]['mid'] = accounted_latency[port]['raw'][len(accounted_latency[port]['raw']) // 2]
        # accounted_latency[port]['p75'] = accounted_latency[port]['raw'][int(len(accounted_latency[port]['raw']) * 0.75) - 1]
        # accounted_latency[port]['p999'] = accounted_latency[port]['raw'][int(len(accounted_latency[port]['raw']) * 0.999) - 1]          

    return sched_latency, accounted_latency 


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
                        'rx_ready': rx_ready,
                        'rx_wake_up': rx_wake_up,
                        'rx_data_copy': rx_data_copy,
                        'rx_return': rx_return,
                        'tx_write': tx_write,
                        'tx_tcp': tx_tcp,
                        'tx_ip': tx_ip,
                        'tx_queue': tx_queue,
                        'tx_xmit': tx_xmit,
                    })
                count[port] += 1

    sched_latency = {}
    accounted_latency = {}
    
    for port, port_samples in samples.items():
        sched_latency[port] = {'raw': [], 'avg': 0, 'mid': 0, 'p999': 0}
        accounted_latency[port] = {'raw': [], 'avg': 0, 'mid': 0, 'p75': 0, 'p999': 0}
        for ts in port_samples: # this shouldn't happen but we keep it as the original code
            if ts['rx_ready'] >  ts['rx_wake_up']:
                ts['rx_wake_up'] = ts['rx_ready']

            sched_latency[port]['raw'].append(ts['rx_data_copy'] - ts['rx_ready'])
            accounted_latency[port]['raw'].append(ts['rx_return'] - ts['rx_data_copy'])
        sched_latency[port]['raw'].sort()
        sched_latency[port]['avg'] = sum(sched_latency[port]['raw']) / len(sched_latency[port]['raw'])
        sched_latency[port]['mid'] = sched_latency[port]['raw'][len(sched_latency[port]['raw']) // 2]
        sched_latency[port]['p999'] = sched_latency[port]['raw'][int(len(sched_latency[port]['raw']) * 0.999) - 1]
        accounted_latency[port]['raw'].sort()
        accounted_latency[port]['avg'] = sum(accounted_latency[port]['raw']) / len(accounted_latency[port]['raw'])
        accounted_latency[port]['mid'] = accounted_latency[port]['raw'][len(accounted_latency[port]['raw']) // 2]
        accounted_latency[port]['p999'] = accounted_latency[port]['raw'][int(len(accounted_latency[port]['raw']) * 0.999) - 1]
        # #filter processing: filter all values that are greater than mid * 3
        # accounted_latency[port]['raw'] = [x for x in accounted_latency[port]['raw'] if x <= accounted_latency[port]['mid'] * 3]
        # accounted_latency[port]['raw'].sort()
        # accounted_latency[port]['avg'] = sum(accounted_latency[port]['raw']) / len(accounted_latency[port]['raw'])
        # accounted_latency[port]['mid'] = accounted_latency[port]['raw'][len(accounted_latency[port]['raw']) // 2]
        # accounted_latency[port]['p75'] = accounted_latency[port]['raw'][int(len(accounted_latency[port]['raw']) * 0.75) - 1]
        # accounted_latency[port]['p999'] = accounted_latency[port]['raw'][int(len(accounted_latency[port]['raw']) * 0.999) - 1]
    
    return sched_latency, accounted_latency

def process_experiment(result_dir, experiment, n_thread, save_id):
    print(f"[PID {os.getpid()}] Processing experiment: {experiment} with {n_thread} threads")

    experiment_dir = os.path.join(result_dir, experiment)
    client_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}.log")
    server_breakdown_path = os.path.join(experiment_dir, f"latencies-{n_thread}-server.log")

    client_sched, client_accounted = client_sched_parser(client_breakdown_path)
    server_sched, server_accounted = server_sched_parser(server_breakdown_path)

    client_save_path = os.path.join(experiment_dir, f"sched_client_{n_thread}.txt")
    server_save_path = os.path.join(experiment_dir, f"sched_server_{n_thread}.txt")

    # client_accounted_save_path = os.path.join(experiment_dir, f"accounted_client_{n_thread}.txt")
    # server_accounted_save_path = os.path.join(experiment_dir, f"accounted_server_{n_thread}.txt")

    with open(client_save_path, "w") as cf:
        cf.write("Port,Avg,Mid,P99.9\n")
        for port in sorted(client_sched.keys()):
            cf.write(
                f"{port},{client_sched[port]['avg']},"
                f"{client_sched[port]['mid']},{client_sched[port]['p999']}\n"
            )

    with open(server_save_path, "w") as sf:
        sf.write("Port,Avg,Mid,P99.9\n")
        for port in sorted(server_sched.keys()):
            sf.write(
                f"{port},{server_sched[port]['avg']},"
                f"{server_sched[port]['mid']},{server_sched[port]['p999']}\n"
            )

    # with open(client_accounted_save_path, "w") as caf:
    #     caf.write("Port,Avg,Mid,P75,P99.9,n\n")
    #     for port in sorted(client_accounted.keys()):
    #         caf.write(
    #             f"{port},{client_accounted[port]['avg']},"
    #             f"{client_accounted[port]['mid']},{client_accounted[port]['p75']},{client_accounted[port]['p999']},{len(client_accounted[port]['raw'])}\n"
    #         )
    # with open(server_accounted_save_path, "w") as saf:
    #     saf.write("Port,Avg,Mid,P75,P99.9,n\n")
    #     for port in sorted(server_accounted.keys()):
    #         saf.write(
    #             f"{port},{server_accounted[port]['avg']},"
    #             f"{server_accounted[port]['mid']},{server_accounted[port]['p75']},{server_accounted[port]['p999']},{len(server_accounted[port]['raw'])}\n"
    #         )

    # # draw different ports' raw accounted latency CDF
    # import matplotlib.pyplot as plt
    # plt.figure(figsize=(10, 10))
    # drawn = 0
    # for port in sorted(client_accounted.keys()):
    #     if drawn >= 26:
    #         break
    #     data = client_accounted[port]['raw']
    #     data.sort()
    #     yvals = np.arange(len(data)) / float(len(data))
    #     # calculate total data values in [0, 90%)
    #     total_data = sum(data[:int(len(data)*0.9)])
    #     print(data[0:10])
    #     plt.plot(data, yvals, label=f"Port {port} - {total_data} - {len(data)}", color=colors[int(port) % len(colors)], linestyle='-' if (int(port)<10013) else '--')
    #     drawn += 1
    # plt.xlabel("rx_data_copy wall time (ns)")
    # plt.ylabel("CDF")
    # plt.xlim(0, 500)
    # plt.grid()
    # plt.legend()
    # cdf_save_path = os.path.join(f"accounted_client_cdf_{save_id}.pdf")
    # plt.tight_layout()
    # plt.savefig(cdf_save_path)
    # plt.close()

    # plt.figure(figsize=(10, 10))
    # drawn = 0
    # for port in sorted(server_accounted.keys()):
    #     if drawn >= 26:
    #         break
    #     data = server_accounted[port]['raw']
    #     data.sort()
    #     yvals = np.arange(len(data)) / float(len(data))
    #     total_data = sum(data[:int(len(data)*0.9)])
    #     plt.plot(data, yvals, label=f"Port {port} - {total_data} - {len(data)}", color=colors[int(port) % len(colors)], linestyle='-' if (int(port)<10013) else '--')
    #     drawn += 1
    # plt.xlabel("rx_data_copy wall time (ns)")
    # plt.ylabel("CDF")
    # plt.xlim(0, 500)
    # plt.grid()
    # plt.legend()
    # cdf_save_path = os.path.join(f"accounted_server_cdf_{save_id}.pdf")
    # plt.tight_layout()
    # plt.savefig(cdf_save_path)
    # plt.close()

    return experiment  # just for logging in the parent


if __name__ == "__main__":
    result_dir = "/data0/projects/latency/"
    experiments = [
        # "sirq_pcbs_pktirq_1_1/48_64_1_1_1_1_0_0_1_0",
        # "sirq_pcbs_pktirq_1_1/48_64_1_1_1_1_0_0_1_1",
        # "sirq_pcbs_pktirq_1_1/48_64_1_1_1_1_0_0_1_2",
        # "sirq_pcbs_pktirq_1_1/48_64_1_1_1_1_0_0_1_3",
        # "sirq_pcbs_pktirq_1_1/48_64_1_1_1_1_0_0_1_4",
        # "sirq_pktirq_1_1/48_64_1_1_1_1_0_0_1_0",
        # "sirq_pktirq_1_1/48_64_1_1_1_1_0_0_1_1",
        # "sirq_pktirq_1_1/48_64_1_1_1_1_0_0_1_2",
        # "sirq_pktirq_1_1/48_64_1_1_1_1_0_0_1_3",
        # "sirq_pktirq_1_1/48_64_1_1_1_1_0_0_1_4",
        # "nirq_pktirq_vruntime_1_1/48_64_1_1_1_1_0_0_1_1",
        # "nirq_pktirq_vruntime_1_1/48_64_1_1_1_1_0_0_1_1",
        # "nirq_pktirq_vruntime_1_1/48_64_1_1_1_1_0_0_1_2",
        # "nirq_pktirq_vruntime_1_1/48_64_1_1_1_1_0_0_1_3",
        # "nirq_pktirq_vruntime_1_1/48_64_1_1_1_1_0_0_1_4",
        "sirq_breakdown_cores_1_1/48_64_1_1_1_1_0_0_16_0",
    ]
    n_threads = [
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