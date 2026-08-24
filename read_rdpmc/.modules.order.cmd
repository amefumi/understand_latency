cmd_/home/ame/latency/read_rdpmc/modules.order := {   echo /home/ame/latency/read_rdpmc/latency_pmu.ko; :; } | awk '!x[$$0]++' - > /home/ame/latency/read_rdpmc/modules.order
