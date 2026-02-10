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

fm.fontManager.addfont("/home/ame/GillSans.ttc")

# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.family": "Gill Sans",
    "font.size": 12,

    # sizes
    "axes.titlesize": 12,
    "axes.labelsize": 12,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,

    # lines and markers
    "lines.linewidth": 2.5,
    "lines.markersize": 4,
    
    # thick frame and ticks
    "axes.linewidth": 2,
    "xtick.major.width": 2,
    "xtick.major.size": 6,
    "ytick.major.width": 2,
    "ytick.major.size": 6,
    "xtick.minor.width": 2,
    "xtick.minor.size": 3,
    "ytick.minor.width": 2,
    "ytick.minor.size": 3,
    "xtick.direction": "in",
    "ytick.direction": "in",
    
    # grid
    "grid.linestyle": ":",
    "grid.linewidth": 2,
    "grid.color": "black",
    "grid.alpha": 1,
    "axes.axisbelow": True,

    # legend
    "legend.fontsize": 12,
})


labels = [
    "CFS",
    "CFS + IRQa",
    "CFS + ACCa",
    "Packet-based",
    "Round-robin",
]

p_999_latency = [
    1139,
    1193,
    470,
    271,
    265,
]

throughput = [
    0.360022,
    0.345151,
    0.381745,
    0.350184
]

# Figure 1: latency across different configurations in bar plot
plt.figure(figsize=(4.5,4.5*0.618))
bars = plt.bar(np.arange(len(labels)), p_999_latency, color=["#d62728", "#ff7f0e", "#1f77b4", "#2ca02c", "#9467bd"])
plt.xticks(np.arange(len(labels)), labels, rotation=30, ha="right")
plt.ylabel("P99.9 Latency (us)")
plt.ylim(0, 1500)
plt.grid(axis="both")
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2.0, yval + 60, f'{yval}', ha='center', va='bottom', fontsize=12, backgroundcolor='white')
plt.tight_layout()
plt.savefig("knee_point_latency_comparision.pdf")
plt.close()

# # Figure 2: throughput across different configurations in bar plot
# plt.figure(figsize=(6,6*0.618))
# bars = plt.bar(np.arange(len(labels)), throughput, color=["#d62728", "#ff7f0e", "#1f77b4", "#2ca02c"])
# plt.xticks(np.arange(len(labels)), labels, rotation=15, ha="center")
# plt.ylabel("Throughput (Gbps)")
# plt.ylim(0, 0.5)
# plt.grid(axis="both")
# for bar in bars:
#     yval = bar.get_height()
#     plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.015, f'{yval:.3f}', ha='center', va='bottom', fontsize=12, backgroundcolor='white')
# plt.tight_layout()
# plt.savefig("throughput_comparison_bar_plot.pdf")
# plt.close()