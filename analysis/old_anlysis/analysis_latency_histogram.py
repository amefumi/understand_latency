import numpy as np
import matplotlib.pyplot as plt
import os

total_bin = 100000

def read_histogram(file_path):
    assert os.path.exists(file_path), f"File {file_path} does not exist"
    with open(file_path, 'rb') as f:
        data = np.fromfile(f, dtype=np.uint64, count=total_bin)
    return data


bin_1_path = "/data0/projects/latency/airq_breakdown_1_1/48_64_1_1_1_1_0_0_1_2/overall_hist.bin"
bin_2_path = "/data0/projects/latency/sirq_breakdown_4_2/48_64_1_1_1_1_0_0_1_1/overall_hist.bin"
bin_3_path = "/data0/projects/latency/airq_sched_accounting_1_1/48_64_1_1_1_1_0_0_1_1/overall_hist.bin"
bin_4_path = "/data0/projects/latency/sirq_breakdown_1_1/48_64_1_1_1_1_0_0_1_1/overall_hist.bin"

hist_1 = read_histogram(bin_1_path)
hist_2 = read_histogram(bin_2_path)
hist_3 = read_histogram(bin_3_path)
hist_4 = read_histogram(bin_4_path)

# consider i is the latency in microseconds, hist_*[i] is the count of samples with that latency, draw CDF
def cdf(hist, label, color):
    total_samples = np.sum(hist, dtype=np.uint64)
    cumulative = np.cumsum(hist)
    cdf = cumulative / total_samples
    bins = np.arange(total_bin, dtype=np.float64)
    return bins, cdf


bin_1, cdf_1 = cdf(hist_1, "Linux + cIRQa", "blue")
bin_2, cdf_2 = cdf(hist_2, "Linux + SCHEDa (Middle)", "orange")
bin_3, cdf_3 = cdf(hist_3, "Linux + SCHEDa (Good)", "green")
bin_4, cdf_4 = cdf(hist_4, "Linux + SCHEDa (Bad)", "red")

plt.figure(figsize=(8, 6))
plt.plot(bin_1, cdf_1, label="Linux + cIRQa", color="blue")
plt.plot(bin_4, cdf_4, label="Linux + SCHEDa (Bad 500us)", color="red")
plt.plot(bin_2, cdf_2, label="Linux + SCHEDa (Middle 400us)", color="orange")
plt.plot(bin_3, cdf_3, label="Linux + SCHEDa (Good 330us)", color="green")
plt.xlim(1, 1000)  # limit x-axis to 5000 us
# plt.ylim(top=1.)
# plt.yscale('log')
plt.xscale('log')
plt.xlabel("Latency (us)")
plt.ylabel("CDF")
plt.title("Latency CDF Comparison")
plt.grid(True, which="both", color='grey', linestyle='--', linewidth=0.5, zorder=2)
plt.legend()
plt.tight_layout()
plt.savefig("latency_cdf_comparison.pdf", bbox_inches='tight')