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


# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Liberation Sans", "Nimbus Sans", "Helvetica", "DejaVu Sans"],
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
    "ytick.minor.width": 1,
    "ytick.minor.size": 3,
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
    "legend.fontsize": 12,

})


# pad_left = 0.9
# pad_right = 0.7
# pad_bottom = 0.7
# pad_top    = 0.15

# ---------- style (latency-throughput curve) ----------

colors = ["#bf1a15", "#497ade", "#639d4e", "#8c17f6", "#b77294"]
# colors = ["#8e2c14", "#e25953", "#7b3bf1", "#739739"]
markers = [
    MarkerStyle("x", capstyle="round", joinstyle="round", fillstyle="none"), 
    # MarkerStyle("s", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("h", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("+", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("o", capstyle="round", joinstyle="round", fillstyle="none")
]
markers_size = [6, 6, 6, 6, 6]
markers_width = [2, 2, 2, 2, 2]
marker_facecolor = ["none", "none", "none", "none", "none"]
zorder = [6, 7, 8, 9, 7]
result_dir = "/data0/projects/latency/"
saved_file_name = "latency_throughput_new_cstate"
# saved_file_name = "latency_throughput_eevdf_cloudlab"

saved_figure_dir = "/home/ame/latency/slide/results"
# saved_figure_name = "latency_throughput_curve_eevdf_250113"
saved_figure_name = "single_core_multiple_thread_acca"

experiments = ["combined_nirq", "combined_sirq"]
# experiments = ["combined_nirq", "combined_sirq", "combined_pcbs"]

labels = ["Linux", "Linux + ACCa"]
# labels = ["EEVDF", "EEVDF + ACCa", "EEVDF + PCSched*"]


log = False
max_latency = 3000
max_throughput = 0.4
divider = 0.256

# Initialize figure and axis
# y:x = 7:4
ax_height = 2
ax_width = 2/0.7
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

# Draw dividers and background colors
ax.axvline(x=divider, color='grey', linestyle='--', linewidth=0.5, alpha=0.5)
ax.axvspan(0, divider, facecolor='oldlace', zorder=0)
# ax.axvspan(divider, max_throughput, facecolor='#d9eaf1', zorder=0)

# Draw text annotations: left part "DIM disabled", right part "DIM enabled"
ax.annotate('DIM off', xy=(0.175, 1300), horizontalalignment='center', fontsize=12, color='black', zorder=4,
            bbox=dict(
                # facecolor='#e8e8e8',
                facecolor='oldlace',
                edgecolor='none',
            ),
            path_effects=[
                path_effects.Stroke(linewidth=0.1, foreground='black'),
                path_effects.Normal()
            ])
# draw a white box at (0.275, 1400) to (0.375, 1600) with zorder=4
ax.add_patch(FancyBboxPatch(
    (0.275, 1200), 0.1, 400,
    boxstyle="round,pad=0.0,rounding_size=0.001",
    linewidth=0,
    edgecolor="none",
    facecolor="white",
    zorder=4,
    clip_on=False,
))

ax.annotate('DIM on', xy=(0.325, 1300), horizontalalignment='center', fontsize=12, color='black', zorder=10,
            path_effects=[
                path_effects.Stroke(linewidth=0.1, foreground='black'),
                path_effects.Normal()
            ])

for experiment_index, experiment_name in enumerate(experiments):
    # Read the data file
    latency_throughput_data = os.path.join(result_dir, experiment_name, f"{saved_file_name}.data")
    assert os.path.exists(latency_throughput_data), f"Data file {latency_throughput_data} does not exist."
    data = np.loadtxt(latency_throughput_data, delimiter=',')
    num_threads, avg_lat999, avg_throughput = data[:, 0], data[:, 1], data[:, 2]
    # Draw the latency-throughput curve for each series
    ax.plot(avg_throughput, avg_lat999, color=colors[experiment_index], label=labels[experiment_index], zorder=zorder[experiment_index], 
             marker=markers[experiment_index], markersize=markers_size[experiment_index], markerfacecolor=marker_facecolor[experiment_index], markeredgewidth=markers_width[experiment_index])
    # Optional: annotate each point with the number of threads
    # for i, txt in enumerate(num_threads):
    #     ax.annotate(int(txt), (avg_throughput[i], avg_lat999[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=6, color=colors[experiment_index], 
    #                  path_effects=[path_effects.Stroke(linewidth=1, foreground='black'), path_effects.Normal()]
    #                  )

target_points = [
    (0.36154, 1160), # Linux + PCSched
    # (0.36055, 1193),
    # (0.354, 415),  # Linux + ACCa
    # (0.357, 276)   # Linux + PCSched + AutoDIM
]


# ax.annotate(
#     '48 threads',
#     xy=(0.25, 750),
#     xytext=(0.2, 750),
#     textcoords='data',
#     ha='center',
#     fontsize=12,
#     zorder=20,
#     clip_on=False,
#     bbox=dict(
#         facecolor='oldlace',
#         edgecolor='none',
#     ),
#     color='grey',
# )
# for i, (x, y) in enumerate(target_points):
#     plt.plot(
#         [0.24, x], [800, y],
#         color='grey',
#         linestyle='--',
#         linewidth=0.7,
#         zorder=15,
#     )


# set_major_locator and set_minor_locator for both axes
# if not log:
#     ax.xaxis.set_major_locator(MultipleLocator(0.1))
#     ax.xaxis.set_minor_locator(MultipleLocator(0.05))
#     ax.yaxis.set_major_locator(MultipleLocator(1000))
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

ax.set_xlim(0.1, max_throughput)
ax.set_xticks(np.arange(0.1, max_throughput+0.05, 0.05), ["0.1", "0.15", "0.2", "0.25", "0.3", "0.35", "0.4"])
# ax.set_xticks(np.arange(0, max_throughput+0.01, 0.05))
xticks = ax.xaxis.get_major_ticks()
xticks[0].tick1line.set_markersize(0)
xticks[0].tick2line.set_markersize(0)
xticks[-1].tick1line.set_markersize(0)
xticks[-1].tick2line.set_markersize(0)

ax.set_ylim(-200 if not log else 10, max_latency)
ax.set_yticks(np.arange(0, max_latency+100, 1000))
yticks = ax.yaxis.get_major_ticks()
# yticks[0].tick1line.set_markersize(0)
# yticks[0].tick2line.set_markersize(0)
yticks[-1].tick1line.set_markersize(0)
yticks[-1].tick2line.set_markersize(0)

ax.tick_params(which="both", top=True, right=True)

if log:
    ax.set_yscale('log')

legend = ax.legend(loc='upper left', markerfirst=False, labelspacing=0.15, facecolor='white', edgecolor='white', framealpha=1)
# legend.get_frame().set_edgecolor('none')

# pos = ax.get_position()
# fig_w, fig_h = fig.get_size_inches()
# x0 = fig_w * pos.x0
# y0 = fig_h * pos.y0
# width = fig_w * pos.width
# height = fig_h * pos.height

# from matplotlib import transforms
# bbox = transforms.Bbox.from_extents(
#     x0 - pad_left,
#     y0 - pad_bottom,
#     x0 + width + pad_right,
#     y0 + height + pad_top
# )

from matplotlib.transforms import Bbox

fig.canvas.draw()
renderer = fig.canvas.get_renderer()


latency_px = ax.get_tightbbox(renderer)
bbox_latency = Bbox.from_bounds(
    latency_px.x0 - 10,
    latency_px.y0 - 10,
    latency_px.width + 30,
    latency_px.height + 20,
)

to_in = fig.dpi_scale_trans.inverted()
bbox_latency = bbox_latency.transformed(to_in)

fig.savefig(os.path.join(saved_figure_dir, f'{saved_figure_name}.pdf'), bbox_inches=bbox_latency)