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
    # "ytick.minor.width": 1,
    # "ytick.minor.size": 3,
    "ytick.direction": "in",
    
    # grid
    "grid.linestyle": ":",
    "grid.linewidth": 2,
    "grid.color": "black",
    "grid.alpha": 1,

    # axes
    "axes.labelsize": 14,
    "axes.linewidth": 2,
    "axes.axisbelow": True,
    "axes.labelweight": 600,

    # legend
    "legend.fontsize": 12,

})

# ---------- style (latency-throughput curve) ----------

colors = ["#70211c", "#5860c7", "#639d4e", "#8c17f6", "#b77294"]
# colors = ["#8e2c14", "#e25953", "#7b3bf1", "#739739"]
markers = [
    MarkerStyle("x", capstyle="round", joinstyle="round", fillstyle="none"), 
    MarkerStyle("h", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("+", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("o", capstyle="round", joinstyle="round", fillstyle="none")
]
markers_size = [6, 6, 6, 6]
markers_width = [2, 2, 2, 2]
marker_facecolor = ["none", "none", "none", "none"]
zorder = [4, 3, 5, 6]
result_dir = "/data0/projects/latency/"

experiments = ["combined_eevdf"]
labels = ["EEVDF", "EEVDF + ACCa"]

series = [
    "latency_throughput_iodepth_20threads_nirq",
    "latency_throughput_iodepth_20threads_sirq",
]

saved_figure_name = "latency_throughput_curve_eevdf_iodepth_260128"

log = False
max_latency = 10000
max_throughput = 2
divider = 1

ax_height = 2.2
ax_width = 3.85
fig_width = 20
fig_height = 20


fig = plt.figure(figsize=(fig_width, fig_height))
ax_width_frac = ax_width / fig_width
ax_height_frac = ax_height / fig_height

ax = fig.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])

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


for serie_index, serie_name in enumerate(series):
    for experiment_index, experiment_name in enumerate(experiments):
        latency_throughput_data = os.path.join(result_dir, experiment_name, f"{serie_name}.data")
        assert os.path.exists(latency_throughput_data), f"Data file {latency_throughput_data} does not exist."
        data = np.loadtxt(latency_throughput_data, delimiter=',')
        num_threads, avg_lat999, avg_throughput = data[:, 0], data[:, 1], data[:, 2]
        # Draw the latency-throughput curve for each series
        ax.plot(avg_throughput, avg_lat999, color=colors[serie_index], label=labels[serie_index], zorder=zorder[serie_index], 
                marker=markers[serie_index], markersize=markers_size[serie_index], markerfacecolor=marker_facecolor[serie_index], markeredgewidth=markers_width[serie_index])
        # Optional: annotate each point with the number of threads
        # for i, txt in enumerate(num_threads):
        #     ax.annotate(int(txt), (avg_throughput[i], avg_lat999[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=6, color=colors[experiment_index], 
        #                  path_effects=[path_effects.Stroke(linewidth=1, foreground='black'), path_effects.Normal()]
        #                  )

    # if serie_index == 1:
    #     # 24.00000,417.00000,1.003590000
    #     ax.plot(1, 417, color='red', zorder=10, marker='o', markersize=14, markerfacecolor='none', markeredgewidth=2)

# set_major_locator and set_minor_locator for both axes
# if not log:
#     ax.xaxis.set_major_locator(MultipleLocator(0.2))
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

ax.set_xlabel('Throughput (million IOPS)')
ax.set_ylabel('P99.9 Latency (us)')

ax.set_xlim(0, max_throughput)
ax.set_xticks(np.arange(0, max_throughput+0.01, 0.2))
xticks = ax.xaxis.get_major_ticks()
xticks[0].tick1line.set_markersize(0)
xticks[0].tick2line.set_markersize(0)
xticks[-1].tick1line.set_markersize(0)
xticks[-1].tick2line.set_markersize(0)

ax.set_ylim(10, max_latency)
# ax.set_yticks([0, 500, 1000, 1500])
ax.set_yscale('log')

yticks = ax.yaxis.get_major_ticks()
yticks[0].tick1line.set_markersize(0)
yticks[0].tick2line.set_markersize(0)
# yticks[-1].tick1line.set_markersize(0)
# yticks[-1].tick2line.set_markersize(0)

ax.tick_params(which="both", top=True, right=True)

legend = ax.legend(loc='upper left', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
# legend.get_frame().set_edgecolor('none')
fig.savefig(os.path.join(result_dir, f'{saved_figure_name}.pdf'), bbox_inches='tight')
