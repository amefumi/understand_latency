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

# DIR=$(realpath $(dirname $(readlink -f $0)))
source env.sh
source auth.sh

echo $SUDOPW | sudo -S echo "Local shell privilege escalation successful"

echo "$DIR"

LOG=$((997 / N))
if [[ $N -gt 10 ]]; then LOG=200; fi

uname -r > $DIR/kernel_version.log

# client-side
sudo trace-cmd clear
sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_rx_sched_lat_only=0
sudo sysctl -w net.core.latency_breakdown_nrfs=0
sudo sysctl -w net.core.latency_breakdown_log=$LOG
sudo sysctl -w net.core.latency_breakdown_validation=0
sudo sysctl -w net.core.latency_dumb_schedule_weight=156
sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0 # 0 means enable clamp now
sudo sysctl -w net.core.latency_dumb_schedule_enable=0
sudo sysctl -w net.core.latency_perstage_rdpmc_on=0 # enable rdpmc for latency breakdown
# sudo sysctl -w kernel.sched_wakeup_granularity_ns=999999999 # Note: this is used to disable wake up preemption

echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on
echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting
echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting


# server-side
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S trace-cmd clear"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_on=1"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_rx_sched_lat_only=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_nrfs=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_log=$LOG"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_validation=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_weight=156"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_disable_clamp=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_enable=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_perstage_rdpmc_on=0"
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w kernel.sched_wakeup_granularity_ns=999999999" # Note: this is used to disable wake up preemption

ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting"


# Customized scheduler settings:
# 	* sched_latency_ns: the threshold for woken thread to have virtual runtime clamped.
# 	* sched_min_granularity_ns: the threshold for woken thread to preempt current running thread.
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


# HRTICK settings: HRTICK = 1, NO_HRTICK = 0
if [[ $HRTICK -eq 1 ]];
then
	echo "[HRTICK] Enabled"
	echo HRTICK | sudo tee /sys/kernel/debug/sched_features
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo HRTICK | sudo tee /sys/kernel/debug/sched_features"
else
	echo "[HRTICK] Disabled"
	echo NO_HRTICK | sudo tee /sys/kernel/debug/sched_features
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo NO_HRTICK | sudo tee /sys/kernel/debug/sched_features"
fi


# DIM settings: DIM_DISABLED = 0, DIM_ENABLED = 1, DIM_AUTO = 2
if [[ $DIM -eq 0 ]];
then
	echo "[DIM] Disabled"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx off adaptive-tx off"
	sudo ethtool -C $INTF adaptive-rx off adaptive-tx off
elif [[ $DIM -eq 1 ]];
then
	echo "[DIM] Enabled"
	ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx on adaptive-tx on"
	sudo ethtool -C $INTF adaptive-rx on adaptive-tx on
else
    FRAMES=$(((N/SC+3)/4))	# frames = N/4
	# USECS=$(((5*N/SC+3)/4)) # usecs = (N/4) * (1/(0.4/2)) = 1.25 * N
    USECS=$((N/SC)) # usecs = N
    echo "[DIM] Automatic tuning: rx/tx-frames: $FRAMES rx/tx-usecs:  $USECS"
    ssh $USER@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx off adaptive-tx off"
    ssh $USER@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF \
        rx-frames $FRAMES rx-usecs $USECS \
        tx-frames $FRAMES tx-usecs $USECS"
    sudo ethtool -C $INTF adaptive-rx off adaptive-tx off
    sudo ethtool -C $INTF \
        rx-frames $FRAMES rx-usecs $USECS \
        tx-frames $FRAMES tx-usecs $USECS
fi


# # eanble packet distribution
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

# Enable rdpmc monitoring
# echo 0 | sudo tee /proc/sys/kernel/nmi_watchdog
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 0 | sudo tee /proc/sys/kernel/nmi_watchdog"
# sudo insmod /home/ame/latency/read_rdpmc/latency_pmu.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S insmod /home/ame/latency/read_rdpmc/latency_pmu.ko"


# #　Enable virtual runtime monitoring: total_count=1200 interval_ms=100
# sudo insmod $TARGETDIR/iter_thread/iter_thread.ko total_count=300 interval_ms=1000
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S insmod $TARGETDIR/iter_thread/iter_thread.ko total_count=300 interval_ms=1000"

# # # Enable Netfilter
# sudo insmod $TARGETDIR/netfilter/filter.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S insmod $TARGETDIR/netfilter/filter.ko"
# # echo 5200 | sudo tee /sys/module/filter/parameters/base_target
# # ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 5200 | sudo tee /sys/module/filter/parameters/base_target"
# echo 1 | sudo tee /sys/module/filter/parameters/enable_filter
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 1 | sudo tee /sys/module/filter/parameters/enable_filter"

# # Enable softIRQ counts and time monitoring with bpftrace
# sudo timeout 310 /usr/bin/bpftrace $TARGETDIR/latency/softirq_net_rx.bt > $TARGETDIR/latency/temp/bpf_client.log &
# ssh $USER\@$TARGETC -t "cd /home/ame && echo $SUDOPW | sudo -S timeout 310 /usr/bin/bpftrace $TARGETDIR/latency/softirq_net_rx.bt > $TARGETDIR/latency/temp/bpf_server.log" &

# # Perf: calling sample with per certain cache misses
# echo $SUDOPW | sudo -S /home/ame/perf record -a -g -e cache-misses -c 31 -o $DIR/cache_sample_client.data -- sleep $CLIENT_TIME &
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S /home/ame/perf record -a -g -e cache-misses -c 31 -o $TARGETDIR/latency/temp/cache_sample_server.data -- sleep $CLIENT_TIME" &

# Perf: periodic flamegraph sampling
# echo $SUDOPW | sudo -S /home/ame/perf record -o $TARGETDIR/latency/temp/perf_sample_client.data -C 32 -F 199 -a -g -- sleep $CLIENT_TIME &
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S /home/ame/perf record -o $TARGETDIR/latency/temp/perf_sample_server.data -C 32 -F 199 -a -g -- sleep $CLIENT_TIME" &

# # Perf: measure general cache miss measurement
# echo $SUDOPW | sudo -S /home/ame/perf stat -C 32 -e cache-references,cache-misses -- sleep $CLIENT_TIME &> $TARGETDIR/latency/temp/perf_overall_cache.log &
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S /home/ame/perf stat -C 32 -e cache-references,cache-misses -- sleep $CLIENT_TIME &> $TARGETDIR/latency/temp/perf_overall_cache_server.log" &

# # Perf: L1-dcache-loads, L1-dcache-load-misses, and dTLB-load-misses
# echo $SUDOPW | sudo -S /home/ame/perf stat -C 32 -e cpu/event=0xd0,umask=0x81/,cpu/event=0x24,umask=0xe1/,cpu/event=0x12,umask=0x0e/ -- sleep $CLIENT_TIME &> $TARGETDIR/latency/temp/perf_overall_cache_client.log &
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S /home/ame/perf stat -C 32 -e cpu/event=0xd0,umask=0x81/,cpu/event=0x24,umask=0xe1/,cpu/event=0x12,umask=0x0e/ -- sleep $CLIENT_TIME &> $TARGETDIR/latency/temp/perf_overall_cache_server.log" &

# # Perf: L1-dcache-stores, dTLB-store-misses
# echo $SUDOPW | sudo -S /home/ame/perf stat -C 32 -e cpu/event=0xd0,umask=0x82/,cpu/event=0x13,umask=0x0e/ -- sleep $CLIENT_TIME &> $TARGETDIR/latency/temp/perf_overall_cache_client.log &
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S /home/ame/perf stat -C 32 -e cpu/event=0xd0,umask=0x82/,cpu/event=0x13,umask=0x0e/ -- sleep $CLIENT_TIME &> $TARGETDIR/latency/temp/perf_overall_cache_server.log" &

# # Perf: L2d-cache-loads, L2d-cache-load-misses, LLC-loads
# echo $SUDOPW | sudo -S /home/ame/pmu-tools/ocperf.py stat -C 32 -e L2_RQSTS.ALL_DEMAND_DATA_RD,L2_RQSTS.DEMAND_DATA_RD_MISS,OCR.DEMAND_DATA_RD.ANY_RESPONSE -- sleep $CLIENT_TIME &> $TARGETDIR/latency/temp/perf_overall_cache_client.log &
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S /home/ame/pmu-tools/ocperf.py stat -C 32 -e L2_RQSTS.ALL_DEMAND_DATA_RD,L2_RQSTS.DEMAND_DATA_RD_MISS,OCR.DEMAND_DATA_RD.ANY_RESPONSE -- sleep $CLIENT_TIME &>$TARGETDIR/latency/temp/perf_overall_cache_server.log" &

# Perf: L2d-cache-load-misses, LLC-load-misses
# echo $SUDOPW | sudo -S /home/ame/pmu-tools/ocperf.py stat -C 32 -e L2_RQSTS.DEMAND_DATA_RD_MISS,OCR.DEMAND_DATA_RD.L3_MISS -- sleep $CLIENT_TIME &> $TARGETDIR/latency/temp/perf_overall_cache_client.log &
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S /home/ame/pmu-tools/ocperf.py stat -C 32 -e L2_RQSTS.DEMAND_DATA_RD_MISS,OCR.DEMAND_DATA_RD.L3_MISS -- sleep $CLIENT_TIME &>$TARGETDIR/latency/temp/perf_overall_cache_server.log" &

# # Perf: try to sample l1-dcache-load-misses
# echo $SUDOPW | sudo -S /home/ame/perf record -C 32 -e cpu/event=0x24,umask=0xe1/ -c 10000 -o $DIR/cache_sample_client.data -- sleep $CLIENT_TIME &

# Start server side
ssh $USER\@$TARGETC -t "python3 $TARGETDIR/latency/get_involuntary_ctx_switch.py --time 300 > $TARGETDIR/latency/temp/server_nivcsw.log" &
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S taskset -c $TASKSET nice -n -20 $TARGETDIR/latency/pingpong_server  --ip $TARGET --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --permute $PERMUTE --sc $SC > $TARGETDIR/latency/temp/server.log" &
ssh $USER\@$TARGETC -t "
  echo '$SUDOPW' | sudo -S zsh -c '
    ulimit -n 65536
    exec taskset -c $TASKSET nice -n -20 $TARGETDIR/latency/pingpong_server \
      --ip $TARGET --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE \
      --pin $PIN --permute $PERMUTE --sc $SC \
      > $TARGETDIR/latency/temp/server.log 2>&1
  '
" &

echo "sudo taskset -c $TASKSET nice -n -20 $TARGETDIR/latency/pingpong_server  --ip $TARGET --port $((DPORT)) --count $N --iodepth $IODEPTH --flowsize $SIZE --pin $PIN  > $TARGETDIR/latency/temp/server.log"
sleep 3

# seq 24 | while read i; do date "+%F %T" >> temp/dim.log; ethtool -c $INTF | egrep "Adaptive RX|rx-usecs:|rx-frames:|tx-usecs:|tx-frames:" >> temp/dim.log; sleep 5; done &
# sudo taskset -c $TASKSET nice -n -20 ./netdriver_test_multithread $TARGET:$DPORT --count $N  --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --sc $SC --time $CLIENT_TIME tcpppasync  > temp/client.log &
sudo zsh -c 'ulimit -n 65536; exec taskset -c '"$TASKSET"' nice -n -20 ./netdriver_test_multithread '"$TARGET"':'"$DPORT"' --count '"$N"'  --iodepth '"$IODEPTH"' --flowsize '"$SIZE"' --pin '"$PIN"' --sc '"$SC"' --time '"$CLIENT_TIME"' tcpppasync > temp/client.log' &

echo "echo $SUDOPW | sudo -S taskset -c $TASKSET nice -n -20 ./netdriver_test_multithread $TARGET:$DPORT --count $N  --iodepth $IODEPTH --flowsize $SIZE --pin $PIN --sc $SC --time $CLIENT_TIME tcpppasync"
PIDS="$PIDS $!"
echo "pid $PIDS dport $DPORT"

sar -u 60 $((CLIENT_TIME/60 - 1)) -P ALL > $DIR/cpu-$N.log &
ssh $USER\@$TARGETC -t "sar -u 60 $((CLIENT_TIME/60 - 1)) -P ALL" > $DIR/cpu-server-$N.log &

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

# # Perf: generate flamegraph after periodic calling graph sampling
# sudo /home/ame/perf script -i $TARGETDIR/latency/temp/perf_sample_client.data > $TARGETDIR/latency/temp/perf_sample_client.perf
# /home/ame/Flamegraph/stackcollapse-perf.pl $TARGETDIR/latency/temp/perf_sample_client.perf > $TARGETDIR/latency/temp/perf_sample_client.folded
# /home/ame/Flamegraph/flamegraph.pl $TARGETDIR/latency/temp/perf_sample_client.folded > $TARGETDIR/latency/temp/perf_sample_client.svg
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S /home/ame/perf script -i $TARGETDIR/latency/temp/perf_sample_server.data > $TARGETDIR/latency/temp/perf_sample_server.perf"
# ssh $USER\@$TARGETC -t "/home/ame/Flamegraph/stackcollapse-perf.pl $TARGETDIR/latency/temp/perf_sample_server.perf > $TARGETDIR/latency/temp/perf_sample_server.folded"
# ssh $USER\@$TARGETC -t "/home/ame/Flamegraph/flamegraph.pl $TARGETDIR/latency/temp/perf_sample_server.folded > $TARGETDIR/latency/temp/perf_sample_server.svg"

scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/server.log temp/
scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/server_nivcsw.log temp/
# scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/perf_sample_server.svg temp/ # should not need privilege?
# scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/perf_overall_cache_server.log temp/

# # Perf: copy perf data with correct permission: note this seems to be useless, perf data cannot be understood cross machines
# REF_FILE=$TARGETDIR/latency/temp/server.log
# PERF_FILE=$TARGETDIR/latency/temp/cache_sample_server.data
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo chown --reference=$REF_FILE $PERF_FILE && sudo chmod --reference=$REF_FILE $PERF_FILE"
# scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/cache_sample_server.data temp/

# scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/bpf_server.log temp/
# scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/dim_server.log temp/
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S rm -rf $TARGETDIR/latency/temp/compute*.log"

PIDS2="$!"
# client-side
sudo sysctl -w net.core.latency_breakdown_on=0
sudo sysctl -w net.core.latency_rx_sched_lat_only=0
sudo sysctl -w net.core.latency_breakdown_nrfs=0
sudo sysctl -w net.core.latency_breakdown_validation=0
sudo sysctl -w net.core.latency_dumb_schedule_weight=156 # just reset to default value
sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0
sudo sysctl -w net.core.latency_dumb_schedule_enable=0
sudo sysctl -w net.core.latency_perstage_rdpmc_on=0

# sudo sysctl -w kernel.sched_wakeup_granularity_ns=4000000

sudo cat /sys/kernel/debug/tracing/trace &> $DIR/latencies-$N.log
sudo trace-cmd clear
echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting
echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting

# output involuntary context switch count in server side: get_involuntary_ctx_switch.py. Note the client side data are directly printed in netdriver_test_multithread.cc to client.log

# server-side
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_on=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_rx_sched_lat_only=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_nrfs=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_validation=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_weight=156"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_disable_clamp=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_enable=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_perstage_rdpmc_on=0"

# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w kernel.sched_wakeup_granularity_ns=4000000"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S cat /sys/kernel/debug/tracing/trace > $TARGETDIR/latency/temp/latencies-$N-server.log"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S trace-cmd clear"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S killall pingpong_server"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting"

# move latencies log
scp -r $USER\@$TARGETC:$TARGETDIR/latency/temp/latencies-$N-server.log $DIR
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S rm -rf $TARGETDIR/latency/temp/*"

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

# # Stop processed packets in softIRQ monitoring:
# # 		We suppose to have 4*6*5 = 120 log entries for each time. Due to unwanted logs, we set 230 here (it will be safe as long as it is less than 2*120=240)
# # 		30000 entries for packet runqueue.
# #			Also note we can output the results along with virtual runtime.
# sudo rmmod filter.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo rmmod filter.ko"
# sudo tail -n 300  /var/log/kern.log > temp/filter_client.log
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo tail -n 300  /var/log/kern.log" > temp/filter_server.log

# # remove iter sock
# # sudo rmmod iterate_inet_socks.ko
# # ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo rmmod iterate_inet_socks.ko"

# #remove pkt_dist
# sudo rmmod filter.ko
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo rmmod filter.ko"
# sudo tail -n 500  /var/log/kern.log > temp/pkt_dist_client.log
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v && sudo tail -n 500  /var/log/kern.log" > temp/pkt_dist_server.log

# # Stop virtual runtime monitoring:
# 	# 550 for only iter_thread, 700 for both iter_thread and filter, 6000 for finer details
# sudo rmmod iter_thread
# sudo tail -n 1700  /var/log/kern.log > $DIR/iter_thread_client.log
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S rmmod iter_thread"
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S tail -n 1700  /var/log/kern.log" > $DIR/iter_thread_server.log

# Stop rdpmc monitoring
# echo 1 | sudo tee /proc/sys/kernel/nmi_watchdog
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 1 | sudo tee /proc/sys/kernel/nmi_watchdog"
# sudo rmmod latency_pmu
# ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S rmmod latency_pmu"

# Move data to experiment result folder
sudo mv temp/*.log $DIR/
sudo mv temp/*.bin $DIR/
# sudo mv temp/cache_sample_server.data $DIR/
# sudo mv temp/perf_sample_client.svg $DIR/
# sudo mv temp/perf_sample_server.svg $DIR/
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
