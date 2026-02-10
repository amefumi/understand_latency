#!/usr/bin/env python3
import os
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib import transforms
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

pad_left   = 0.8
pad_right  = 0.6
pad_bottom = 0.7
pad_top    = 0.15


if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"

    series = ["CFS + ACCa", "EEVDF + ACCa"]

    settings = ["Normal (32 in-flights)", "High-load (256 in-flights)"]

    colors = ["#364e4f", "#9C3F19", "#3f6eb5", "#854187"]

    hatches = ["xxxxx", "//////", r"\\\\\\"]

    facecolors = ["white", '#E6A57E', "white", "white"]


    # [48: ACCa, PCSched, AutoDIM], [64: ACCa, PCSched, AutoDIM]
    normal_exec_time = [9229591280/1e9, 9222689572/1e9]
    high_load_exec_time = [9229989637/1e9, 12467387521/1e9]
    
    time_norm = True

    if time_norm:
        high_load_exec_time = [x / y for x, y in zip(high_load_exec_time, normal_exec_time)]
        normal_exec_time = [1 for x in normal_exec_time]

    normal_p999 = [1566, 2387]
    high_load_p999 = [17357, 9822]

    normal_throughput = [34649/1e3, 34611.26/1e3]
    high_load_throughput = [38899/1e3, 48943.85/1e3]

    exec_time_values = [normal_exec_time, high_load_exec_time]
    p999_values = [normal_p999, high_load_p999]
    throughput_values = [normal_throughput, high_load_throughput]

    ax_height = 2.2
    ax_width = 3.85/1.1
    fig_width = 20
    fig_height = 20

    fig_exec_time = plt.figure(figsize=(fig_width, fig_height)) # Create a very big figure
    fig_p999 = plt.figure(figsize=(fig_width, fig_height)) # Create a very big figure
    fig_throughput = plt.figure(figsize=(fig_width, fig_height)) # Create a very big figure

    ax_width_frac = ax_width / fig_width
    ax_height_frac = ax_height / fig_height

    ax_exec_time = fig_exec_time.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])
    ax_p999 = fig_p999.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])
    ax_throughput = fig_throughput.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac])

    for spine in ax_exec_time.spines.values():
        spine.set_visible(False)

    for spine in ax_p999.spines.values():
        spine.set_visible(False)

    for spine in ax_throughput.spines.values():
        spine.set_visible(False)

    bbox = FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.0,rounding_size=0.001",
        transform=ax_exec_time.transAxes,
        linewidth=2,
        edgecolor="black",
        facecolor="none",
        zorder=1,
        clip_on=False,
    )
    ax_exec_time.add_patch(bbox)

    bbox = FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.0,rounding_size=0.001",
        transform=ax_p999.transAxes,
        linewidth=2,
        edgecolor="black",
        facecolor="none",
        zorder=1,
        clip_on=False,
    )
    ax_p999.add_patch(bbox)

    bbox = FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.0,rounding_size=0.001",
        transform=ax_throughput.transAxes,
        linewidth=2,
        edgecolor="black",
        facecolor="none",
        zorder=1,
        clip_on=False,
    )
    ax_throughput.add_patch(bbox)

    n_exp = 2
    n_settings = 2

    group_gap = 0.65       # experiment 之间的间距（越大越松）
    bar_w = 0.17           # 每根柱子的宽度
    inner_gap = 0.15       # 同一 experiment 内，thread 柱子之间的间距

    group_w = n_settings * bar_w + (n_settings - 1) * inner_gap
    group_centers = np.arange(n_exp) * (group_w + group_gap)

    # 每个 thread 的 offset（相对 group 左边界）
    offsets = np.arange(n_settings) * (bar_w + inner_gap) - (group_w - bar_w) / 2.0

    # -----------------------------
    # 4) 画图（透明 + 栅格）
    # -----------------------------
    for setting_i, setting in enumerate(settings):
        xs = group_centers + offsets[setting_i]
        ys = exec_time_values[setting_i]
        ys_p999 = p999_values[setting_i]

        ax_exec_time.bar(
            xs, ys,
            width=bar_w,
            edgecolor=colors[setting_i],
            facecolor=facecolors[setting_i],
            linewidth=2.0,
            hatch=hatches[setting_i],
            label=f"{setting}",
            zorder=5,
        )
        ax_p999.bar(
            xs, ys_p999,
            width=bar_w,
            edgecolor=colors[setting_i],
            facecolor=facecolors[setting_i],
            linewidth=2.0,
            hatch=hatches[setting_i],
            label=f"{setting}",
            zorder=5,
        )
        ax_throughput.bar(
            xs, throughput_values[setting_i],
            width=bar_w,
            edgecolor=colors[setting_i],
            facecolor=facecolors[setting_i],
            linewidth=2.0,
            hatch=hatches[setting_i],
            label=f"{setting}",
            zorder=5,
        )

    ax_exec_time.set_xticks(group_centers)
    ax_exec_time.set_xlim(-0.8, 2)
    ax_exec_time.set_xticklabels(series)
    ax_exec_time.tick_params(axis="x", rotation=15, which='major')
    ax_p999.set_xticks(group_centers)
    ax_p999.set_xlim(-0.8, 2)
    ax_p999.set_xticklabels(series)
    ax_p999.tick_params(axis="x", rotation=15, which='major')
    ax_throughput.set_xticks(group_centers)
    ax_throughput.set_xlim(-0.8, 2)
    ax_throughput.set_xticklabels(series)
    ax_throughput.tick_params(axis="x", rotation=15, which='major')

    if time_norm:
        ax_exec_time.set_ylabel("Normalized exec. time", labelpad=8)
        ax_exec_time.set_ylim(0, 2)
    else:
        ax_exec_time.set_ylim(0, 20)
        ax_exec_time.set_yticks(np.arange(0, 21, 5), ["0", "5", "10", "15", "20"])
        ax_exec_time.set_ylabel("Execution Time (s)", labelpad=8)

    ax_p999.set_ylabel("P99.9 Latency (us)", labelpad=8)
    ax_p999.set_ylim(100, 100000)
    ax_p999.set_yscale('log')
    # ax_p999.set_yticks(np.arange(0, 20001, 5000), ["0", "5000", "10000", "15000", "20000"])

    ax_throughput.set_ylabel("Throughput (kIOPS)", labelpad=8)
    ax_throughput.set_ylim(0, 60)
    ax_throughput.set_yticks(np.arange(0, 61, 15), ["0", "15", "30", "45", "60"])

    ax_exec_time.grid(
        True,
        which="major",
        linestyle=(0, (0, 2)),
        linewidth=2,
        color="black",
        dash_capstyle="round",
        alpha=1.0,
        zorder=1,
    )

    ax_p999.grid(
        True,
        which="major",
        linestyle=(0, (0, 2)),
        linewidth=2,
        color="black",
        dash_capstyle="round",
        alpha=1.0,
        zorder=1,
    )

    ax_throughput.grid(
        True,
        which="major",
        linestyle=(0, (0, 2)),
        linewidth=2,
        color="black",
        dash_capstyle="round",
        alpha=1.0,
        zorder=1,
    )

    try:
        mpl.rcParams["hatch.linewidth"] = 1
    except Exception:
        pass

    xticks = ax_exec_time.xaxis.get_major_ticks()
    xticks[0].tick1line.set_markersize(0)
    xticks[0].tick2line.set_markersize(0)
    xticks[-1].tick1line.set_markersize(0)
    xticks[-1].tick2line.set_markersize(0)
    yticks = ax_exec_time.yaxis.get_major_ticks()
    yticks[0].tick1line.set_markersize(0)
    yticks[0].tick2line.set_markersize(0)
    yticks[-1].tick1line.set_markersize(0)
    yticks[-1].tick2line.set_markersize(0)
    ax_exec_time.tick_params(which="both", top=True, right=True)

    xticks = ax_p999.xaxis.get_major_ticks()
    xticks[0].tick1line.set_markersize(0)
    xticks[0].tick2line.set_markersize(0)
    xticks[-1].tick1line.set_markersize(0)
    xticks[-1].tick2line.set_markersize(0)
    yticks = ax_p999.yaxis.get_major_ticks()
    yticks[0].tick1line.set_markersize(0)
    yticks[0].tick2line.set_markersize(0)
    yticks[-1].tick1line.set_markersize(0)
    yticks[-1].tick2line.set_markersize(0)
    ax_p999.tick_params(which="both", top=True, right=True)

    xticks = ax_throughput.xaxis.get_major_ticks()
    xticks[0].tick1line.set_markersize(0)
    xticks[0].tick2line.set_markersize(0)
    xticks[-1].tick1line.set_markersize(0)
    xticks[-1].tick2line.set_markersize(0)
    yticks = ax_throughput.yaxis.get_major_ticks()
    yticks[0].tick1line.set_markersize(0)
    yticks[0].tick2line.set_markersize(0)
    yticks[-1].tick1line.set_markersize(0)
    yticks[-1].tick2line.set_markersize(0)
    ax_throughput.tick_params(which="both", top=True, right=True)

    pos = ax_exec_time.get_position()
    fig_w, fig_h = fig_exec_time.get_size_inches()
    x0 = fig_w * pos.x0
    y0 = fig_h * pos.y0
    x1 = fig_w * pos.x1
    y1 = fig_h * pos.y1
    bbox = transforms.Bbox.from_extents(
        x0 - pad_left,
        y0 - pad_bottom,
        x1 + pad_right,
        y1 + pad_top,
    )

    # legend
    ax_exec_time.legend(loc='upper left', markerfirst=False, labelspacing=0.1, facecolor='none', edgecolor='none', framealpha=1, bbox_to_anchor=(0, 1.02),)

    # draw a white box on ax_exec_time, from (-0.7, 1.52) to (1.5, 1.98), with zorder = 3
    ax_exec_time.add_patch(FancyBboxPatch(
        (-0.6, 1.65), 2.2, 0.2,
        boxstyle="round,pad=0.1",
        linewidth=0,
        edgecolor="white",
        facecolor="white",
        zorder=3,
    ))

    fig_exec_time.savefig(os.path.join(result_dir, "execution_time_imbalanced_260120.pdf"), bbox_inches=bbox)
    fig_p999.savefig(os.path.join(result_dir, "p999_latency_imbalanced_260120.pdf"), bbox_inches=bbox)
    fig_throughput.savefig(os.path.join(result_dir, "throughput_imbalanced_260120.pdf"), bbox_inches=bbox)