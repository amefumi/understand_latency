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
    "legend.fontsize": 14,

})

pad_left   = 1
pad_right  = 0.6
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
    experiments = ["nirq_breakdown_1_1", "dirq_breakdown_1_1", "sirq_breakdown_1_1", "sirq_pcbs_breakdown_1_1"]

    series = ["Linux", "Linux + IRQa", "Linux + ACCa", "Linux + PCSched"]

    colors = ["#7f170e", "#5ca16d", "#3f6eb5", "#854187"]

    hatches = ["//////", "xxxxxx", "++++", r"\\\\\\"]

    threads = [44, 48, 52, 64]

    ax_height = 2.2
    ax_width = 3.85
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

    values = np.full((len(experiments), len(threads)), np.nan, dtype=float)

    for exp_i, exp_name in enumerate(experiments):
        interrupt_path = os.path.join(result_dir, exp_name, "interrupts_dimon.data")
        interrupts = parse_interrupts_files(interrupt_path)

        mp = {n: tot for (n, tot) in interrupts}
        for thr_i, thr in enumerate(threads):
            values[exp_i, thr_i] = mp.get(thr, np.nan)

    n_exp = len(experiments)
    n_thr = len(threads)

    group_gap = 0.65       # experiment 之间的间距（越大越松）
    bar_w = 0.18           # 每根柱子的宽度
    inner_gap = 0.1       # 同一 experiment 内，thread 柱子之间的间距

    group_w = n_thr * bar_w + (n_thr - 1) * inner_gap
    group_centers = np.arange(n_exp) * (group_w + group_gap)

    # 每个 thread 的 offset（相对 group 左边界）
    offsets = np.arange(n_thr) * (bar_w + inner_gap) - (group_w - bar_w) / 2.0


    # -----------------------------
    # 4) 画图（透明 + 栅格）
    # -----------------------------
    for thr_i, thr in enumerate(threads):
        xs = group_centers + offsets[thr_i]
        ys = values[:, thr_i]

        ax.bar(
            xs, ys,
            width=bar_w,
            facecolor="white",
            edgecolor=colors[thr_i],
            linewidth=2.0,
            hatch=hatches[thr_i],
            label=f"{thr} threads",
            zorder=5,
        )

    # -----------------------------
    # 5) x 轴：experiment label 在组中心
    # -----------------------------
    ax.set_xticks(group_centers)
    ax.set_xticklabels(series)  # 或 experiments
    ax.tick_params(axis="x", rotation=15)

    ax.set_xlim(-1.3, group_centers[-1] + 1.3)

    ax.set_ylim(0, 8e7)
    ax.set_yticks(np.arange(0, 8.5e7, 2e7), ["0", r"2x10$^7$", "4x10$^7$", "6x10$^7$", "8x10$^7$" ])
    ax.set_ylabel("#Interrupts", labelpad=8)
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

    # 让 hatch 线更明显（可选：需要 mpl 支持）
    try:
        mpl.rcParams["hatch.linewidth"] = 1
    except Exception:
        pass

    xticks = ax.xaxis.get_major_ticks()
    xticks[0].tick1line.set_markersize(0)
    xticks[0].tick2line.set_markersize(0)
    xticks[-1].tick1line.set_markersize(0)
    xticks[-1].tick2line.set_markersize(0)
    yticks = ax.yaxis.get_major_ticks()
    yticks[0].tick1line.set_markersize(0)
    yticks[0].tick2line.set_markersize(0)
    yticks[-1].tick1line.set_markersize(0)
    yticks[-1].tick2line.set_markersize(0)
    ax.tick_params(which="both", top=True, right=True)

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
    ax.legend(loc='upper left', markerfirst=False, labelspacing=0.3, facecolor='white', edgecolor='white', framealpha=1, ncol=2)

    plt.savefig(os.path.join(result_dir, "interrupts_by_threads_260120.pdf"), bbox_inches=bbox)