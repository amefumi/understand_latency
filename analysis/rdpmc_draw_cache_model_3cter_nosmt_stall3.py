import os
import re
import matplotlib as mpl
import numpy as np
from scipy import stats
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

# Highest port (inclusive) to keep when plotting.
MAX_PORT = 19999

# Invalid processing-time sentinel written by the parser when a stage had no
# valid samples for a given port.
INVALID_TIME = -9999


class ThreadData:
    def __init__(self):
        self.pid = 0
        self.total_time = 0.0
        self.average_cycle = 0.0
        self.average_stall = 0.0
        self.average_inst = 0.0


def parse_all_thread_info(experiment_dir, filename, total_threads=None):

    path = os.path.join(experiment_dir, filename)
    with open(path, "r") as f:
        lines = [ln for ln in f.readlines() if ln.strip()]

    header = lines[0].split()
    col = {name: i for i, name in enumerate(header)}

    stages = ['rxc', 'app', 'txc']
    levels = ['l1', 'l2', 'l3'] # l1: cycles, l2: stalls, l3: instructions

    threads_info = []
    for line in lines[1:]:
        vals = line.split()
        if len(vals) < len(header):
            continue

        port = int(vals[col['port']])
        if port > MAX_PORT:
            continue

        t = ThreadData()
        t.pid = port
        t.total_time = sum(float(vals[col[f'{s}_avg']]) for s in stages)

        average_values = {lv: 0.0 for lv in levels}
        for s in stages:
            count = int(vals[col[f'{s}_count']])
            if count == 0:
                continue
            for lv in levels:
                average_values[lv] += float(vals[col[f'{s}_{lv}']]) / count

        t.average_cycle = average_values['l1']
        t.average_stall = average_values['l2']
        t.average_inst = average_values['l3']

        threads_info.append(t)

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
    result_dir = "/data2/projects/latency/"
    experiments = [
        "sirq_rdpmc_lfb_understanding_9/28_64_1_1_1_1_0_0_1_0",
        "sirq_rdpmc_lfb_understanding_9/28_64_1_1_1_1_0_0_1_1",
        "sirq_rdpmc_lfb_understanding_9/28_64_1_1_1_1_0_0_1_2",
        "sirq_rdpmc_lfb_understanding_9/28_64_1_1_1_1_0_0_1_3",
        "sirq_rdpmc_lfb_understanding_9/28_64_1_1_1_1_0_0_1_4",
        "sirq_rdpmc_lfb_understanding_9/28_64_1_1_1_1_0_0_1_5",
        "sirq_rdpmc_lfb_understanding_9/28_64_1_1_1_1_0_0_1_6",
        "sirq_rdpmc_lfb_understanding_9/28_64_1_1_1_1_0_0_1_7",
        "sirq_rdpmc_lfb_understanding_9/28_64_1_1_1_1_0_0_1_8",
        "sirq_rdpmc_lfb_understanding_9/28_64_1_1_1_1_0_0_1_9",
    ]

    save_idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    n_thread = 48

    out_dir = "/data0/projects/latency/rdpmc_nosmt_stall3_performance"
    os.makedirs(out_dir, exist_ok=True)

    def plot_model(xs, ys, out_path, marker, xlabel, ylabel):
        """Scatter processing time vs modeled CPU cycles with a linear fit."""
        xs = np.asarray(xs)
        ys = np.asarray(ys)

        # Least-squares linear fit of measured processing time against the
        # modeled CPU cycles. r2 is the coefficient of determination; pval is
        # the two-sided p-value for the null hypothesis of zero slope.
        r2, pval = np.nan, np.nan
        if len(xs) >= 2:
            fit = stats.linregress(xs, ys)
            r2 = fit.rvalue ** 2
            pval = fit.pvalue

        fig, ax = new_framed_axes()

        ax.plot(
            xs, ys,
            linestyle="none",
            marker=marker,
            color="teal",
            markersize=8,
            markeredgewidth=2,
            zorder=3,
        )

        ax.text(
            0.04, 0.96,
            f"$R^2 = {r2:.3f}$\n$p = {pval:.1e}$",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=15,
            zorder=4,
            # bbox=dict(
            #     boxstyle="round,pad=0.3",
            #     facecolor="white",
            #     edgecolor="none",
            #     alpha=1.0,
            # ),
        )

        ax.set_xlabel(xlabel, labelpad=8)
        ax.set_ylabel(ylabel, labelpad=8)

        save_framed_figure(fig, ax, out_path)
        print(f"[SAVED] {out_path}  "
              f"({len(xs)} points, R^2={r2:.3f}, p={pval:.1e})")

    for exp_index, experiment in enumerate(experiments):
        experiment_dir = os.path.join(result_dir, experiment)
        server_info = parse_all_thread_info(
            experiment_dir, "rdpmc_server_3.txt", n_thread)

        server_times = [t.total_time for t in server_info
                        if t.total_time != INVALID_TIME]
        server_cycles = [t.average_cycle for t in server_info
                         if t.total_time != INVALID_TIME]
        server_stalls = [t.average_stall for t in server_info
                         if t.total_time != INVALID_TIME]
        server_insts = [t.average_inst for t in server_info
                        if t.total_time != INVALID_TIME]

        server_work_cycles = [cycle - stall for cycle, stall in zip(server_cycles, server_stalls)]
        
        server_ipc = sum(server_insts) / sum(server_cycles) # estimation of IPC
        server_min_inst = min(server_insts) if len(server_insts) > 0 else 0
        server_insts_normed = [inst - server_min_inst for inst in server_insts]
        server_modeled = [inst_normed + stall for inst_normed, stall in zip(server_insts_normed, server_stalls)]

        # estimation of extra cycles due to extra instructions
        server_inst_extra = [inst_normed * server_ipc for inst_normed in server_insts_normed]

        raw_path_server = os.path.join(
            out_dir, f"{save_idx[exp_index]}_server_proc_vs_cycles.pdf")
        plot_model(server_cycles, server_times, raw_path_server, markers[0], "Average CPU Cycles", "Processing Time (ns)")

        raw_path_server = os.path.join(
            out_dir, f"{save_idx[exp_index]}_server_proc_vs_stall.pdf")
        plot_model(server_stalls, server_times, raw_path_server, markers[0], "Average Stall Cycles", "Processing Time (ns)")

        raw_path_server = os.path.join(
            out_dir, f"{save_idx[exp_index]}_server_proc_vs_inst.pdf")
        plot_model(server_insts, server_times, raw_path_server, markers[0], "Average Instructions", "Processing Time (ns)")

        raw_path_server = os.path.join(
            out_dir, f"{save_idx[exp_index]}_server_proc_vs_modeled.pdf")
        plot_model(server_modeled, server_times, raw_path_server, markers[0], "Average Modeled Cycles", "Processing Time (ns)")
