#!/usr/bin/env python3
import os
from matplotlib import transforms
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
    # Analysis parameters
    result_dir = "/data2/projects/latency/httpd_wrk2_logs_3000_breakdown/results"
    # experiments = ["nirq_breakdown_1_1", "dirq_breakdown_1_1", "sirq_breakdown_2_1", "sirq_pcbs_tx_tcp_1", "nirq_pktirq_1_1", "sirq_understanding_24_1"]
    # experiments = ["sirq_pcbs_breakdown_1_1"]
    experiments = ["nirqbreakdown"]
    threads = [22, 24, 26, 28]
    threads = [18, 20, 22, 24, 26, 28, 30, 32]
    dim = "on"
    # Plotting parameters
    heatmap_labels = ['rx_irq', 'rx_napi', 'rx_ip', 'rx_tcp', 'rx_sched', 'rx_data_copy', 'app', 'tx_data_copy', 'tx_tcp', 'tx_ip', 'tx_queue','tx_xmit']*2
    heatmap_cap = 2000
    # heatmap_cap = 500 # Figure 10c-d

    bar = True
    ylabel = True

    pad_left   = 0.8
    pad_left_no_label = 0.4
    pad_right  = 0.95
    pad_right_no_bar = 0.4

    # pad_bottom = 0.65
    pad_bottom = 0.7 # Figure 6a and 10c-d
    pad_top    = 0.15

    for experiment in experiments:
        for n_thread in threads:
            heatmap_path = os.path.join(result_dir, f"heatmap_{experiment}_{dim}_{n_thread}_99.npy")
            # Check if processed heatmap file exists
            assert os.path.exists(heatmap_path), f"Heatmap file {heatmap_path} does not exist. Please run the breakdown analysis first."
            tail_latencies = np.load(heatmap_path)
            print(f"Loaded existing breakdown heatmap for {experiment} with {n_thread} threads.")

            # Initialize figure and axis
            # ax_height = 2.4
            # ax_width = 2.4

            ax_height = 2.2
            ax_width = 2.4

            fig_width = 20
            fig_height = 20

            fig = plt.figure(figsize=(fig_width, fig_height)) # Create a very big figure
            ax_width_frac = ax_width / fig_width
            ax_height_frac = ax_height / fig_height
            ax = fig.add_axes([0.3, 0.3, ax_width_frac, ax_height_frac]) # Add axes at specific position

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

            # Draw heatmap
            ax.imshow(tail_latencies, aspect='auto', interpolation='nearest', vmin=0, vmax=heatmap_cap, cmap=paper_reds)

            # Draw horizontal line to separate client and server
            ax.axhline(y=11.4, color='black', linestyle=(0, (2, 4)), linewidth=1, dash_capstyle='round')
            ax.text(x=tail_latencies.shape[1] / 2, y=11, s='Client', ha='center', fontsize=12)
            ax.text(x=tail_latencies.shape[1] / 2, y=23, s='Server', ha='center', fontsize=12)

            p99_tail_latency = np.sum(tail_latencies[:, tail_latencies.shape[1]//2])
            print(f"p99 tail latency for {experiment} with {n_thread} threads: {p99_tail_latency:.2f} us")

            if bar:
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

                # cb = ax.figure.colorbar(mappable=ax.images[0], ax=ax, fraction=0.046, pad=0.04)
                # cb.set_label('Latency (us)', rotation=90, labelpad=5)
                # cb.ax.yaxis.set_tick_params(labelsize=11)
                # cb.outline.set_visible(False)
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

            ax.set_xlabel('Percentile', labelpad=8)
            ax.set_xticks(ticks=np.linspace(0, tail_latencies.shape[1]-1, 5))

            ax.set_xticklabels([f"{x}" for x in np.linspace(98, 100, 5)], rotation=0, fontsize=12)
            ax.tick_params(axis='x', labelsize=12)

            ax.set_yticks(ticks=np.arange(tail_latencies.shape[0]))


            if ylabel:
                ax.set_yticklabels(labels=heatmap_labels, ha='right', fontsize=8)
                ax.tick_params(axis='y', labelsize=8)
                # labels = ax.get_yticklabels()
                # labels[2].set_color("red")
            else:
                ax.set_yticklabels(labels=[])

            ax.tick_params(axis="both", which="both", width=1, length=3)

            pos = ax.get_position()
            fig_w, fig_h = fig.get_size_inches()
            x0 = fig_w * pos.x0
            y0 = fig_h * pos.y0
            width = fig_w * pos.width
            height = fig_h * pos.height

            bbox = transforms.Bbox.from_extents(
                x0 - pad_left if ylabel else x0 - pad_left_no_label,
                y0 - pad_bottom,
                x0 + width + pad_right if bar else x0 + width + pad_right_no_bar,
                y0 + height + pad_top
            )
            
            save_path = os.path.join(result_dir, f'heatmap_{experiment}_{dim}_{n_thread}_99.pdf')
            plt.savefig(save_path, bbox_inches=bbox)