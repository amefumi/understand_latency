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

from matplotlib.patches import FancyBboxPatch

def rounded_bar(ax, x, height, width=0.8,
                bottom=0,
                radius=0.08,
                **kwargs):
    """
    Draw a rounded bar using FancyBboxPatch
    """
    patch = FancyBboxPatch(
        (x - width / 2, bottom),
        width,
        height,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=kwargs.pop("linewidth", 1.5),
        edgecolor=kwargs.pop("edgecolor", "black"),
        facecolor=kwargs.pop("facecolor", "none"),
        zorder=kwargs.pop("zorder", 3),
        clip_on=False,
    )
    ax.add_patch(patch)
    return patch


def rounded_bar_xy(ax, x, y, width, height, radius=0.05, **kwargs):
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        facecolor=kwargs.get("facecolor", "none"),
        edgecolor=kwargs.get("edgecolor", "black"),
        linewidth=kwargs.get("linewidth", 1.5),
        zorder=kwargs.get("zorder", 3),
        clip_on=False,
    )
    ax.add_patch(patch)
    return patch


# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.family": "serif",
    "font.serif": ["Gill Sans"],
    "font.weight": 500,
    "font.size": 12,

    # lines and markers
    "lines.linewidth": 2,
    "lines.solid_capstyle": "round",
    "lines.solid_joinstyle": "round",
    
    # thick frame and ticks

    "xtick.labelsize": 12,
    "xtick.major.width": 2,
    "xtick.major.size": 6,
    "xtick.major.pad": 10,
    "xtick.minor.width": 2,
    "xtick.minor.size": 3,
    "xtick.direction": "in",

    "ytick.labelsize": 12,
    "ytick.major.width": 2,
    "ytick.major.size": 6,
    "ytick.major.pad": 6,
    # "ytick.minor.width": 2,
    # "ytick.minor.size": 3,
    "ytick.direction": "in",
    
    # grid
    "grid.linestyle": ":",
    "grid.linewidth": 2,
    "grid.color": "black",
    "grid.alpha": 1,

    # axes
    "axes.labelsize": 12,
    "axes.linewidth": 2,
    "axes.axisbelow": True,
    "axes.labelweight": 600,

    # legend
    "legend.fontsize": 11,

    "hatch.linewidth": 0.5,

})

# ---------- style (latency-throughput curve) ----------

colors = ["#5360c9", "#ef8733", "#85201a", "#8c17f6", "#b77294"]
# colors = ["#8e2c14", "#e25953", "#7b3bf1", "#739739"]
markers = [
    MarkerStyle("x", capstyle="round", joinstyle="round", fillstyle="none"), 
    MarkerStyle("h", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("+", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("o", capstyle="round", joinstyle="round", fillstyle="none")
]

hatches = ["", r"\\\\\\", "xxxxxxxx"]

markers_size = [6, 6, 6, 6, 6]
markers_width = [2, 2, 2, 2, 2]
marker_facecolor = ["#5360c9", "white", "white", "none", "none"]
zorder = [4, 5, 6, 7, 8]
result_dir = "/data0/projects/latency/"
saved_figure_name = "skb_size_cdf_iops_bar"

experiments = "combined_pcbs"
saved_result_files = ["pkt_dist_client_2_32_1", "pkt_dist_client_8_32_1", "pkt_dist_client_32_24_1"]

labels = ["2 threads", "8 threads", "32 threads"]


# Initialize figure and axis
# y:x = 7:4
ax_height = 1.2
ax_width = 5
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

for experiment_index, saved_file_name in enumerate(saved_result_files):
    # Read the data file
    latency_throughput_data = os.path.join(result_dir, experiments, f"{saved_file_name}.data")
    assert os.path.exists(latency_throughput_data), f"Data file {latency_throughput_data} does not exist."
    data = np.loadtxt(latency_throughput_data, delimiter=' ')
    packet_size, cdf = data[:, 0], data[:, 1]

    draw_size, draw_rate = [], []

    last_cdf = 0
    for i in range(33):
        if packet_size[i] > 0:
            draw_size.append(packet_size[i])
            draw_rate.append(cdf[i]-last_cdf)
        last_cdf = cdf[i]

    avg = sum(draw_rate[i] * draw_size[i] for i in range(len(draw_size)))
    print(avg)

    # adjust draw_size, so three experiment_index align with three bar series
    draw_size = np.array(draw_size) - 0.25 + experiment_index * 0.25
    for x, h in zip(draw_size, draw_rate):
        rounded_bar(
            ax,
            x=x,
            height=h+0.001,
            width=0.27,
            radius=0.01,   # ← 控制圆角大小（关键参数）
            facecolor=colors[experiment_index],
            edgecolor=colors[experiment_index],
            linewidth=1.3,
            zorder=experiment_index*2+3
        )
    ax.bar(draw_size, draw_rate, width=0.2, color=colors[experiment_index], label=labels[experiment_index], zorder=experiment_index*2+4, hatch=hatches[experiment_index], edgecolor=colors[experiment_index], linewidth=0.5,
           facecolor=marker_facecolor[experiment_index])

    rounded_bar_xy(
        ax,
        x=33 - 0.25 + experiment_index * 0.25,
        y=0.6,
        height=0.003,
        width=0.27,
        radius=0.01,   # ← 控制圆角大小（关键参数）
        facecolor=colors[experiment_index],
        edgecolor=colors[experiment_index],
        linewidth=1.3,
        zorder=experiment_index*2+3
    )


# ax.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=2)
ax.grid(
    True,
    which="major",
    linestyle=(0, (0, 2)),
    linewidth=2,
    color="black",
    dash_capstyle="round",
    alpha=1.0,
    zorder=1,
)

ax.set_xlabel('Number of requests per segment')
ax.set_ylabel('Fraction of Samples')

ax.set_xlim(0.5, 32.5)
ax.set_xticks([1, 8, 16, 24, 32], ["1", "8", "16", "24", "32"])
xticks = ax.xaxis.get_major_ticks()
# xticks[0].tick1line.set_markersize(0)
# xticks[0].tick2line.set_markersize(0)
xticks[-1].tick1line.set_markersize(0)
xticks[-1].tick2line.set_markersize(0)

ax.set_ylim(0, 0.8)
ax.set_yticks(np.arange(0, 0.8+0.2, 0.2))
yticks = ax.yaxis.get_major_ticks()
# yticks[0].tick1line.set_markersize(0)
# yticks[0].tick2line.set_markersize(0)
yticks[-1].tick1line.set_markersize(0)
yticks[-1].tick2line.set_markersize(0)

ax.tick_params(which="both", top=True, right=True)

# legend = ax.legend(loc='upper right', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
# legend.get_frame().set_edgecolor('none')
fig.savefig(os.path.join(result_dir, f'{saved_figure_name}.pdf'), bbox_inches='tight')