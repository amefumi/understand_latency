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


markers = [
    MarkerStyle("o", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle("p", capstyle="round", joinstyle="round", fillstyle="none"),
    MarkerStyle(".", capstyle="round", joinstyle="round"),
    MarkerStyle("*", capstyle="round", joinstyle="round"),
]


pad_left   = 0.9
pad_right  = 0.3
pad_bottom = 0.7
pad_top    = 0.25

class ThreadData:
    def __init__(self):
        self.pid = 0
        self.rx_data_copy_time = 0
        self.rx_data_copy_cache_miss = []
        self.app_time = 0
        self.app_cache_miss = []
        self.tx_data_copy_time = 0
        self.tx_data_copy_cache_miss = []
        self.subtotal_time = 0
        self.subtotal_cache_miss = []

    def __repr__(self):
        return (f"ThreadData(pid={self.pid}, "
                f"rxc={self.rx_data_copy_time:.1f}/{self.rx_data_copy_cache_miss}, "
                f"app={self.app_time:.1f}/{self.app_cache_miss}, "
                f"txc={self.tx_data_copy_time:.1f}/{self.tx_data_copy_cache_miss}, "
                f"subtotal={self.subtotal_time:.1f}/{self.subtotal_cache_miss})")


# Invalid processing-time sentinel written by the parser when a stage had no
# valid samples for a given port.
INVALID_TIME = -9999


def parse_all_thread_info(experiment_dir, total_threads=None):
    """Parse rdpmc_client.txt into a list of ThreadData.

    Each row in rdpmc_client.txt corresponds to one client thread (port). The
    cache-miss lists are ordered [L1, L2, L3(LLC)] so they line up with the
    `level` indices used below.
    """
    client_path = os.path.join(experiment_dir, "rdpmc_client.txt")
    with open(client_path, "r") as f:
        lines = [ln for ln in f.readlines() if ln.strip()]

    header = lines[0].split()
    col = {name: i for i, name in enumerate(header)}

    threads_info = []
    for line in lines[1:]:
        vals = line.split()
        if len(vals) < len(header):
            continue

        port = int(vals[col['port']])
        if port >= 10024:
            continue

        t = ThreadData()
        t.pid = port

        t.rx_data_copy_time = float(vals[col['rxc_avg']])
        t.rx_data_copy_cache_miss = [int(vals[col['rxc_l1']]),
                                     int(vals[col['rxc_l2']]),
                                     int(vals[col['rxc_llc']])]

        t.app_time = float(vals[col['app_avg']])
        t.app_cache_miss = [int(vals[col['app_l1']]),
                            int(vals[col['app_l2']]),
                            int(vals[col['app_llc']])]

        t.tx_data_copy_time = float(vals[col['txc_avg']])
        t.tx_data_copy_cache_miss = [int(vals[col['txc_l1']]),
                                     int(vals[col['txc_l2']]),
                                     int(vals[col['txc_llc']])]

        t.subtotal_time = float(vals[col['total_avg']])
        t.subtotal_cache_miss = [int(vals[col['total_l1']]),
                                 int(vals[col['total_l2']]),
                                 int(vals[col['total_llc']])]

        threads_info.append(t)

    if total_threads is not None and len(threads_info) != total_threads:
        print(f"[WARN] expected {total_threads} threads but parsed {len(threads_info)}")

    return threads_info


def new_framed_axes():
    """Create a figure/axes pair with the project's framed, gridded style."""
    ax_height = 2.2
    ax_width = 3.85 / 1.1
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
        linewidth=2,
        edgecolor="black",
        facecolor="none",
        transform=ax.transAxes,
        zorder=1,
        clip_on=False,
    )
    ax.add_patch(bbox)

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

    return fig, ax


def save_framed_figure(fig, ax, out_path):
    """Save with the padded bounding box used by the other figures."""
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

    fig.savefig(out_path, bbox_inches=bbox)
    plt.close(fig)


if __name__ == "__main__":

    result_dir = "/data0/projects/latency/"
    experiment = "sirq_rdpmc_l3_2_1/48_64_1_1_1_1_0_0_1_8"
    series = ['rx_data_copy', 'app', 'tx_data_copy', 'subtotal']
    level = ['l1_miss', 'l2_miss', 'l3_miss']
    n_thread = 48

    out_dir = "/data0/projects/latency/rdpmc_results"
    os.makedirs(out_dir, exist_ok=True)

    experiment_dir = os.path.join(result_dir, experiment)
    threads_info = parse_all_thread_info(experiment_dir, n_thread)

    for thread in threads_info:
        print(thread)

    # Map each series name to (time attribute, cache-miss-list attribute) on
    # ThreadData, plus a human-readable label / color / marker for the plot.
    series_attr = {
        'rx_data_copy': ('rx_data_copy_time', 'rx_data_copy_cache_miss'),
        'app':          ('app_time',          'app_cache_miss'),
        'tx_data_copy': ('tx_data_copy_time', 'tx_data_copy_cache_miss'),
        'subtotal':     ('subtotal_time',     'subtotal_cache_miss'),
    }
    series_label = {
        'rx_data_copy': 'RX Data Copy',
        'app':          'Application',
        'tx_data_copy': 'TX Data Copy',
        'subtotal':     'Subtotal',
    }
    series_style = {
        'rx_data_copy': ('teal',           markers[0]),
        'app':          ('darkslateblue',  markers[1]),
        'tx_data_copy': ('cornflowerblue', markers[3]),
        'subtotal':     ('darkturquoise',  markers[2]),
    }

    # Map level name to the index inside the cache-miss list and its label.
    level_index = {'l1_miss': 0, 'l2_miss': 1, 'l3_miss': 2}
    level_label = {'l1_miss': 'L1', 'l2_miss': 'L2', 'l3_miss': 'L3 (LLC)'}

    # Draw one figure per (series, level) combination.
    for s in series:
        time_attr, miss_attr = series_attr[s]
        color, marker = series_style[s]

        for lv in level:
            idx = level_index[lv]

            xs = []
            ys = []
            for thread in threads_info:
                t = getattr(thread, time_attr)
                if t == INVALID_TIME:
                    continue
                misses = getattr(thread, miss_attr)
                xs.append(misses[idx])
                ys.append(t)

            xs = np.asarray(xs)
            ys = np.asarray(ys)

            fig, ax = new_framed_axes()

            ax.plot(
                xs, ys,
                linestyle="none",
                marker=marker,
                color=color,
                markersize=8,
                markeredgewidth=2,
                zorder=3,
                label=series_label[s],
            )

            ax.set_xlabel(f"{level_label[lv]} cache misses", labelpad=8)
            ax.set_ylabel("Processing time (ns)", labelpad=8)
            # ax.legend(loc='upper left', markerfirst=False, labelspacing=0.2,
            #           facecolor='white', edgecolor='white', framealpha=1,
            #           handletextpad=0.4)

            out_name = f"rdpmc_{s}_{lv}.pdf"
            save_framed_figure(fig, ax, os.path.join(out_dir, out_name))
            print(f"[SAVED] {os.path.join(out_dir, out_name)}  ({len(xs)} points)")
