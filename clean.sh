# !/bin/bash
sudo killall netdriver_test_mutihread
sudo killall pingpong_server
sudo killall bpftrace
sudo rmmod iter_thread
sudo rmmod filter
sudo killall sleep