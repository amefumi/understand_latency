#!/bin/bash

N=$1
DIR=$2
SIZE=$3
IODEPTH=$4
# DIM_DISABLED = 0, DIM_ENABLED = 1
DIM=$5
# off = 0, on = 1
PIN=$6
PERMUTE=$7
HRTICK=$8
SCHE=$9
SC=${10}
RUN=${11}
DIM_MONITOR=${12}
DPORT=5001

CLIENT_TIME=300

# Check if the first parameter exists
if [ -z "${13}" ]; then
  TIMEOUT=8
else
  TIMEOUT=${13}
fi

# Check if the second parameter exists
if [ -z "${14}" ]; then
  PKT=128
else
  PKT=${14}
fi
# DIR=$(realpath $(dirname $(readlink -f $0)))
source env.sh
source auth.sh

echo $SUDOPW | sudo -S echo "Local shell privilege escalation successful"

echo "$TIMEOUT"
echo "$PKT"
echo "$DIR"

LOG=$((997 / N))
if [[ $N -gt 10 ]]; then LOG=200; fi
#LOG=249

uname -r > $DIR/kernel_version.log

# client-side
sudo trace-cmd clear
sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_rx_sched_lat_only=0
sudo sysctl -w net.core.latency_breakdown_nrfs=0
sudo sysctl -w net.core.latency_breakdown_log=$LOG
echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on
echo 1 | sudo tee /sys/module/core/parameters/accu_irq_accounting

# server-side
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S trace-cmd clear"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_on=1"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_rx_sched_lat_only=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_nrfs=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_log=$LOG"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 1 | sudo tee /sys/module/core/parameters/accu_irq_accounting"



if [[ $SCHE -eq 0 ]];
then
	echo 24000000 | sudo tee /proc/sys/kernel/sched_latency_ns
	echo 3000000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 24000000 | sudo tee /proc/sys/kernel/sched_latency_ns"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 3000000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns"
else
	echo "$SCHE"000 | sudo tee /proc/sys/kernel/sched_latency_ns
	echo "$SCHE"000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo "$SCHE"000 | sudo tee /proc/sys/kernel/sched_latency_ns"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo "$SCHE"000 | sudo tee /proc/sys/kernel/sched_min_granularity_ns"
fi

if [[ $HRTICK -eq 1 ]];
then
	echo HRTICK | sudo tee /sys/kernel/debug/sched_features
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo HRTICK | sudo tee /sys/kernel/debug/sched_features"
else
	echo NO_HRTICK | sudo tee /sys/kernel/debug/sched_features
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo NO_HRTICK | sudo tee /sys/kernel/debug/sched_features"
fi

if [[ $DIM -eq 1 ]];
then
	echo "enable dim"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx on adaptive-tx on"
	sudo ethtool -C $INTF adaptive-rx on adaptive-tx on
elif [[ $DIM -eq 0 ]];
then
	echo "disable dim"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx off adaptive-tx off"
#	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo ethtool -C $INTF rx-frames $PKT rx-usecs $TIMEOUT tx-frames $PKT tx-usecs $TIMEOUT"
	sudo ethtool -C $INTF adaptive-rx off adaptive-tx off
#	sudo ethtool -C $INTF rx-frames $PKT rx-usecs $TIMEOUT tx-frames $PKT tx-usecs $TIMEOUT
else
	echo "half dim: rx on, tx off"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx on adaptive-tx off"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF tx-frames 128 tx-usecs 32"
	sudo ethtool -C $INTF adaptive-rx on adaptive-tx off
	sudo ethtool -C $INTF tx-frames 128 tx-usecs 32
fi


# packet distribution
# sudo insmod $TARGETDIR/pkt_dist/filter.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo insmod $TARGETDIR/pkt_dist/filter.ko"
# echo 1 | sudo tee /sys/module/filter/parameters/enable_filter
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && echo 1 | sudo tee /sys/module/filter/parameters/enable_filter"


#TASKSET="0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60"
#TASKSET="32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111"
if [[ $SC -eq 1 ]];
then
	TASKSET="32,96"
else
	TASKSET="32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111"
fi

cat /proc/interrupts > $DIR/interrupt_before
cat /proc/softirqs > $DIR/softirq_before
ifconfig $INTF > $DIR/ifconfig_before
ssh $USER\@$TARGETC -t "cat /proc/interrupts" > $DIR/interrupt_before_server
ssh $USER\@$TARGETC -t "cat /proc/softirqs" > $DIR/softirq_before_server
ssh $USER\@$TARGETC -t "ifconfig $INTF" > $DIR/ifconfig_before_server

 #total_count=1200 interval_ms=100
sudo insmod $TARGETDIR/iter_thread/iter_thread.ko total_count=300
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S insmod $TARGETDIR/iter_thread/iter_thread.ko total_count=300"

# enable netfilter 
sudo insmod $TARGETDIR/netfilter/filter.ko
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S insmod $TARGETDIR/netfilter/filter.ko"
# echo 5200 | sudo tee /sys/module/filter/parameters/base_target
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 5200 | sudo tee /sys/module/filter/parameters/base_target"
echo 1 | sudo tee /sys/module/filter/parameters/enable_filter
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 1 | sudo tee /sys/module/filter/parameters/enable_filter"

# ssh $USER\@$TARGETC -t "sudo taskset -c $TASKSET nice -n -20 $TARGETDIR/latency/pingpong_server  --ip $TARGET --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE --pin > $TARGETDIR/latency/temp/server.log" &
# ssh $USER@$TARGETC -t "seq 12 | while read i; do date '+%F %T' >> $TARGETDIR/latency/temp/dim.log; ethtool -c $INTF | egrep 'Adaptive RX|rx-usecs:|rx-frames:|tx-usecs:|tx-frames:' >> $TARGETDIR/latency/temp/dim_server.log; sleep 5; done" &

# # bpftrace for softirq net_rx
# sudo timeout 310 /usr/bin/bpftrace $TARGETDIR/latency/softirq_net_rx.bt > $TARGETDIR/latency/temp/bpf_client.log &
# ssh $USER\@$TARGETC -t "cd /home/ame && echo $SUDOPW | sudo -S timeout 310 /usr/bin/bpftrace $TARGETDIR/latency/softirq_net_rx.bt > $TARGETDIR/latency/temp/bpf_server.log" &

ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S taskset -c $TASKSET nice -n -20 $TARGETDIR/latency/pingpong_server_perf  --ip $TARGET --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --permute $PERMUTE --sc $SC --time $CLIENT_TIME > $TARGETDIR/latency/temp/server.log" &
echo "sudo taskset -c $TASKSET nice -n -20 $TARGETDIR/latency/pingpong_server_perf  --ip $TARGET --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --time $CLIENT_TIME > $TARGETDIR/latency/temp/server.log"
sleep 3

# seq 24 | while read i; do date "+%F %T" >> temp/dim.log; ethtool -c $INTF | egrep "Adaptive RX|rx-usecs:|rx-frames:|tx-usecs:|tx-frames:" >> temp/dim.log; sleep 5; done &
sudo taskset -c $TASKSET nice -n -20 ./netdriver_test_multithread_perf $TARGET:$DPORT --count $N  --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --sc $SC --time $CLIENT_TIME tcpppasync  > temp/client.log &
echo "echo $SUDOPW | sudo -S taskset -c $TASKSET nice -n -20 ./netdriver_test_multithread_perf $TARGET:$DPORT --count $N  --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --sc $SC --time $CLIENT_TIME tcpppasync"
PIDS="$PIDS $!"
echo "pid $PIDS dport $DPORT"

sar -u 60 $((CLIENT_TIME/60 - 1)) -P ALL > $DIR/cpu-$N.log &
ssh $USER\@$TARGETC -t "sar -u 60 $((CLIENT_TIME/60 - 1)) -P ALL" > $DIR/cpu-server-$N.log &

# perf for context switch counting
# sudo /home/ame/perf stat --per-thread -e context-switches -p $(pidof netdriver_test_multithread) -- sleep 300 > temp/perf_client.log 2>&1 &
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S /home/ame/perf stat --per-thread -e context-switches -p \$(pidof pingpong_server) -- sleep 300 > $TARGETDIR/latency/temp/perf_server.log 2>&1" &

# Start record DIM
if [[ $DIM_MONITOR -eq 1 ]];
then
	echo 'p:mlx5_cq_mod mlx5_core_modify_cq_moderation cqn=+0(%si):u32 period=%dx:u16 count=%cx:u16' | sudo tee /sys/kernel/debug/tracing/kprobe_events
	echo 1 | sudo tee /sys/kernel/debug/tracing/events/kprobes/mlx5_cq_mod/enable
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && echo 'p:mlx5_cq_mod mlx5_core_modify_cq_moderation cqn=+0(%si):u32 period=%dx:u16 count=%cx:u16' | sudo tee /sys/kernel/debug/tracing/kprobe_events"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && echo 1 | sudo tee /sys/kernel/debug/tracing/events/kprobes/mlx5_cq_mod/enable"
	echo "DIM Monitoring."
fi


# sleep 60
# only do server perf only
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo $TARGETDIR/perf sched record -C 0 -k CLOCK_MONOTONIC -- sleep 10 > perf.log; sudo $TARGETDIR/perf sched script > server_perf.log &" &

# sudo ../perf sched record -C 0 -k CLOCK_MONOTONIC -- sleep 30
# sudo ../perf sched script > temp/client_perf.log


# queue size
# sleep 30
# sudo insmod $TARGETDIR/iter_sock/iterate_inet_socks.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo insmod $TARGETDIR/iter_sock/iterate_inet_socks.ko"
# get perf
# sleep 60
# only do server perf only
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo $TARGETDIR/perf sched record -C 0 -k CLOCK_MONOTONIC -- sleep 30 > perf.log; sudo $TARGETDIR/perf sched script > server_perf.log &" &
# sudo ../perf sched record -C 0 -k CLOCK_MONOTONIC -- sleep 30
# sudo ../perf sched script > temp/client_perf.log




wait $PIDS
kill -9 $PIDS2

echo $SUDOPW | sudo -S echo "Local shell privilege escalation after experiment successful"

# get compute log
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S killall compute_md"
sleep 15 # wait for server side perf/bpftrace to finish
# scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/compute*.log temp/
scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/server.log temp/
scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/bpf_server.log temp/
# scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/dim_server.log temp/
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S rm -rf $TARGETDIR/latency/temp/compute*.log"

PIDS2="$!"
# client-side
sudo sysctl -w net.core.latency_breakdown_on=0
sudo sysctl -w net.core.latency_rx_sched_lat_only=0
sudo sysctl -w net.core.latency_breakdown_nrfs=0
sudo cat /sys/kernel/debug/tracing/trace &> $DIR/latencies-$N.log
sudo trace-cmd clear
echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting


# remove filter
# We suppose to have 4*6*5 = 120 log entries for each time. Due to unwanted logs, we set 230 here (it will be safe as long as it is less than 2*120=240)
# 30000 entries for packet runqueue
sudo rmmod filter.ko
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo rmmod filter.ko"
# sudo tail -n 30000  /var/log/kern.log > temp/filter_client.log
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo tail -n 30000  /var/log/kern.log" > temp/filter_server.log

sleep 15 # wait for server side to finish perf logging

# server-side
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_on=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_rx_sched_lat_only=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_nrfs=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S cat /sys/kernel/debug/tracing/trace" > $DIR/latencies-$N-server.log
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S trace-cmd clear"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S killall pingpong_server"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"

# Stop record DIM
if [[ $DIM_MONITOR -eq 1 ]];
then
	echo 0 | sudo tee /sys/kernel/debug/tracing/events/kprobes/mlx5_cq_mod/enable
	echo "-:mlx5_cq_mod" | sudo tee /sys/kernel/debug/tracing/kprobe_events
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && echo 0 | sudo tee /sys/kernel/debug/tracing/events/kprobes/mlx5_cq_mod/enable"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && echo "-:mlx5_cq_mod" | sudo tee /sys/kernel/debug/tracing/kprobe_events"
	mv $DIR/latencies-$N.log $DIR/dim.log
	mv $DIR/latencies-$N-server.log $DIR/dim_server.log
	echo "DIM Monitoring stopped."
fi

# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo ../perf sched script > temp/server_perf.log"
# scp -r $USER\@$TARGETC:/home/$USER/server_perf.log temp/

# remove iter sock
# sudo rmmod iterate_inet_socks.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo rmmod iterate_inet_socks.ko"

#remove pkt_dist
# sudo rmmod filter.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo rmmod filter.ko"
# sudo tail -n 60  /var/log/kern.log > temp/pkt_dist_client.log
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo tail -n 61  /var/log/kern.log" > temp/pkt_dist_server.log

# remove iter_thread
# 550 for only iter_thread, 700 for both iter_thread and filter, 6000 for finer details
sudo rmmod iter_thread
sudo tail -n 1700  /var/log/kern.log > $DIR/iter_thread_client.log
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S rmmod iter_thread"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S tail -n 1700  /var/log/kern.log" > $DIR/iter_thread_server.log


sudo mv temp/*.log $DIR/
# move histogram data to result dir
sudo mv temp/*.bin $DIR/
./parse/parse-netperf.py $DIR $N > $DIR/linux_latency
# if [[ $IODEPTH -eq 1 ]];
# then
# 	./parse/parse-breakdown-server.py $DIR $N > $DIR/linux_latency_breakdown_s
# 	./parse/parse-breakdown.py $DIR $N >  $DIR/linux_latency_breakdown_c 
# else
# 	./parse/parse-breakdown-rx_sched_c.py $DIR $N > $DIR/linux_latency_breakdown_rx_sched_c 
# 	./parse/parse-breakdown-rx_sched_s.py $DIR $N > $DIR/linux_latency_breakdown_rx_sched_s
# fi

cat /proc/interrupts > $DIR/interrupt_after
ssh $USER\@$TARGETC -t "cat /proc/interrupts" > $DIR/interrupt_after_server
cat /proc/softirqs > $DIR/softirq_after
ssh $USER\@$TARGETC -t "cat /proc/softirqs" > $DIR/softirq_after_server
ifconfig $INTF > $DIR/ifconfig_after
ssh $USER\@$TARGETC -t "ifconfig $INTF" > $DIR/ifconfig_after_server

# PIDS="$PIDS $!"
# ./parse/parse-breakdown-server.py $DIR $N > $DIR/linux_latency_breakdown_s
# ./parse/parse-breakdown.py $DIR $N >  $DIR/linux_latency_breakdown_c 
# python3 parse/parse_vruntime.py $DIR/client_perf.log $((N/SC)) > $DIR/runtime_diff
# python3 parse/parse_vruntime.py $DIR/server_perf.log $((N/SC)) > $DIR/runtime_diff_server
echo "done"  
