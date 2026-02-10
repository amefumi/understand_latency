#!/usr/bin/env python3
import os
import numpy as np
from itertools import product
from statistics import stdev
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import matplotlib.patheffects as path_effects
from matplotlib.ticker import MultipleLocator, LogLocator, LogFormatter

total_bin = 100000

def read_histogram(file_path):
    assert os.path.exists(file_path), f"File {file_path} does not exist"
    with open(file_path, 'rb') as f:
        data = np.fromfile(f, dtype=np.uint64, count=total_bin)
        data = data + 1
    return data

if __name__ == "__main__":
    bin_path = "/data0/projects/latency/airq_pktirq_perf_1_1/52_64_1_1_1_1_0_0_1_0/overall_hist.bin"
    histogram = read_histogram(bin_path)
    short_histrogram = histogram[:10000]
    plt.figure(figsize=(20, 6*0.618))
    plt.plot(short_histrogram)
    plt.tight_layout()
    plt.xlabel("Latency (us)")
    plt.yscale("log")
    plt.ylabel("Number of packets")
    plt.tight_layout()
    plt.savefig("latency_histogram_example.pdf", format="pdf")
    print(len(histogram[histogram > 1]))  # Print number of non-zero bins