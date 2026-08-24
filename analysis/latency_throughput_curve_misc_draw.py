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
    "lines.linewidth": 2,
    "lines.solid_capstyle": "round",
    "lines.solid_joinstyle": "round",
    
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
    "axes.labelsize": 17,
    "axes.linewidth": 2,
    "axes.axisbelow": True,
    "axes.labelweight": 600,

    # legend
    "legend.fontsize": 13,

})

pad_left = 0.9
pad_right = 0.2
pad_bottom = 0.7
pad_top    = 0.15

# ---------- style (latency-throughput curve) ----------
# "#bf1a15", "#dd883f", 
colors = ["#497ade", "#70211c", "#995278", "#b77294"]
# colors = ["#8e2c14", "#e25953", "#7b3bf1", "#739739"]
markers = [
    # MarkerStyle("x", capstyle="round", joinstyle="round", fillstyle="none"), 
    # MarkerStyle("s", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("h", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("s", capstyle="round", joinstyle="round", fillstyle="full"),
    MarkerStyle("o", capstyle="round", joinstyle="round", fillstyle="full")
]
markers_size = [6, 6, 6, 6, 6]
markers_width = [2, 2, 2, 2, 2]
marker_facecolor = ["none", colors[1], colors[2], "none", "none"]
zorder = [6, 7, 8, 9, 7]
result_dir = "/data0/projects/latency/"
experiment_dir = "combined_sirq"

experiments = ["new_cstate", "nolb", "nosmt"]
saved_figure_name = "latency_throughput_curve_misc_raw"

labels = ["Default", "Enable Load Balancing", "Disable Hyperthreading"]


log = False
max_latency = 1500
max_throughput = 0.4

# Initialize figure and axis
# y:x = 7:4
ax_height = 2.2
ax_width = 3.85/1.05
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


for experiment_index, experiment_name in enumerate(experiments):
    # Read the data file
    latency_throughput_data = os.path.join(result_dir, experiment_dir, f"latency_throughput_{experiment_name}.data")
    assert os.path.exists(latency_throughput_data), f"Data file {latency_throughput_data} does not exist."
    data = np.loadtxt(latency_throughput_data, delimiter=',')
    num_threads, avg_lat999, avg_throughput = data[:, 0], data[:, 1], data[:, 2]
    # Draw the latency-throughput curve for each series
    ax.plot(avg_throughput, avg_lat999, color=colors[experiment_index], label=labels[experiment_index], zorder=zorder[experiment_index], 
             marker=markers[experiment_index], markersize=markers_size[experiment_index], markerfacecolor=marker_facecolor[experiment_index], markeredgewidth=markers_width[experiment_index])

# Draw DIM enabled point
ax.plot(0.18687, 293, color='orange', zorder=10, marker='s', markersize=14, markerfacecolor='none', markeredgewidth=2)
ax.plot(0.27125, 296, color='orange', zorder=10, marker='s', markersize=14, markerfacecolor='none', markeredgewidth=2)
ax.plot(0.26250, 416, color='orange', zorder=10, marker='s', markersize=14, markerfacecolor='none', markeredgewidth=2)


# set_major_locator and set_minor_locator for both axes
if not log:
    ax.xaxis.set_major_locator(MultipleLocator(0.05))
    # ax.xaxis.set_minor_locator(MultipleLocator(0.05))
    ax.yaxis.set_major_locator(MultipleLocator(500))
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

ax.set_xlabel('Throughput (million IOPS)', labelpad=8)
ax.set_ylabel('P99.9 Latency (us)', labelpad=8)

ax.set_xlim(0, max_throughput)
ax.set_xticks(np.arange(0, max_throughput+0.05, 0.05), ["0", "0.05", "0.1", "0.15", "0.2", "0.25", "0.3", "0.35", "0.4"])
xticks = ax.xaxis.get_major_ticks()
xticks[0].tick1line.set_markersize(0)
xticks[0].tick2line.set_markersize(0)
xticks[-1].tick1line.set_markersize(0)
xticks[-1].tick2line.set_markersize(0)

ax.set_ylim(0 if not log else 10, max_latency)
ax.set_yticks(np.arange(0, max_latency+50, 500))
yticks = ax.yaxis.get_major_ticks()
yticks[0].tick1line.set_markersize(0)
yticks[0].tick2line.set_markersize(0)
yticks[-1].tick1line.set_markersize(0)
yticks[-1].tick2line.set_markersize(0)

ax.tick_params(which="both", top=True, right=True)

if log:
    ax.set_yscale('log')

legend = ax.legend(loc='upper left', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
legend.get_frame().set_edgecolor('none')
legend.set_zorder(2)

pos = ax.get_position()
fig_w, fig_h = fig.get_size_inches()
x0 = fig_w * pos.x0
y0 = fig_h * pos.y0
width = fig_w * pos.width
height = fig_h * pos.height

from matplotlib import transforms
bbox = transforms.Bbox.from_extents(
    x0 - pad_left,
    y0 - pad_bottom,
    x0 + width + pad_right,
    y0 + height + pad_top
)

fig.savefig(os.path.join(result_dir, f'{saved_figure_name}.pdf'), bbox_inches=bbox)