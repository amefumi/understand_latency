import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.ticker import MultipleLocator, LogLocator, LogFormatter
from matplotlib.patches import Circle
import matplotlib.font_manager as fm
import numpy as np

fm.fontManager.addfont("/home/ame/GillSans.ttc")


# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.family": "Gill Sans",
    "font.size": 14,
    # sizes
    "axes.titlesize": 18,
    "axes.labelsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,

    # lines and markers
    "lines.linewidth": 2.5,
    "lines.markersize": 3,
    

    # thick frame and ticks
    "axes.linewidth": 2.0,
    "xtick.major.width": 2.0,
    "ytick.major.width": 2.0,
    "xtick.minor.width": 1.6,
    "ytick.minor.width": 1.6,
})

# ---------- sample data (replace with yours) ----------
x  = np.array([0.12, 0.18, 0.35, 0.65, 0.85, 1.05, 1.18])
y2 = np.array([40, 100, 105, 85, 120, 200, 380])         # “2 threads per core”
y8 = np.array([160, 300, 360, 520, 610, 800, 1300])      # “8 threads per core”
y32= np.array([320, 700, 1000, 1200, 2200, 8000, 13000]) # “32 threads per core”

# colors & markers chosen to match the figure’s feel
c2, c8, c32 = "#5aa02c", "#8b59ff", "#d11b8d"   # green, violet, magenta
m2, m8, m32 = "P", "s", "x"                     # plus-filled, square, x

fig, ax = plt.subplots(figsize=(8, 8*0.618)) # golden ratio

# ---------- plot ----------
ax.plot(x, y2,  color=c2,  marker=m2,  label="2 threads  per core")
ax.plot(x, y8,  color=c8,  marker=m8,  label="8 threads per core")
ax.plot(x, y32, color=c32, marker=m32, label="32 thread  per core")

# log-scale Y with decade ticks (10, 100, 1000, …)
ax.set_yscale("log")
ax.set_ylim(10, 1e5)
ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0,)))
ax.yaxis.set_minor_locator(LogLocator(base=10, subs=np.arange(2,10)*0.1))
ax.yaxis.set_major_formatter(LogFormatter(labelOnlyBase=False))

# linear X with vertical dotted grid every ~0.2
ax.set_xlim(0, 1.6)
ax.xaxis.set_major_locator(MultipleLocator(0.2))
ax.xaxis.set_minor_locator(MultipleLocator(0.1))

# dotted black grid (major + minor)
ax.grid(which="major", linestyle=(0, (1, 10)), color="k", linewidth=2.0)
ax.grid(which="minor", visible=False)

# labels
ax.set_xlabel("Throughput per core (million IOPS)")
ax.set_ylabel("P99.9 Latency (us)")

# legend without frame
leg = ax.legend(frameon=False, loc="upper left")

# thicker tick marks (and a bit longer to match the bold look)
ax.tick_params(which="major", length=8)
ax.tick_params(which="minor", length=5)

# ---------- circle highlights (like the brown circles) ----------
for (xc, yc) in [(0.65, 80), (0.70, 550), (0.85, 2000)]:
    circ = Circle((xc, yc), radius=0.06, transform=ax.transData,
                  fill=False, linewidth=4, edgecolor="#7a3b11", alpha=0.9)
    ax.add_patch(circ)

plt.tight_layout()
plt.savefig("latency_throughput_curve.pdf", bbox_inches='tight')
