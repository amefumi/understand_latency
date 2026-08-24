import os
import re
import matplotlib as mpl
import numpy as np
from matplotlib import transforms
from matplotlib.markers import MarkerStyle
from matplotlib.patches import FancyBboxPatch
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import matplotlib.patheffects as path_effects
from matplotlib.ticker import MultipleLocator, LogLocator, LogFormatter
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

    "xtick.labelsize": 13,
    "xtick.major.width": 2,
    "xtick.major.size": 6,
    "xtick.major.pad": 5,
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
    "legend.fontsize": 14,

})


pad_left   = 0.6
pad_right  = 0.95
pad_bottom = 0.7
pad_top    = 0.15

def parse_interrupts_files(interrupts_path):
    interrupt_data = np.loadtxt(interrupts_path, delimiter=',').reshape(-1, 3)
    interrupts = []
    
    for row in interrupt_data:
        interrupts.append([int(row[0]), int(row[1])+int(row[2])])
    # [ [n_threads, total_interrupts], ...]

    return interrupts


if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"

    # series = ["ACCa", "PCSched", "AutoDIM", "ACCa", "PCSched", "AutoDIM"]
    series = ["ACCa", "PCSched", "PCSched + AutoDIM"]

    settings = ["Single core", "Multiple cores"]

    colors = ["#ed872f", "#5360cb", "#3f6eb5", "#854187"]

    hatches = ["//////", "none", "++++", r"\\\\\\"]

    facecolors = ["white", '#5360cb', "white", "white"]


    # [48: ACCa, PCSched, AutoDIM], [64: ACCa, PCSched, AutoDIM]
    # multi_cores_results = [24922979.81, 25464455.02, 24887018.27, 20282737.46, 20866444.44, 18717356.21]
    # single_core_results = [28476808.2, 27849812.4, 19983026.2, 19732594.8, 19550640.6, 17092188.6]

    multi_cores_results = [20282737.46, 20866444.44, 18717356.21]
    single_core_results = [19732594.8, 19550640.6, 17092188.6]

    values = [single_core_results, multi_cores_results]

    ax_height = 2.2
    ax_width = 2.8
    fig_width = 20
    fig_height = 20

    fig = plt.figure(figsize=(fig_width, fig_height)) # Create a very big figure
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


    n_exp = 3
    n_settings = 2

    group_gap = 0.65       # experiment 之间的间距（越大越松）
    bar_w = 0.25          # 每根柱子的宽度
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
        ys = values[setting_i]

        ax.bar(
            xs, ys,
            width=bar_w,
            edgecolor=colors[setting_i],
            facecolor=facecolors[setting_i],
            linewidth=2.0,
            hatch=hatches[setting_i],
            label=f"{setting}",
            zorder=5,
        )


    # divider = (group_centers[2] + group_centers[3]) / 2.0

    # ax.axvline(x=divider, color='grey', linestyle='--', linewidth=1, alpha=0.8)
    # # ax.axvspan(-100, divider, facecolor='#98beb6', zorder=0, alpha=0.1)
    # # ax.axvspan(divider, 100, facecolor='#d8d7ea', zorder=0, alpha=0.2)

    # # Draw text annotations: left part "DIM disabled", right part "DIM enabled"
    # ax.annotate('48 threads', xy=(group_centers[1]-0.08, 3.3e7), horizontalalignment='center', fontsize=14, color='black', zorder=12, backgroundcolor='white',
    #             path_effects=[
    #                 path_effects.Stroke(linewidth=0.3, foreground='black'),
    #                 path_effects.Normal()
    #             ])
    # ax.annotate('64 threads', xy=(group_centers[4]-0.16, 3.3e7), horizontalalignment='center', fontsize=14, color='black', zorder=12, backgroundcolor='white',
    #             path_effects=[
    #                 path_effects.Stroke(linewidth=0.3, foreground='black'),
    #                 path_effects.Normal()
    #             ])

    ax.set_xticks(group_centers)
    ax.set_xlim(-1, 3.5)
    ax.set_xticklabels(series, ha='center')
    ax.tick_params(axis="x", which='both', rotation=15)
    offset = transforms.ScaledTranslation(-15 / 72, 0, fig.dpi_scale_trans)
    for label in ax.get_xticklabels():
        label.set_transform(label.get_transform() + offset)

    ax.set_ylim(0, 6e7)
    ax.set_yticks(np.arange(0, 6.5e7, 2e7), ["0", r"2x10$^7$", "4x10$^7$", "6x10$^7$" ])
    ax.set_ylabel("#Interrupts")
    ax.yaxis.set_label_position("right")
    ax.yaxis.tick_right()

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

    try:
        mpl.rcParams["hatch.linewidth"] = 1
    except Exception:
        pass

    xticks = ax.xaxis.get_major_ticks()
    # xticks[0].tick1line.set_markersize(0)
    # xticks[0].tick2line.set_markersize(0)
    # xticks[-1].tick1line.set_markersize(0)
    # xticks[-1].tick2line.set_markersize(0)
    yticks = ax.yaxis.get_major_ticks()
    # yticks[0].tick1line.set_markersize(0)
    # yticks[0].tick2line.set_markersize(0)
    # yticks[-1].tick1line.set_markersize(0)
    # yticks[-1].tick2line.set_markersize(0)
    ax.tick_params(which="both", top=True, right=True, left=True)

    pos = ax.get_position()
    fig_w, fig_h = fig.get_size_inches()
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
    ax.legend(loc='upper left', markerfirst=False, labelspacing=0.2, facecolor='white', edgecolor='white', framealpha=1)

    plt.savefig(os.path.join(result_dir, "interrupts_by_threads_cores_260625.pdf"), bbox_inches=bbox)