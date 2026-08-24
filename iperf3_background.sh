
IPERF3_BIN=/home/ame/iperf3-18/src/iperf3

sudo taskset -c 32 $IPERF3_BIN -s

# Note --bidir -P 8 will create 16 parallel threads
sudo taskset -c 32 $IPERF3_BIN -c 192.168.1.101 --bidir -P 8 -t 300 -i 10 > iperf3_bidir_8P_300s.log 2>&1