import os

n_cores = 128

def parse_ifconfig(path):
    """"ens1np0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 9000
        inet 192.168.1.101  netmask 255.255.255.0  broadcast 192.168.1.255
        inet6 fe80::9e63:c0ff:fe1a:39fc  prefixlen 64  scopeid 0x20<link>
        ether 9c:63:c0:1a:39:fc  txqueuelen 1000  (Ethernet)
        RX packets 474870308  bytes 1103980090095 (1.1 TB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 362884507  bytes 46658086687 (46.6 GB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
    """
    rx_packets = 0
    tx_packets = 0
    with open(path, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if "RX packets" in line:
                items = line.split()
                rx_packets = int(items[2])
            if "TX packets" in line:
                items = line.split()
                tx_packets = int(items[2])
    return rx_packets, tx_packets


def parse_softirq(path):
    softirqs = [{} for _ in range(n_cores)]
    with open(path, 'r') as f:
        lines = f.readlines()
        for line in lines[1:]:  # Skip the header line
            items = line.split()
            softirq = items[0]
            for i in range(n_cores):
                softirqs[i][softirq] = int(items[i + 1])
    return softirqs

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


def parse_run(run_dir):
    actual_packets_rx_before, actual_packets_tx_before = parse_ifconfig(os.path.join(run_dir, "ifconfig_before"))
    actual_packets_rx_after, actual_packets_tx_after = parse_ifconfig(os.path.join(run_dir, "ifconfig_after"))
    actual_packets_rx_before_server, actual_packets_tx_before_server = parse_ifconfig(os.path.join(run_dir, "ifconfig_before_server"))
    actual_packets_rx_after_server, actual_packets_tx_after_server = parse_ifconfig(os.path.join(run_dir, "ifconfig_after_server"))
    actual_packets_rx = actual_packets_rx_after - actual_packets_rx_before
    actual_packets_tx = actual_packets_tx_after - actual_packets_tx_before
    actual_packets_rx_server = actual_packets_rx_after_server - actual_packets_rx_before_server
    actual_packets_tx_server = actual_packets_tx_after_server - actual_packets_tx_before_server
    print(f"Actual RX packets: {actual_packets_rx}, Actual TX packets: {actual_packets_tx}")
    print(f"Actual RX packets (server): {actual_packets_rx_server}, Actual TX packets (server): {actual_packets_tx_server}")    

    client_interrupt_0 = os.path.join(run_dir, "interrupt_before")
    client_interrupt_1 = os.path.join(run_dir, "interrupt_after")
    server_interrupt_0 = os.path.join(run_dir, "interrupt_before_server")
    server_interrupt_1 = os.path.join(run_dir, "interrupt_after_server")

    client_arr_before = get_interrupt_arr(client_interrupt_0)
    client_arr_after = get_interrupt_arr(client_interrupt_1)
    server_arr_before = get_interrupt_arr(server_interrupt_0)
    server_arr_after = get_interrupt_arr(server_interrupt_1)

    client_diff = calculate_difference(client_arr_after, client_arr_before)
    server_diff = calculate_difference(server_arr_after, server_arr_before)
    client_diff.sort(reverse=True)
    server_diff.sort(reverse=True)
    client_total_interrupts = client_diff[0] + client_diff[1] # NOTE: Qizhe uses average for top 2 interrupts, but I just use sum.
    server_total_interrupts = server_diff[0] + server_diff[1]

    print(f"Client interrupts: {client_total_interrupts}, Server interrupts: {server_total_interrupts}")

    softirq_before = parse_softirq(os.path.join(run_dir, "softirq_before"))
    softirq_after = parse_softirq(os.path.join(run_dir, "softirq_after"))
    softirq_before_server = parse_softirq(os.path.join(run_dir, "softirq_before_server"))
    softirq_after_server = parse_softirq(os.path.join(run_dir, "softirq_after_server"))

    softirq_diff = [{} for _ in range(n_cores)]
    softirq_diff_server = [{} for _ in range(n_cores)]
    for i in range(n_cores):
        for softirq in softirq_before[i]:
            softirq_diff[i][softirq] = softirq_after[i][softirq] - softirq_before[i][softirq]
        for softirq in softirq_before_server[i]:
            softirq_diff_server[i][softirq] = softirq_after_server[i][softirq] - softirq_before_server[i][softirq]
    print(softirq_diff[32])
    print(softirq_diff_server[32])

    throughput_log = os.path.join(run_dir, "linux_latency")
    with open(throughput_log, 'r') as f:
        lines = f.readlines()
        throughput = float(lines[-1].split()[0])
    packets = throughput * duration
    print(f"Packets processed: {packets}")
    print(f"NET_RX per packet on core 32: {softirq_diff[32]['NET_RX:'] / packets}")
    print(f"NET_RX per packet on core 32 (server): {softirq_diff_server[32]['NET_RX:'] / packets}")
    print(f"TASKLET per packet on core 32: {softirq_diff[32]['TASKLET:'] / packets}")
    print(f"TASKLET per packet on core 32 (server): {softirq_diff_server[32]['TASKLET:'] / packets}")
    print(f"HardIRQ per packet on core 32: {client_total_interrupts / packets}")
    print(f"HardIRQ per packet on core 32 (server): {server_total_interrupts / packets}")


duration = 300
parse_run("/data0/projects/latency/p1_nirq_breakdown_cstate_2_9/1_64_1_1_1_1_0_0_1_3")