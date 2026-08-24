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
    # render mathtext ($...$) in the regular font (Gill Sans) instead of the
    # default Computer Modern math font
    "mathtext.default": "regular",

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

pad_left   = 0.9
pad_right  = 0.3
pad_bottom = 0.7
pad_top    = 0.25

# Modeled CPU cycle cost of an access *served at* (hit by) each level of the
# hierarchy. These costs apply to per-level hits, not references: the rdpmc
# counters are inclusive references (only L1 misses reach L2; only L2 misses
# reach L3), so they must be differenced into hits before being charged (see
# parse below). We now keep only the L2 and L3 reference counters, so an L3
# reference is treated as served at L3 (no DRAM counter is collected).
CACHE_CYCLES = {
    'l2': 15,     # L2 hit
    'l3': 60,     # L3 hit
}

# Highest port (inclusive) to keep when plotting.
SIBLING_PORT = 10023
IS_SIBLINGS = True

# Invalid processing-time sentinel written by the parser when a stage had no
# valid samples for a given port.
INVALID_TIME = -9999


class ThreadData:
    def __init__(self):
        self.pid = 0
        self.total_time = 0.0
        self.average_stall = 0.0
        self.average_stall_l1d = 0.0


def parse_all_thread_info(experiment_dir, filename, total_threads=None):
    """Parse an rdpmc_{client,server}_4.txt into a list of ThreadData (one per port).

    Each row holds, per stage (rxc / app / txc), an average processing time, a
    sample count, *summed* L2/L3 cache references, and *summed* Line Fill
    Buffer occupancy (lfb_occ) and active cycles (lfb_cyc). For every port we:
      1. turn the summed references into per-sample averages by dividing by
         the stage's own sample count (refs / stage_count);
      2. sum those per-sample averages across the three stages to get the
         total average references per level;
      3. sum the three stage average times to get the total average time;
      4. compute the per-stage average lfb_occ and lfb_cyc (each summed
         counter / stage_count), sum the per-stage averages across the three
         stages into sum_lfb_occ / sum_lfb_cyc, and form the per-thread
         avg_sum_lfb_occ = sum_lfb_occ / sum_lfb_cyc (occupancy per cycle);
      5. difference the inclusive references into per-level hits
         (l2_hit = l2 - l3, l3_hit = l3), model CPU cycles from those hits via
         CACHE_CYCLES, then divide the modeled cycles by avg_sum_lfb_occ to
         discount for memory-level parallelism.
    """
    path = os.path.join(experiment_dir, filename)
    with open(path, "r") as f:
        lines = [ln for ln in f.readlines() if ln.strip()]

    header = lines[0].split()
    col = {name: i for i, name in enumerate(header)}

    stages = ['rxc', 'app', 'txc']
    levels = ['l2', 'l3']

    threads_info = []
    for line in lines[1:]:
        vals = line.split()
        if len(vals) < len(header):
            continue

        port = int(vals[col['port']])
        if (IS_SIBLINGS and port <= SIBLING_PORT) or (not IS_SIBLINGS and port > SIBLING_PORT):
            continue

        t = ThreadData()
        t.pid = port

        # (3) total average processing time across the three stages.
        t.total_time = sum(float(vals[col[f'{s}_avg']]) for s in stages)

        # (1)+(2) per-sample average references per level, summed over stages.
        avg_stall_time = {lv: 0.0 for lv in levels}
        for s in stages:
            count = int(vals[col[f'{s}_count']])
            if count == 0:
                continue
            for lv in levels:
                avg_stall_time[lv] += float(vals[col[f'{s}_{lv}']]) / count

        t.average_stall = avg_stall_time['l2']
        t.average_stall_l1d = avg_stall_time['l3']

        threads_info.append(t)

    return threads_info


def new_framed_axes():
    """Create a figure/axes pair with the project's framed, gridded style."""
    ax_height = 2.2
    ax_width = 3.85 / 1.2
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
        "sirq_rdpmc_lfb_understanding_10/48_64_1_1_1_1_0_0_1_0",
        "sirq_rdpmc_lfb_understanding_10/48_64_1_1_1_1_0_0_1_1",
        "sirq_rdpmc_lfb_understanding_10/48_64_1_1_1_1_0_0_1_2",
        "sirq_rdpmc_lfb_understanding_10/48_64_1_1_1_1_0_0_1_3",
        "sirq_rdpmc_lfb_understanding_10/48_64_1_1_1_1_0_0_1_4",
        "sirq_rdpmc_lfb_understanding_10/48_64_1_1_1_1_0_0_1_5",
        "sirq_rdpmc_lfb_understanding_10/48_64_1_1_1_1_0_0_1_6",
        "sirq_rdpmc_lfb_understanding_10/48_64_1_1_1_1_0_0_1_7",
        "sirq_rdpmc_lfb_understanding_10/48_64_1_1_1_1_0_0_1_8",
        "sirq_rdpmc_lfb_understanding_10/48_64_1_1_1_1_0_0_1_9",
    ]

    save_idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    n_thread = 48

    out_dir = "/data0/projects/latency/rdpmc_understanding_10_results"
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
            color="#5484ee",
            markersize=10,
            markeredgewidth=2,
            zorder=3,
        )

        ax.text(
            0.05, 0.9,
            f"$R^2 = {r2:.3f}$",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=16,
            zorder=4,
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor="white",
                edgecolor="none",
                alpha=1.0,
            ),
        )

        ax.set_xlabel(xlabel, labelpad=8)
        ax.set_ylabel(ylabel, labelpad=8)

        save_framed_figure(fig, ax, out_path)
        print(f"[SAVED] {out_path}  "
              f"({len(xs)} points, R^2={r2:.3f}, p={pval:.1e})")

    for exp_index, experiment in enumerate(experiments):
        experiment_dir = os.path.join(result_dir, experiment)
        client_info = parse_all_thread_info(
            experiment_dir, "rdpmc_client_2.txt", n_thread)
        server_info = parse_all_thread_info(
            experiment_dir, "rdpmc_server_2.txt", n_thread)

        # Per-experiment processing-time summary. The client gap is the spread
        # (largest - smallest) of total processing time across the kept client
        # threads; the server figure is the average total processing time across
        # the kept server threads.
        client_times = [t.total_time for t in client_info
                        if t.total_time != INVALID_TIME]
        server_times = [t.total_time for t in server_info
                        if t.total_time != INVALID_TIME]
        client_gap = (max(client_times) - min(client_times)
                      if client_times else float('nan'))
        server_gap = (max(server_times) - min(server_times)
                       if server_times else float('nan'))
        print(f"[STATS] {experiment}: "
              f"client processing-time gap = {client_gap:.1f} ns, "
              f"server processing-time gap = {server_gap:.1f} ns")

        # y: total average processing time (ns); x: modeled CPU cycles, with
        # (lfb) and without (raw) the LFB occupancy discount. Both client and
        # server threads are pooled into the same scatter / fit.
        time_server, stall_server, stall_l1d_server = [], [], []
        time_client, stall_client, stall_l1d_client = [], [], []


        surfix = "" if not IS_SIBLINGS else "_sibling"

        for thread in server_info:
        # for thread in client_info:
            if thread.total_time == INVALID_TIME:
                continue
            time_server.append(thread.total_time)
            stall_server.append(thread.average_stall)
            stall_l1d_server.append(thread.average_stall_l1d)

        raw_path_server = os.path.join(
            out_dir, f"{save_idx[exp_index]}_server_proc_vs_stall{surfix}.pdf")
        plot_model(stall_server, time_server, raw_path_server, '.', "Stall Cycles", "Processing Time (ns)")
        
        raw_path_server_stall = os.path.join(
            out_dir, f"{save_idx[exp_index]}_server_l1d_vs_stall{surfix}.pdf")
        plot_model(stall_l1d_server, stall_server, raw_path_server_stall, '.', "L1d Miss Stall Cycles", "Stall Cycles")

        # for thread in client_info:
        #     if thread.total_time == INVALID_TIME:
        #         continue
        #     time_client.append(thread.total_time)
        #     stall_client.append(thread.average_stall)
        #     stall_l1d_client.append(thread.average_stall_l1d)
        
        # raw_path_client = os.path.join(
        #     out_dir, f"{save_idx[exp_index]}_client_proc_vs_stall{surfix}.pdf")
        # plot_model(stall_client, time_client, raw_path_client, '.', "Stall Cycles", "Processing Time (ns)")
        # raw_path_client_stall = os.path.join(
        #     out_dir, f"{save_idx[exp_index]}_client_l1d_vs_stall{surfix}.pdf")
        # plot_model(stall_l1d_client, stall_client, raw_path_client_stall, '.', "Stall Cycles with L1d Miss", "Stall Cycles" )
