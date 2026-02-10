# Linux + cIRQa 
L1d_load_client = [
    380640327371,
    394747281580,
    400767430054,
    392082288079,
    394592498363
]

L1d_load_server = [
    380227673010,
    393779240264,
    397707559495,
    388713018580,
    392171733104
]

L1d_load_misses_client = [
    18336569949,
    18836019766,
    19215556987,
    19266005461,
    19406942980
]

L1d_load_misses_server = [
    17754180666,
    18740891010,
    18919740526,
    18372127891,
    18607217613,
]

dTLB_load_misses_client = [
    3435884,
    4517387,
    4084451,
    3820526,
    4685010
]

dTLB_load_misses_server = [
    3144114,
    2897285,
    2714540,
    2682830,
    2683742
]

L1d_store_client = [
    231494758680,
    233159841725,
    232873154989,
    232109430833,
    234609860665
]

L1d_store_server = [
    228680448027,
    231059892955,
    229658090103,
    229885556301,
    231060946187
]

dTLB_store_misses_client = [
    1975089,
    1802862,
    2143852,
    1678049,
    2067463,
]

dTLB_store_misses_server = [
    1050038,
    1245961,
    995553,
    1120432,
    913574
]

llc_loads_client = [
    145361728,
    141255588,
    157369089,
    159376356,
    144801169
]

llc_loads_server = [
    145361728,
    141255588,
    157369089,
    159376356,
    144801169
]

llc_load_misses_client = [
    14211584,
    14105366,
    10791198,
    14956766,
    12076258
]

llc_load_misses_server = [
    7157231,
    10190569,
    6131128,
    14812534,
    5658008
]

cache_references_client = [
    1497997760,
    1610211841,
    1511091674,
    1366206649,
    1265627040
]

cache_misses_client = [
    61130750,
    135770731,
    138638937,
    50888147,
    61857219
]

cache_references_server = [
    1228393059,
    1258674962,
    1341461298,
    1306260668,
    1190761074
]

cache_misses_server = [
    28989795,
    25611623,
    30284964,
    54647705,
    31676477
]

# Linux + RR
L1d_load_client_rr = [
    349883276638,
    361240791054,
    363942155915,
    354566262134,
    364087508219
]

L1d_load_server_rr = [
    351666491940,
    358845478346,
    359980404052,
    355570007388,
    361816862782
]

L1d_load_misses_client_rr = [
    17070130012,
    17876080684,
    18299734167,
    17416772951,
    17970261764,
]

L1d_load_misses_server_rr = [
    16401641761,
    16785576409,
    16854035876,
    16980741077,
    16834300619,

]

llc_loads_client_rr = [
    191486711,
    182853245,
    207487785,
    247860412,
    157638955
]

llc_loads_server_rr = [
    182088585,
    173925978,
    213496042,
    183460085,
    173802638,
]

llc_load_misses_client_rr = [
    0,0,0,0,0
]
llc_load_misses_server_rr = [
    0,0,0,0,0
]

import os
import re
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import matplotlib.patheffects as path_effects
from matplotlib.ticker import MultipleLocator, LogLocator, LogFormatter

fm.fontManager.addfont("/home/ame/GillSans.ttc")

# ---------- style (global) ----------
mpl.rcParams.update({
    # font
    "font.family": "Gill Sans",
    "font.size": 14,

    # sizes
    "axes.titlesize": 14,
    "axes.labelsize": 14,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,

    # lines and markers
    "lines.linewidth": 2.5,
    "lines.markersize": 4,
    
    # thick frame and ticks
    "axes.linewidth": 2,
    "xtick.major.width": 1,
    "xtick.major.size": 3,
    "ytick.major.width": 1,
    "ytick.major.size": 3,
    "xtick.minor.width": 2,
    "xtick.minor.size": 2,
    "ytick.minor.width": 2,
    "ytick.minor.size": 2,
    "xtick.direction": "in",
    "ytick.direction": "in",
    
    # grid
    "grid.linestyle": ":",
    "grid.linewidth": 2,
    "grid.color": "black",
    "grid.alpha": 1,
    "axes.axisbelow": True,

    # legend
    "legend.fontsize": 12,
})


# draw L1d-load, L1d-load-misses, dTLB-load-misses, L1d-store, TLB-store-misses in one figure. Each metric is drawn as a bar with stddev error bars.
plt.figure(figsize=(6, 6*0.618))
metrics = [
    ("L1d-loads", L1d_load_client, L1d_load_server, L1d_load_client_rr, L1d_load_server_rr),
    ("L1d-load-misses", L1d_load_misses_client, L1d_load_misses_server, L1d_load_misses_client_rr, L1d_load_misses_server_rr),
    ("LLC-loads", llc_loads_client, llc_loads_server, llc_loads_client_rr, llc_loads_server_rr),
    ("LLC-load-misses", llc_load_misses_client, llc_load_misses_server, llc_load_misses_client_rr, llc_load_misses_server_rr),
]
x = range(len(metrics))
width = 0.35

client_means = [sum(c)/len(c) for _, c, _, __, ___ in metrics]
client_stds = [ (max(c)-min(c))/2 for _, c, _, __, ___ in metrics]
server_means = [sum(s)/len(s) for _, _, s, __, ___ in metrics]
server_stds = [ (max(s)-min(s))/2 for _, _, s, __, ___ in metrics]

plt.bar([i - 0.5*width for i in x], client_means, width, yerr=client_stds, label='Client', capsize=5, color='skyblue', edgecolor='black')
plt.bar([i + 0.5*width for i in x], server_means, width, yerr=server_stds, label='Server', capsize=5, color='salmon', edgecolor='black')
# write L1d-load-misses rate on top of the corresponding bars
for i in range(len(metrics)):
    if metrics[i][0] == "L1d-load-misses":
        client_rate = client_means[i] / client_means[0] * 100
        server_rate = server_means[i] / server_means[0] * 100
        plt.text(i - width/2, client_means[i] + client_stds[i] + 1e7, f"{client_rate:.2f}%", ha='center', va='bottom', fontsize=8, color='black', path_effects=[path_effects.withStroke(linewidth=3, foreground="white")])
        plt.text(i + width/2, server_means[i] + server_stds[i] + 1e7, f"{server_rate:.2f}%", ha='center', va='bottom', fontsize=8, color='black', path_effects=[path_effects.withStroke(linewidth=3, foreground="white")])
for i in range(len(metrics)):
    if metrics[i][0] == "LLC-loads":
        client_rate = client_means[i] / client_means[1] * 100
        server_rate = server_means[i] / server_means[1] * 100
        plt.text(i - width/2, client_means[i] + client_stds[i] + 1e6, f"{client_rate:.2f}%", ha='center', va='bottom', fontsize=8, color='black', path_effects=[path_effects.withStroke(linewidth=3, foreground="white")])
        plt.text(i + width/2, server_means[i] + server_stds[i] + 1e6, f"{server_rate:.2f}%", ha='center', va='bottom', fontsize=8, color='black', path_effects=[path_effects.withStroke(linewidth=3, foreground="white")])
for i in range(len(metrics)):
    if metrics[i][0] == "LLC-load-misses":
        client_rate = client_means[i] / client_means[2] * 100
        server_rate = server_means[i] / server_means[2] * 100
        plt.text(i - width/2, client_means[i] + client_stds[i] + 1e6, f"{client_rate:.2f}%", ha='center', va='bottom', fontsize=8, color='black', path_effects=[path_effects.withStroke(linewidth=3, foreground="white")])
        plt.text(i + width/2, server_means[i] + server_stds[i] + 1e6, f"{server_rate:.2f}%", ha='center', va='bottom', fontsize=8, color='black', path_effects=[path_effects.withStroke(linewidth=3, foreground="white")])
plt.xticks(x, [m[0] for m in metrics], rotation=30, ha='center')
plt.ylabel('Counts')
# plt.yscale('log')
plt.legend()
plt.tight_layout()
plt.savefig('cache_hierarchy_metrics.pdf')
plt.close()

# # draw cache references and cache misses in one figure. Each metric is drawn as a bar with stddev error bars.
# plt.figure(figsize=(6, 6*0.618))
# metrics = [
#     ("Cache References", cache_references_client, cache_references_server),
#     ("Cache Misses", cache_misses_client, cache_misses_server),
# ]
# x = range(len(metrics))
# width = 0.35
# client_means = [sum(c)/len(c) for _, c, _ in metrics]
# client_stds = [ (max(c)-min(c))/2 for _, c, _ in metrics]
# server_means = [sum(s)/len(s) for _, _, s in metrics]
# server_stds = [ (max(s)-min(s))/2 for _, _, s in metrics]
# plt.bar([i - width/2 for i in x], client_means, width, yerr=client_stds, label='Client', capsize=5, color='skyblue', edgecolor='black')
# plt.bar([i + width/2 for i in x], server_means, width, yerr=server_stds, label='Server', capsize=5, color='salmon', edgecolor='black')
# # write cache miss rate on top of the corresponding bars
# for i in range(len(metrics)):
#     if metrics[i][0] == "Cache Misses":
#         client_rate = client_means[i] / client_means[0] * 100
#         server_rate = server_means[i] / server_means[0] * 100
#         plt.text(i - width/2, client_means[i] + client_stds[i] + 1e6, f"{client_rate:.2f}%", ha='center', va='bottom', fontsize=8, color='black', path_effects=[path_effects.withStroke(linewidth=3, foreground="white")])
#         plt.text(i + width/2, server_means[i] + server_stds[i] + 1e6, f"{server_rate:.2f}%", ha='center', va='bottom', fontsize=8, color='black', path_effects=[path_effects.withStroke(linewidth=3, foreground="white")])
# plt.xticks(x, [m[0] for m in metrics], rotation=30, ha='right')
# plt.ylabel('Counts')
# plt.legend()
# plt.tight_layout()
# plt.savefig('general_cache_metrics.pdf')
# plt.close()