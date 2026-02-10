#!/usr/bin/env python3
import os
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patheffects as path_effects
from matplotlib.markers import MarkerStyle
from matplotlib.ticker import MultipleLocator, LogLocator, LogFormatter
from matplotlib.patches import FancyBboxPatch


fm.fontManager.addfont("/home/ame/GillSans/Gill Sans.otf")
fm.fontManager.addfont("/home/ame/GillSans/Gill Sans Medium.otf")
fm.fontManager.addfont("/home/ame/GillSans/Gill Sans Bold.otf")

# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.family": "serif",
    "font.serif": ["Gill Sans"],
    "font.weight": 500,
    "font.size": 12,

    # lines and markers
    "lines.linewidth": 2.5,
    "lines.solid_capstyle": "round",
    "lines.solid_joinstyle": "round",
    "lines.dash_capstyle": "round",
    "lines.dash_joinstyle": "round",
    # thick frame and ticks

    "xtick.labelsize": 15,
    "xtick.major.width": 2,
    "xtick.major.size": 6,
    "xtick.major.pad": 10,
    "xtick.minor.width": 2,
    "xtick.minor.size": 3,
    "xtick.direction": "in",

    "ytick.labelsize": 15,
    "ytick.major.width": 2,
    "ytick.major.size": 6,
    "ytick.major.pad": 6,
    "ytick.minor.width": 1,
    "ytick.minor.size": 3,
    "ytick.direction": "in",
    
    # grid
    "grid.linestyle": ":",
    "grid.linewidth": 2,
    "grid.color": "black",
    "grid.alpha": 1,

    # axes
    "axes.labelsize": 18,
    "axes.linewidth": 2,
    "axes.axisbelow": True,
    "axes.labelweight": 600,

    # legend
    "legend.fontsize": 13,

})


# ---------- style (latency-throughput curve) ----------

cdf_colors = ['#749735',"#7a3cf3", "#9d1f63",]
avg_colors = ['#749735', '#7a3cf3', '#9d1f63']
# colors = ["#8e2c14", "#e25953", "#7b3bf1", "#739739"]

line_styles = ["-", (0, (1, 1.5)), (0, (3, 1.5, 1, 1.5))]
zorder = [7, 5, 8, 6, 7]
result_dir = "/data0/projects/latency/"
saved_figure_name = "skb_size_cdf_inflights"
# saved_figure_name = "skb_size_cdf_iops"

experiments = "combined_pcbs"
saved_result_files = ["pkt_dist_client_2_64_1", "pkt_dist_client_8_16_0", "pkt_dist_client_32_4_1"]
# saved_result_files = ["pkt_dist_server_2_32_1", "pkt_dist_server_8_32_1", "pkt_dist_server_32_24_1"]

labels = ["2 threads", "8 threads", "32 threads"]


# Initialize figure and axis
# y:x = 7:4
ax_height = 2.2
ax_width = 3.85/1.1
fig_width = 20
fig_height = 20

fig = plt.figure(figsize=(fig_width, fig_height)) # Create a very big figure
ax_width_frac = ax_width / fig_width
ax_height_frac = ax_height / fig_height

ax = fig.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac]) # Add axes at specific position

# re-draw axes spines
for spine in ax.spines.values():
    spine.set_visible(False)

bbox = FancyBboxPatch(
    (0, 0), 1, 1,
    boxstyle="round,pad=0.0,rounding_size=0.001",
    transform=ax.transAxes,
    linewidth=2,
    edgecolor="black",
    facecolor="none",
    zorder=1,
    clip_on=False,
)
ax.add_patch(bbox)

avg_sizes = []

for experiment_index, saved_file_name in enumerate(saved_result_files):
    # Read the data file
    latency_throughput_data = os.path.join(result_dir, experiments, f"{saved_file_name}.data")
    assert os.path.exists(latency_throughput_data), f"Data file {latency_throughput_data} does not exist."
    data = np.loadtxt(latency_throughput_data, delimiter=' ')
    packet_size, cdf = data[:, 0], data[:, 1]

    # calculate average skb size: cdf is the cumulative distribution function, ranging from 0 to 1
    average_size = 0.0
    previous_cdf = 0.0
    for i in range(len(packet_size)):
        delta_cdf = cdf[i] - previous_cdf
        average_size += packet_size[i] * delta_cdf
        previous_cdf = cdf[i]
    # if experiment_index == 2:
    #     average_size -= 0.3
    print(f"Average skb size for {labels[experiment_index]}: {average_size:.2f} bytes")
    avg_sizes.append(average_size)
    # Draw the latency-throughput curve for each series
    ax.plot(packet_size, cdf, color=cdf_colors[experiment_index], label=labels[experiment_index], zorder=zorder[experiment_index], linestyle=line_styles[1], linewidth=1.7, solid_capstyle='round', solid_joinstyle='round')

avg_sizes[0] -= 0.11
avg_sizes[2] += 0.11

for experiment_index, average_size in enumerate(avg_sizes):
    ax.plot([average_size, average_size], [0, 1], color=avg_colors[experiment_index], zorder=zorder[experiment_index], label="avg.", linewidth=2.5, solid_capstyle='round', solid_joinstyle='round')
    # ax.vlines(average_size, ymin=0, ymax=1, color=avg_colors[experiment_index], linestyle=line_styles[experiment_index], zorder=zorder[experiment_index]-1, label="avg.", capstyle='round')

# # ax.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=2)
ax.grid(
    True,
    which="major",
    linestyle=(0, (0, 2)),
    linewidth=2,
    color="grey",
    dash_capstyle="round",
    alpha=1.0,
    zorder=1,
)

ax.set_xlabel('Number of requests per segment', labelpad=8)
ax.set_ylabel('CDF', labelpad=8)

# ax.set_xlim(-8/5, 32)
ax.set_xlim(0, 32)
ax.set_xticks(np.arange(0, 32+1, 8), ["0", "8", "16", "24", "32"])
xticks = ax.xaxis.get_major_ticks()
# xticks[0].tick1line.set_markersize(0)
# xticks[0].tick2line.set_markersize(0)
xticks[-1].tick1line.set_markersize(0)
xticks[-1].tick2line.set_markersize(0)

# ax.set_ylim(-0.2/5, 1)
ax.set_ylim(0, 1)
ax.set_yticks(np.arange(0, 1.1, 0.25))
yticks = ax.yaxis.get_major_ticks()
# yticks[0].tick1line.set_markersize(0)
# yticks[0].tick2line.set_markersize(0)
yticks[-1].tick1line.set_markersize(0)
yticks[-1].tick2line.set_markersize(0)

ax.tick_params(which="both", top=True, right=True)

# draw a white box with zorder = 3, at (9, 0.01) to (30, 0.4)
ax.add_patch(FancyBboxPatch(
    (9, 0.18), 21, 0.12,
    boxstyle="round,pad=0.1",
    linewidth=0,
    edgecolor="white",
    facecolor="white",
    zorder=3,
))

legend = ax.legend(loc='lower right', markerfirst=False, handletextpad=0.6, labelspacing=0.17, columnspacing=0.8, facecolor='none', edgecolor='none', framealpha=1, handlelength=2, ncol=2)
legend.set_zorder(10)
# legend.get_frame().set_edgecolor('none')
fig.savefig(os.path.join(result_dir, f'{saved_figure_name}.pdf'), bbox_inches='tight')