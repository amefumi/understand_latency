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
from matplotlib.transforms import Bbox

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

OUT_DIR = "/home/ame/latency/slide/results"


def save_cropped(fig, ax, path, extra_width=0, extra_height=10):
    """Crop `ax` out of its oversized canvas and write it to `path`.

    `extra_width` / `extra_height` are pixels added to the tight bbox, to make room for
    artists that tightbbox does not see (e.g. a colorbar on a separate axes).
    """
    fig.canvas.draw()
    bbox_px = ax.get_tightbbox(fig.canvas.get_renderer())
    crop_px = Bbox.from_bounds(
        bbox_px.x0, bbox_px.y0,
        bbox_px.width + extra_width, bbox_px.height + extra_height,
    )
    # --- convert from pixels -> inches for bbox_inches
    crop_in = crop_px.transformed(fig.dpi_scale_trans.inverted())
    fig.savefig(path, bbox_inches=crop_in, pad_inches=0)


def boxed_frame(ax, linewidth=1.5, zorder=1):
    """Replace the spines with a single rounded frame patch."""
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.add_patch(FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.0,rounding_size=0.001",
        transform=ax.transAxes,
        linewidth=linewidth,
        edgecolor="black",
        facecolor="none",
        zorder=zorder,
        clip_on=False,
    ))


def draw_latency(labels, avg_latency, p99_latency, out_path, bar_width=0.5):
    """Bar of average latency with a whisker up to p99, one bar per label."""
    # ---------- geometry ----------
    fig_width, fig_height = 20, 20   # a very big canvas; cropped down to the axes on save
    ax_x0, ax_y0 = 0.3, 0.3
    ax_width, ax_height = 1, 2.4     # inches

    fig = plt.figure(figsize=(fig_width, fig_height))
    ax = fig.add_axes([ax_x0, ax_y0, ax_width / fig_width, ax_height / fig_height])
    boxed_frame(ax)

    ax.set_ylabel('Latency (us)', labelpad=8)
    ax.set_ylim(0, 30)
    ax.set_xlim(-0.5, len(labels)-0.5)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels)
    ax.tick_params(which="both", top=True, right=True)

    bars = ax.bar(np.arange(len(labels)), avg_latency, bar_width, color='#ff0000', edgecolor='#ff0000', zorder=3)
    for b in bars:
        b.set_joinstyle("round")
    for i in range(len(labels)):
        ax.vlines(i, 0, p99_latency[i], color='#ff0000', lw=4, zorder=4)
        ax.plot(i, p99_latency[i], 'o', color='#ff0000', markersize=5, zorder=5)
    ax.grid(True, which="both", linestyle=(0, (0.1, 2)), dash_capstyle='round', zorder=0)

    save_cropped(fig, ax, out_path, extra_width=5)
    return fig, ax


def draw_breakdown(heatmap_path, heatmap_labels, out_path, heatmap_cap=10):
    """Per-stage latency breakdown heatmap over the tail percentiles, with colorbar."""
    # ---------- geometry ----------
    fig_width, fig_height = 20, 20   # a very big canvas; cropped down to the axes on save
    ax_x0, ax_y0 = 0.3, 0.3
    ax_width, ax_height = 2.4, 2.4   # inches

    fig = plt.figure(figsize=(fig_width, fig_height))
    ax = fig.add_axes([ax_x0, ax_y0, ax_width / fig_width, ax_height / fig_height])
    boxed_frame(ax)

    heatmap_np = np.load(heatmap_path)

    print("NaN:", np.isnan(heatmap_np).sum())
    print("Inf:", np.isinf(heatmap_np).sum())
    print("min/max:", np.nanmin(heatmap_np), np.nanmax(heatmap_np))

    ax.imshow(np.minimum(heatmap_np, heatmap_cap), aspect='auto', cmap=paper_reds, interpolation='nearest', vmin=0, vmax=heatmap_cap)
    ax.axhline(y=11.4, color='black', linestyle=(0, (2, 4)), linewidth=1, dash_capstyle='round')
    ax.text(x=heatmap_np.shape[1] / 2, y=11, s='Client', ha='center', fontsize=12)
    ax.text(x=heatmap_np.shape[1] / 2, y=23, s='Server', ha='center', fontsize=12)

    cax_width = 0.006
    cax_pad   = 0.005

    ax_pos = ax.get_position()
    cax = fig.add_axes([
        ax_pos.x1 + cax_pad,  # 紧贴 ax 右侧
        ax_pos.y0,
        cax_width,
        ax_pos.height
    ])

    cb = fig.colorbar(ax.images[0], cax=cax, fraction=0.046, pad=0)
    cb.set_label('Latency (us)', rotation=90, labelpad=5)
    cb.ax.yaxis.set_tick_params(labelsize=12)
    cb.outline.set_visible(False)
    boxed_frame(cb.ax, zorder=5)

    ax.set_xlabel('Percentile', labelpad=8)
    ax.set_xticks(ticks=np.linspace(0, heatmap_np.shape[1]-1, 5))
    ax.set_xticklabels([f"{x}" for x in np.linspace(99.8, 100, 5)], rotation=0, fontsize=12)
    ax.set_yticks(ticks=np.arange(heatmap_np.shape[0]))
    ax.set_yticklabels(labels=heatmap_labels, ha='right', fontsize=8)

    # ax.tick_params(axis='x', labelsize=9)
    ax.tick_params(axis='y', labelsize=8)
    ax.tick_params(axis="both", which="both", width=1, length=3)

    save_cropped(fig, ax, out_path, extra_width=60)
    return fig, ax


if __name__ == "__main__":
    # data points mannually extracted from the experiment results
    labels = ['1'] #, 'Poll']
    avg_latency = [12.8552]#, 10.898]
    p99_latency = [19]#, 14]

    heatmap_path = "/data0/projects/latency/nirq_singlethread_1_1/heatmap_nirq_singlethread_1_1_1.npy"
    heatmap_labels = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue','tx_xmit']*2

    draw_latency(labels, avg_latency, p99_latency,
                 os.path.join(OUT_DIR, "single_thread_latency_only.pdf"))
    draw_breakdown(heatmap_path, heatmap_labels,
                   os.path.join(OUT_DIR, "single_thread_breakdown_only.pdf"))
