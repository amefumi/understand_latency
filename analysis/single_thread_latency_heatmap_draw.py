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
    "axes.labelsize": 15,
    "axes.linewidth": 2,
    "axes.axisbelow": True,
    "axes.labelweight": 600,

    # legend
    "legend.fontsize": 12,

})

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
import matplotlib.cm as cm

reds = cm.get_cmap("Reds")
deep = reds(1.0)  # 完全等于 Reds 最深色

def mix_with_white(rgba, a):
    # a=1 保留原色；a 越小越接近白（去粉、去脏）
    r, g, b, _ = rgba
    return (1 - (1-r)*a, 1 - (1-g)*a, 1 - (1-b)*a)

paper_reds = LinearSegmentedColormap.from_list(
    "paper_reds",
    [
        (0.00, (1.00, 1.00, 1.00)),                 # 白
        # (0.03, (0.995, 0.985, 0.985)),              # 极浅暖白（很短：让浅色更快靠白）
        (0.18, mix_with_white(reds(0.35), 0.55)),   # 去粉的浅红（压缩在前段）
        (0.55, reds(0.55)),                         # 中段开始拉长：深色不容易变浅
        (0.82, reds(0.85)),                         # 深红区更“耐用”
        (1.00, deep),                               # 最深端完全一致
    ],
    N=256
)

if __name__ == "__main__":
    # data points mannually extracted from the experiment results
    labels = ['1'] #, 'Poll']
    avg_latency = [12.8552]#, 10.898]
    p99_latency = [19]#, 14]
    
    # Initialize figure and axis
    ax_height = 2.4
    ax_width_latency = 1
    ax_width_breakdown = 2.4

    fig_width = 20
    fig_height = 20

    
    bar_width = 0.5

    fig = plt.figure(figsize=(fig_width, fig_height)) # Create a very big figure

    ax_width_frac_latency = ax_width_latency / fig_width
    ax_width_frac_breakdown = ax_width_breakdown / fig_width
    ax_height_frac = ax_height / fig_height

    ax_latency = fig.add_axes([0.3, 0.3, ax_width_frac_latency, ax_height_frac])
    ax_breakdown = fig.add_axes([0.3 + ax_width_frac_latency + 0.1, 0.3, ax_width_frac_breakdown, ax_height_frac])

    # re-draw axes spines
    for spine in ax_latency.spines.values():
        spine.set_visible(False)

    for spine in ax_breakdown.spines.values():
        spine.set_visible(False)

    bbox = FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.0,rounding_size=0.001",
        transform=ax_latency.transAxes,
        linewidth=2,
        edgecolor="black",
        facecolor="none",
        zorder=1,
        clip_on=False,
    )
    ax_latency.add_patch(bbox)

    bbox = FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.0,rounding_size=0.001",
        transform=ax_breakdown.transAxes,
        linewidth=2,
        edgecolor="black",
        facecolor="none",
        zorder=1,
        clip_on=False,
    )
    ax_breakdown.add_patch(bbox)

    # Draw the single thread latency bar
    ax_latency.set_ylabel('Latency (us)', labelpad=8)
    ax_latency.set_ylim(0, 30)
    ax_latency.set_xlim(-0.5, len(labels)-0.5)
    ax_latency.set_xticks(np.arange(len(labels)))
    ax_latency.set_xticklabels(labels)
    ax_latency.tick_params(which="both", top=True, right=True)

    bars = ax_latency.bar(np.arange(len(labels)), avg_latency, bar_width, color='#ff0000', edgecolor='#ff0000', zorder=3)
    for b in bars:
        b.set_joinstyle("round")
    for i in range(len(labels)):
        ax_latency.vlines(i, 0, p99_latency[i], color='#ff0000', lw=4, zorder=4)
        ax_latency.plot(i, p99_latency[i], 'o', color='#ff0000', markersize=5, zorder=5)
    ax_latency.grid(True, which="both", linestyle=(0, (0.1, 2)), dash_capstyle='round', zorder=0)


    # Draw the latency breakdown heatmap
    heatmap_path = "/data0/projects/latency/nirq_singlethread_1_1/heatmap_nirq_singlethread_1_1_1.npy"
    heatmap_labels = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue','tx_xmit']*2
    heatmap_cap = 10

    heatmap_np = np.load(heatmap_path)


    print("NaN:", np.isnan(heatmap_np).sum())
    print("Inf:", np.isinf(heatmap_np).sum())
    print("min/max:", np.nanmin(heatmap_np), np.nanmax(heatmap_np))

    ax_breakdown.imshow(np.minimum(heatmap_np, heatmap_cap), aspect='auto', cmap=paper_reds, interpolation='nearest', vmin=0, vmax=heatmap_cap)
    ax_breakdown.axhline(y=11.4, color='black', linestyle=(0, (2, 4)), linewidth=1, dash_capstyle='round')
    ax_breakdown.text(x=heatmap_np.shape[1] / 2, y=11, s='Client', ha='center', fontsize=12)
    ax_breakdown.text(x=heatmap_np.shape[1] / 2, y=23, s='Server', ha='center', fontsize=12)

    cax_width = 0.006
    cax_pad   = 0.005

    ax_pos = ax_breakdown.get_position()
    cax = fig.add_axes([
        ax_pos.x1 + cax_pad,  # 紧贴 ax 右侧
        ax_pos.y0,
        cax_width,
        ax_pos.height
    ])

    cb = fig.colorbar(ax_breakdown.images[0], cax=cax, fraction=0.046, pad=0)
    cb.set_label('Latency (us)', rotation=90, labelpad=5)
    cb.ax.yaxis.set_tick_params(labelsize=12)
    cb.outline.set_visible(False)

    bbox = FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.0,rounding_size=0.001",
        transform=cb.ax.transAxes,
        linewidth=2,
        edgecolor="black",
        facecolor="none",
        zorder=5,
        clip_on=False,
    )
    cb.ax.add_patch(bbox)



    ax_breakdown.set_xlabel('Percentile', labelpad=8)
    ax_breakdown.set_xticks(ticks=np.linspace(0, heatmap_np.shape[1]-1, 5))
    ax_breakdown.set_xticklabels([f"{x}" for x in np.linspace(99.8, 100, 5)], rotation=0, fontsize=12)
    ax_breakdown.set_yticks(ticks=np.arange(heatmap_np.shape[0]))
    ax_breakdown.set_yticklabels(labels=heatmap_labels, ha='right', fontsize=8)

    # ax_breakdown.tick_params(axis='x', labelsize=9)
    ax_breakdown.tick_params(axis='y', labelsize=8)
    ax_breakdown.tick_params(axis="both", which="both", width=1, length=3)

    from matplotlib.transforms import Bbox

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    bbox_latency_px = ax_latency.get_tightbbox(renderer)
    bbox_breakdown_px = ax_breakdown.get_tightbbox(renderer)

    # unify vertical extent in *pixels*
    y0 = min(bbox_latency_px.y0, bbox_breakdown_px.y0)
    y1 = max(bbox_latency_px.y1, bbox_breakdown_px.y1)
    common_h = y1 - y0

    bbox_latency_px_new = Bbox.from_bounds(
        bbox_latency_px.x0, y0,
        bbox_latency_px.width+5, common_h+10
    )
    bbox_breakdown_px_new = Bbox.from_bounds(
        bbox_breakdown_px.x0, y0,
        bbox_breakdown_px.width+60, common_h+10
    )

    # --- convert from pixels -> inches for bbox_inches
    to_in = fig.dpi_scale_trans.inverted()
    bbox_latency_in = bbox_latency_px_new.transformed(to_in)
    bbox_breakdown_in = bbox_breakdown_px_new.transformed(to_in)

    fig.savefig("/data0/projects/latency/single_thread_latency_only.pdf", bbox_inches=bbox_latency_in, pad_inches=0)
    fig.savefig("/data0/projects/latency/single_thread_breakdown_only.pdf", bbox_inches=bbox_breakdown_in, pad_inches=0)