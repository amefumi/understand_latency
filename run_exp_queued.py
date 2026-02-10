import os
import subprocess
from itertools import product

# Define parameters
#hd="sirq_pcbs_breakdown_cores"
# hd="sirq_pcbs_segdist_iodepth"
hd="sirq_eevdf_66_curve"
our_patch="2"
c_state="1"
# num_apps = [1, 2, 4, 8, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64]
# num_apps = [16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64]
# num_apps = [34, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72]
num_apps = [1, 2, 4, 8, 12, 16, 20, ]# 24, 28, 32, 36, 40, 44, 48, 56, 64, 72, 80]
# need to run 8, 16
# num_apps = [24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80]
# num_apps = [40, 44, 48, 52, 56, 60, 64, 68, 72]
# num_apps = [48]# 24, 28, 32, 36, 40, 48, 52, 56, 60, 64, 68, 72, 76, 80]
# 2, 4, 8, 16, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80
flowsize = [64]
iodepth = [1]
dim = [0, 2]
pin = [1]
permute = [1]
hrtick = [0]
sched = [0]
cores = [1]
runs = [0, 1]
dim_monitor = 0
# Testing DIM disabled parameters
# timeout = [90]
# pkt_threshold = [28]
breakdown = False

# sys = "linux"

# Define the configuration data
config_data = """[settings]
hd= {}
our_patch= {}
c_state = {}
num_apps = {}
flowsize = {}
iodepth = {}
dim = {}
pin = {}
permute = {}
hrtick = {}
sched = {}
cores = {}
timeout = {}
"""
# def wrtie_to_config(DIR, hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, timeout, pkt_t, run):
def wrtie_to_config(DIR, hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run):

    # The path to the file where the config will be written
    config_file_path = '{}/config.txt'.format(DIR)

    # Write the config data to the file
    with open(config_file_path, 'w') as file:
        file.write(config_data.format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run))

def main():
    # Generate all combinations
    # combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs, timeout, pkt_threshold)
    combinations = product(num_apps, flowsize, iodepth, dim, pin, permute, hrtick, sched, cores, runs)
    # for n, f, i, d, p, perm, h, s, core, run, t, pkt_t in combinations:
    for n, f, i, d, p, perm, h, s, core, run in combinations:
        # Execute the main script
        # DIR = "results/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, t, pkt_t, run)
        DIR = "/data0/projects/latency/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run)
        # DIR = "results/oldresults/{}_{}_{}/{}_{}_{}_{}_{}_{}_{}_{}_{}_{}".format(hd, our_patch, c_state, n, f, i, d, p, perm, h, s, core, run)
        os.makedirs(DIR, exist_ok=True)
        wrtie_to_config(DIR, hd, our_patch, c_state, n * core, f, i, d, p, perm, h, s, core, run)
        # command = f"./linux-both-8c-compute.sh {n * core} {DIR} {f} {i} {d} {p} {perm} {h} {s} {core} {run} {t} {pkt_t}"
        command = f"./linux-both-8c-compute.sh {n * core} {DIR} {f} {i} {d} {p} {perm} {h} {s} {core} {run} {dim_monitor}"
        print(command)
        subprocess.run(command, shell=True)
        # get latency breakdown 
        # command = f"./parse-breakdown-server.py {DIR} {n} > {DIR}/linux_latency_breakdown_s"
        # subprocess.run(command, shell=True)
        # command = f"./parse-breakdown.py {DIR} {n} > {DIR}/linux_latency_breakdown_c"
        # subprocess.run(command, shell=True)
        # Create directories and copy files

main()
