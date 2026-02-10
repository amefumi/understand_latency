#!/bin/bash
IFACE=ens1np0
readlink -f /sys/class/net/$IFACE/ptp
PTPN=$(basename "$(readlink -f /sys/class/net/$IFACE/ptp)")
echo "/dev/$PTPN"

sudo phc_ctl /dev/$PTPN get