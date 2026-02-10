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
    "legend.fontsize": 12,

})

# ---------- style (latency-throughput curve) ----------

colors = ["#bf1a15", "#497ade", "#639d4e", "#8c17f6", "#b77294"]

colors_tiny = ["#e57373", "#64b5f6", "#81c784", "#ba68c8", "#ffb6c1"]

# colors = ["#8e2c14", "#e25953", "#7b3bf1", "#739739"]
markers = [
    MarkerStyle("x", capstyle="round", joinstyle="round", fillstyle="none"), 
    MarkerStyle("h", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("+", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("o", capstyle="round", joinstyle="round", fillstyle="none")
]
markers_size = [7.5, 7.5, 7.5, 7.5, 7.5]
markers_width = [2.5, 2.5, 2.5, 2.5, 2.5]
marker_facecolor = ["none", "none", "none", "none", "none"]
zorder = [6, 7, 8, 9, 10]
result_dir = "/data0/projects/latency/"

experiments = ["combined_nirq", "combined_sirq", "combined_pcbs"]
labels = ["Linux", "Linux + ACCa", "Linux + PCSched"]

throughput_series = [
    "latency_throughput_iodepth_2threads",
    "latency_throughput_iodepth_8threads",
    "latency_throughput_iodepth_32threads",
    "latency_throughput_iodepth_48threads",
]

rx_sched_latency_series = [
    "rx_sched_combined_iodepth_2threads",
    "rx_sched_combined_iodepth_8threads",
    "rx_sched_combined_iodepth_32threads",
    "rx_sched_combined_iodepth_48threads",
]

saved_figure_name = "rx_sched_combined_iodepth_separate_260224"

log = False
max_latency = 100000
max_throughput = 2
divider = 1

ax_height = 2.2
ax_width = 3.85/1.1
fig_width = 20
fig_height = 20

combined_mode = False

for serie_index, serie_name in enumerate(throughput_series):
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

    # Draw dividers and background colors
    if serie_index == 0:
        # ax.axvline(x=divider, color='grey', linestyle='--', linewidth=0.5, alpha=0.5)
        ax.axvspan(0, divider, facecolor='oldlace', zorder=0)
        # ax.axvspan(divider, max_throughput, facecolor='#d9eaf1', zorder=0, alpha=0.4)
        ax.annotate('DIM off', xy=(0.5, 1000), horizontalalignment='center', fontsize=14, color='black', zorder=10,
                    bbox=dict(
                        # facecolor='#e8e8e8',
                        facecolor='oldlace',
                        edgecolor='none',
                    ),
                    path_effects=[
                        path_effects.Stroke(linewidth=0.3, foreground='black'),
                        path_effects.Normal()
                    ])
        ax.annotate('DIM on', xy=(1.5, 1000), horizontalalignment='center', fontsize=14, color='black', zorder=10,
                    bbox=dict(
                        facecolor='white',
                        # facecolor='#f1f7f9',
                        edgecolor='none',
                    ),
                    path_effects=[
                        path_effects.Stroke(linewidth=0.3, foreground='black'),
                        path_effects.Normal()
                    ])
    else:
        # ax.axvspan(0, max_throughput, facecolor='#d9eaf1', zorder=0, alpha=0.4)
        pass


    for experiment_index, experiment_name in enumerate(experiments):
        # Read the data file
        latency_throughput_data = os.path.join(result_dir, experiment_name, f"{serie_name}.data")
        rx_sched_latency_data = os.path.join(result_dir, experiment_name, f"{rx_sched_latency_series[serie_index]}.data")

        assert os.path.exists(latency_throughput_data), f"Data file {latency_throughput_data} does not exist."
        assert os.path.exists(rx_sched_latency_data), f"Data file {rx_sched_latency_data} does not exist."

        data = np.loadtxt(latency_throughput_data, delimiter=',')
        rx_sched_data = np.loadtxt(rx_sched_latency_data, delimiter=',')

        num_threads, avg_lat999, avg_throughput = data[:, 0], data[:, 1], data[:, 2]
        num_threads, rx_sched_mean, rx_sched_mid, rx_sched_p999, rx_sched_client, rx_sched_server = rx_sched_data[:, 0], rx_sched_data[:, 1]/1e3, rx_sched_data[:, 2]/1e3, rx_sched_data[:, 3]/1e3, rx_sched_data[:, 4]/1e3, rx_sched_data[:, 5]/1e3

        # Draw the latency-throughput curve for each series
        if combined_mode:
            ax.plot(avg_throughput, rx_sched_p999, color=colors[experiment_index], label=labels[experiment_index], zorder=zorder[experiment_index], 
                marker=markers[experiment_index], markersize=markers_size[experiment_index], markerfacecolor=marker_facecolor[experiment_index], markeredgewidth=markers_width[experiment_index])
        else:
            ax.plot(avg_throughput, rx_sched_client, color=colors[experiment_index], label=labels[experiment_index]+":  Client", zorder=zorder[experiment_index], 
                marker=markers[experiment_index], markersize=markers_size[experiment_index], markerfacecolor=marker_facecolor[experiment_index], markeredgewidth=markers_width[experiment_index], solid_capstyle="round", solid_joinstyle="round")
            ax.plot(avg_throughput, rx_sched_server, color=colors_tiny[experiment_index], label="Server", zorder=zorder[experiment_index], 
                marker=markers[experiment_index], markersize=markers_size[experiment_index], markerfacecolor=marker_facecolor[experiment_index], markeredgewidth=markers_width[experiment_index], linestyle='--', solid_capstyle="round", solid_joinstyle="round")

        # Optional: annotate each point with the number of threads
        # for i, txt in enumerate(num_threads):
        #     ax.annotate(int(txt), (avg_throughput[i], avg_lat999[i]), textcoords="offset points", xytext=(4,4), ha='center', fontsize=6, color=colors[experiment_index], 
        #                  path_effects=[path_effects.Stroke(linewidth=1, foreground='black'), path_effects.Normal()]
        #                  )

    # if serie_index == 1:
    #     # 24.00000,417.00000,1.003590000
    #     if combined_mode:
    #         ax.plot(1, 196, color='red', zorder=10, marker='o', markersize=14, markerfacecolor='none', markeredgewidth=2)
    #     else:
    #         ax.plot(1, 150, color='red', zorder=10, marker='o', markersize=14, markerfacecolor='none', markeredgewidth=2)

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

    ax.set_xlabel('Throughput (million IOPS)', labelpad=8)
    ax.set_ylabel('P99.9 rx_sched (us)', labelpad=8)

    ax.set_xlim(0, max_throughput)
    ax.set_xticks(np.arange(0, max_throughput+0.05, 0.25), ["0", "0.25", "0.5", "0.75", "1.0", "1.25", "1.5", "1.75", "2.0"])
    xticks = ax.xaxis.get_major_ticks()
    xticks[0].tick1line.set_markersize(0)
    xticks[0].tick2line.set_markersize(0)
    xticks[-1].tick1line.set_markersize(0)
    xticks[-1].tick2line.set_markersize(0)

    ax.set_ylim(10, max_latency)
    ax.set_yscale('log')
    ax.set_yticks([10, 100, 1000, 10000, 100000])
    yticks = ax.yaxis.get_major_ticks()
    yticks[0].tick1line.set_markersize(0)
    yticks[0].tick2line.set_markersize(0)
    # yticks[-1].tick1line.set_markersize(0)
    # yticks[-1].tick2line.set_markersize(0)

    ax.tick_params(which="both", top=True, right=True)

    if serie_index == 0:
        if combined_mode:
            legend = ax.legend(loc='upper left', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)
        else:
            handles, labels = ax.get_legend_handles_labels()

            new_handles = [handles[0], handles[2], handles[4], handles[1], handles[3], handles[5]]
            new_labels  = [labels[0], labels[2], labels[4], labels[1], labels[3], labels[5]]

            legend = ax.legend(new_handles, new_labels, loc='upper left', markerfirst=False, labelspacing=0.1, facecolor='white', edgecolor='white', framealpha=1, ncol=2, columnspacing=1.2, handletextpad=0.4)
            legend.set_zorder(4)
    # legend.get_frame().set_edgecolor('none')
    fig.savefig(os.path.join(result_dir, f'{saved_figure_name}_{serie_index}.pdf'), bbox_inches='tight')
