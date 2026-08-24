

source env.sh
source auth.sh

NAME="${1:?Usage: $0 <NAME> <SAVE_PATH>}"   # save name for this experiment
SAVE_PATH="${2:?Usage: $0 <NAME> <SAVE_PATH>}"   # output folder

CPU_CORE=32
EXP_TIME=300s
RATE_PER_THREAD=3000
RUNS_LIST=(0 1 2)
# THREADS_LIST=(2 4 6 8 10 12 14 16 18 20 22 24 26 28 30 32 36 40 48)
# THREADS_LIST=(18 20 22 24 26 28 30 32)
THREADS_LIST=(20 22 24 26 28)
DIM_STATE=off # = on, off, or autodim


SLEEP_BETWEEN=5

HTTP_HOST="192.168.1.102"
HTTP_RESOURCE="/hello_world.html"
HTTP_TARGET="http://${HTTP_HOST}${HTTP_RESOURCE}"

WRK_PATH="/home/ame/httpd_experiment/wrk2/wrk"

mkdir -p ${SAVE_PATH}

echo $SUDOPW | sudo -S echo "Local shell privilege escalation successful"

# Client side configuration
sudo trace-cmd clear
echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on
echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting
echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting

sudo sysctl -w net.core.latency_breakdown_on=1
sudo sysctl -w net.core.latency_breakdown_log=100
sudo sysctl -w net.core.latency_dumb_schedule_weight=1000
sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0 # 0 means enable clamp now
sudo sysctl -w net.core.latency_dumb_schedule_enable=0
sudo sysctl -w net.core.latency_dumb_schedule_strict=0

if [ "$DIM_STATE" != "autodim" ]; then
    sudo ethtool -C $INTF adaptive-rx $DIM_STATE adaptive-tx $DIM_STATE
fi


# Server side configuration
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S trace-cmd clear"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 1 | sudo tee /sys/kernel/debug/tracing/tracing_on"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting"

ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_on=1"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_log=100"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_weight=1000"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_disable_clamp=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_enable=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_strict=0"

if [ "$DIM_STATE" != "autodim" ]; then
    ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx $DIM_STATE adaptive-tx $DIM_STATE"
fi


# Experiments:
for n_threads in "${THREADS_LIST[@]}"; do
    for run in "${RUNS_LIST[@]}"; do
        log_file="${SAVE_PATH}/${NAME}_${n_threads}_DIM-${DIM_STATE}_${run}.log"
        server_breakdown="${SAVE_PATH}/${NAME}_${n_threads}_DIM-${DIM_STATE}_${run}_server_breakdown.log"
        client_breakdown="${SAVE_PATH}/${NAME}_${n_threads}_DIM-${DIM_STATE}_${run}_client_breakdown.log"
        sudo trace-cmd clear
        ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S trace-cmd clear"

        if [ "$DIM_STATE" == "autodim" ]; then
            # FRAMES=$((((n_threads)*2+1)/3))
            FRAMES=$(((n_threads)/2))
            USECS_SERVER=$(((n_threads)*5)) # ~100kIOPS -> 10us overhead per request
            USECS_CLIENT=$(((n_threads)*3)) # ~100kIOPS -> 10us overhead per request
            sudo ethtool -C $INTF adaptive-rx off adaptive-tx off rx-frames $FRAMES rx-usecs $USECS_CLIENT tx-frames $FRAMES tx-usecs $USECS_CLIENT
            ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx off adaptive-tx off rx-frames $FRAMES rx-usecs $USECS_SERVER tx-frames $FRAMES tx-usecs $USECS_SERVER"
            echo "Running ${HTTP_TARGET} with ${n_threads} threads, run ${run} of ${#RUNS_LIST[@]}, logging to ${log_file}, autodim with ${FRAMES} frames and ${USECS} usecs"
        else
            echo "Running ${HTTP_TARGET} with ${n_threads} threads, run ${run} of ${#RUNS_LIST[@]}, logging to ${log_file}"
        fi

        total_rate=$((n_threads * RATE_PER_THREAD))
        sudo taskset -c $CPU_CORE nice -n -20 ${WRK_PATH} \
            -t ${n_threads} -c ${n_threads} -d ${EXP_TIME} \
            -R ${total_rate} -U \
            ${HTTP_TARGET} \
            > ${log_file} 2>&1

        sudo cat /sys/kernel/debug/tracing/trace &> $client_breakdown
        ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S cat /sys/kernel/debug/tracing/trace > /home/ame/latency/temp/httpd-breakdown-server.log"
        scp $USER\@$TARGETC:/home/ame/latency/temp/httpd-breakdown-server.log $server_breakdown
        ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S rm -rf /home/ame/latency/temp/*"

        # We restart httpd to reset threads' vruntime, ensuring they have close inital vruntime.
        ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S systemctl restart apache2"
        sleep ${SLEEP_BETWEEN}
    done
done

echo 0 | sudo tee /sys/kernel/debug/tracing/tracing_on
echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting
echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting

sudo sysctl -w net.core.latency_breakdown_on=0
sudo sysctl -w net.core.latency_dumb_schedule_weight=1000
sudo sysctl -w net.core.latency_dumb_schedule_disable_clamp=0 # 0 means enable clamp now
sudo sysctl -w net.core.latency_dumb_schedule_enable=0
sudo sysctl -w net.core.latency_dumb_schedule_strict=0
sudo ethtool -C $INTF adaptive-rx off adaptive-tx off


ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 0 | sudo tee /sys/kernel/debug/tracing/tracing_on"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 0 | sudo tee /sys/module/core/parameters/accu_irq_accounting"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S -v; echo 0 | sudo tee /sys/module/core/parameters/scheduler_accounting"

ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_breakdown_on=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_weight=1000"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_disable_clamp=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_enable=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S sysctl -w net.core.latency_dumb_schedule_strict=0"
ssh $USER\@$TARGETC -t "echo $SUDOPW | sudo -S ethtool -C $INTF adaptive-rx off adaptive-tx off"
