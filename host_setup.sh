#!/bin/bash
sudo systemctl stop apparmor
sudo systemctl disable apparmor
sudo aa-teardown
# Disable Atera Agent
sudo systemctl stop AteraAgent
sudo pkill -f Atera
sudo mv /etc/systemd/system/AteraAgent.service /etc/systemd/system/AteraAgent.service.bak
sudo systemctl daemon-reload

# Disable Deep C-State
for g in /sys/devices/system/cpu/cpu{32..47}/cpuidle/state{1,2,3}/disable /sys/devices/system/cpu/cpu{96..111}/cpuidle/state{1,2,3}/disable; do
  echo 1 | sudo tee "$g"
done

# Enable CPU performance mode
# for c in /sys/devices/system/cpu/cpu{32..47}/cpufreq/scaling_governor /sys/devices/system/cpu/cpu{96..111}/cpufreq/scaling_governor; do
#   echo "performance" | sudo tee "$c"
# done

# Get the dir of this project
DIR=$(realpath $(dirname $(readlink -f $0)))

# Source the environment file
source $DIR/env.sh
sudo ifconfig $INTF mtu 9000
sudo ifconfig $INTF $HOST
# Enable aRFS and configure network
sudo service irqbalance stop
# sudo ethtool -C $INTF adaptive-rx on adaptive-tx on
sudo ethtool -K $INTF ntuple on gro on gso on tso on lro off
echo 32768 | sudo tee /proc/sys/net/core/rps_sock_flow_entries
for f in /sys/class/net/$INTF/queues/rx-*/rps_flow_cnt; do echo 32768 | sudo tee $f; done
sudo ./mlnx_perf_tune/set_irq_affinity.sh $INTF

# Increase sock size limits
sudo sysctl -w net.core.wmem_max=12582912
sudo sysctl -w net.core.rmem_max=12582912

# Enable hardware timestamps
sudo hwstamp_ctl -i $INTF -r 1

#echo HRTICK | sudo tee /sys/kernel/debug/sched_features
#echo 100000 | sudo tee /proc/sys/kernel/sched_latency_ns
#echo 100000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns
sudo phc2sys -s CLOCK_REALTIME -c $INTF -O 0 -m &

# synchoronize the hardware timer
# phc2sys -a -r
# comppile compute app
#g++ -pthread compute_md.cpp -o compute

# change the open file limit
ulimit -n 8192
echo 451200 |sudo tee /sys/kernel/debug/tracing/buffer_size_kb
#sleep 10
echo "Setup host done!"
exit
