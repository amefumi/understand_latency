// breakdown_heatmap.cpp
//
// C++ port of the Python latency-breakdown heatmap generator.
//
// Parses per-packet client/server breakdown logs, reconstructs the end-to-end
// (client -> server -> client) latency stages, keeps the tail (top 0.2%) of the
// distribution sorted by total round-trip time, and writes the result as a
// NumPy .npy array of shape (24, N) that np.load() reads back identically.
//
// Build:  g++ -O2 -std=c++17 heatmap_parse_p99.cpp -o heatmap_parse_p99
//
// Note: the .npy writer assumes a little-endian host (descr '<f8'), which is
// the case on x86-64 / aarch64. All timestamps are read as 64-bit integers.

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

// ---------------------------------------------------------------------------
// Per-packet latency stages (already differenced into durations, in ns).
// ---------------------------------------------------------------------------
struct Latency {
    long long rx_irq, rx_napi, rx_ip, rx_tcp, rx_sched, rx_data_copy;
    long long app;
    long long tx_data_copy, tx_tcp, tx_ip, tx_queue, tx_xmit;
    long long full;     // tx_finish - rx_hw         (used for the server leg)
    long long phase_1;  // rx_return - rx_hw         (client only)
    long long phase_2;  // tx_finish - rx_return     (client only)
};

// Insertion-ordered collection of ports -> list of per-packet latencies.
struct ParsedLog {
    std::vector<long long> order;                 // port keys, insertion order
    std::vector<std::vector<Latency>> latencies;  // parallel to `order`
    std::unordered_map<long long, size_t> index;  // port -> slot in `order`
};

// Matches the Python regex line format. 23 integer fields after the prefix.
static const char* kFmt =
    "source port: %lld destination port: %lld "
    "-- rx -- hw: %lld alloc: %lld irq: %lld napi: %lld gro: %lld ip: %lld "
    "tcp: %lld read: %lld sleep: %lld ready: %lld wakeup: %lld "
    "data copy: %lld return: %lld "
    "-- tx -- alloc: %lld write: %lld data copy: %lld tcp: %lld ip: %lld "
    "queue: %lld xmit: %lld finish: %lld";

// Build a Latency record from the 23 parsed values (v[2..22] are timestamps).
static Latency make_latency(const long long* v) {
    const long long rx_hw        = v[2];
    const long long rx_alloc     = v[3];
    const long long rx_gro       = v[6];
    const long long rx_tcp_ts    = v[8];
    const long long rx_ready     = v[11];
    const long long rx_data_copy = v[13];
    const long long rx_return    = v[14];
    const long long tx_write     = v[16];
    const long long tx_tcp_ts    = v[18];
    const long long tx_ip_ts     = v[19];
    const long long tx_queue     = v[20];
    const long long tx_xmit      = v[21];
    const long long tx_finish    = v[22];

    Latency l;
    l.rx_irq       = rx_alloc - rx_hw;
    l.rx_napi      = rx_gro - rx_alloc;
    l.rx_ip        = rx_tcp_ts - rx_gro;
    l.rx_tcp       = rx_ready - rx_tcp_ts;
    l.rx_sched     = rx_data_copy - rx_ready;
    l.rx_data_copy = rx_return - rx_data_copy;
    l.app          = tx_write - rx_return;
    l.tx_data_copy = tx_tcp_ts - tx_write;
    l.tx_tcp       = tx_ip_ts - tx_tcp_ts;
    l.tx_ip        = tx_queue - tx_ip_ts;
    l.tx_queue     = tx_xmit - tx_queue;
    l.tx_xmit      = tx_finish - tx_xmit;
    l.full         = tx_finish - rx_hw;
    l.phase_1      = rx_return - rx_hw;
    l.phase_2      = tx_finish - rx_return;
    return l;
}

// Parse a breakdown log. `server` selects whether packets are keyed by the
// destination port (server) or the source port (client). The first two
// matched packets per port are skipped to avoid initialization artifacts.
static ParsedLog parse_log(const std::string& path, bool server) {
    ParsedLog out;
    std::ifstream in(path);
    if (!in) {
        std::cerr << "warning: could not open " << path << " (skipping)\n";
        return out;
    }

    std::unordered_map<long long, int> count;
    std::string line;
    long long v[23];

    while (std::getline(in, line)) {
        const auto pos = line.find("source port:");
        if (pos == std::string::npos) continue;

        int matched = std::sscanf(
            line.c_str() + pos, kFmt,
            &v[0], &v[1], &v[2], &v[3], &v[4], &v[5], &v[6], &v[7], &v[8],
            &v[9], &v[10], &v[11], &v[12], &v[13], &v[14], &v[15], &v[16],
            &v[17], &v[18], &v[19], &v[20], &v[21], &v[22]);
        if (matched != 23) continue;

        const long long port = server ? v[1] : v[0];

        auto it = out.index.find(port);
        size_t slot;
        if (it == out.index.end()) {
            slot = out.order.size();
            out.index.emplace(port, slot);
            out.order.push_back(port);
            out.latencies.emplace_back();
            count[port] = 0;
        } else {
            slot = it->second;
        }

        if (count[port] >= 2)  // skip first two packets per port
            out.latencies[slot].push_back(make_latency(v));
        ++count[port];
    }
    return out;
}

// ---------------------------------------------------------------------------
// Combined end-to-end sample. `fields` is already laid out in heatmap row
// order; `total_full` is the round-trip time used for tail selection.
// ---------------------------------------------------------------------------
struct Combined {
    std::array<double, 24> fields;
    double total_full;
};

// End-to-end matching, mirroring combine_breakdown_e2e:
//   client[2i] (send) -> server[2i] (recv+send) -> client[2i+1] (recv)
// Values are converted from ns to us (divide by 1e3). Client port order is
// preserved to match the Python dict-insertion iteration order.
static std::vector<Combined> combine_e2e(const ParsedLog& client,
                                         const ParsedLog& server) {
    std::vector<Combined> combined;
    constexpr double kNsToUs = 1e3;

    for (size_t oi = 0; oi < client.order.size(); ++oi) {
        const long long port = client.order[oi];
        auto sit = server.index.find(port);
        if (sit == server.index.end()) continue;

        const auto& cs = client.latencies[oi];
        const auto& ss = server.latencies[sit->second];

        const size_t num_samples = std::min(cs.size(), ss.size()) / 2;
        for (size_t i = 0; i < num_samples; ++i) {
            const Latency& s1 = cs[i * 2];      // client, sender 1
            const Latency& r1 = ss[i * 2];      // server, receiver 1
            const Latency& s2 = cs[i * 2 + 1];  // client, sender 2 (receiver)

            Combined c;
            // client receive stages come from sender_2
            c.fields[0]  = s2.rx_irq       / kNsToUs;
            c.fields[1]  = s2.rx_napi      / kNsToUs;
            c.fields[2]  = s2.rx_ip        / kNsToUs;
            c.fields[3]  = s2.rx_tcp       / kNsToUs;
            c.fields[4]  = s2.rx_sched     / kNsToUs;
            c.fields[5]  = s2.rx_data_copy / kNsToUs;
            // client app + transmit stages come from sender_1
            c.fields[6]  = s1.app          / kNsToUs;
            c.fields[7]  = s1.tx_data_copy / kNsToUs;
            c.fields[8]  = s1.tx_tcp       / kNsToUs;
            c.fields[9]  = s1.tx_ip        / kNsToUs;
            c.fields[10] = s1.tx_queue     / kNsToUs;
            c.fields[11] = s1.tx_xmit      / kNsToUs;
            // server full stack comes from receiver_1
            c.fields[12] = r1.rx_irq       / kNsToUs;
            c.fields[13] = r1.rx_napi      / kNsToUs;
            c.fields[14] = r1.rx_ip        / kNsToUs;
            c.fields[15] = r1.rx_tcp       / kNsToUs;
            c.fields[16] = r1.rx_sched     / kNsToUs;
            c.fields[17] = r1.rx_data_copy / kNsToUs;
            c.fields[18] = r1.app          / kNsToUs;
            c.fields[19] = r1.tx_data_copy / kNsToUs;
            c.fields[20] = r1.tx_tcp       / kNsToUs;
            c.fields[21] = r1.tx_ip        / kNsToUs;
            c.fields[22] = r1.tx_queue     / kNsToUs;
            c.fields[23] = r1.tx_xmit      / kNsToUs;

            c.total_full = s1.phase_2 / kNsToUs
                         + r1.full    / kNsToUs
                         + s2.phase_1 / kNsToUs;
            combined.push_back(c);
        }
    }
    return combined;
}

// Sort by total round-trip time and keep the top 0.2% tail.
// stable_sort matches Python's stable sort for boundary tie-breaking.
static std::vector<Combined> tail_e2e(std::vector<Combined> latencies) {
    std::stable_sort(latencies.begin(), latencies.end(),
                     [](const Combined& a, const Combined& b) {
                         return a.total_full < b.total_full;
                     });
    const size_t start =
        static_cast<size_t>(static_cast<double>(latencies.size()) * 0.98);
    return std::vector<Combined>(latencies.begin() + start, latencies.end());
}

// Write a (24, N) C-ordered float64 .npy. heatmap[row=field][col=sample].
static bool save_npy(const std::string& path,
                     const std::vector<Combined>& tail) {
    std::ofstream out(path, std::ios::binary);
    if (!out) {
        std::cerr << "error: could not write " << path << "\n";
        return false;
    }
    const size_t N = tail.size();

    std::string header = "{'descr': '<f8', 'fortran_order': False, 'shape': (24, "
                       + std::to_string(N) + "), }";
    const size_t preamble = 10;  // 6 magic + 2 version + 2 header length
    const size_t total = preamble + header.size() + 1;  // +1 for '\n'
    const size_t pad = (64 - (total % 64)) % 64;
    header.append(pad, ' ');
    header.push_back('\n');

    const std::uint16_t hlen = static_cast<std::uint16_t>(header.size());
    out.write("\x93NUMPY", 6);
    out.put('\x01').put('\x00');                       // version 1.0
    out.put(static_cast<char>(hlen & 0xFF));           // header length, LE
    out.put(static_cast<char>((hlen >> 8) & 0xFF));
    out.write(header.data(), static_cast<std::streamsize>(header.size()));

    for (int field = 0; field < 24; ++field)
        for (size_t s = 0; s < N; ++s)
            out.write(reinterpret_cast<const char*>(&tail[s].fields[field]),
                      sizeof(double));
    return static_cast<bool>(out);
}

// Aggregate all runs for one (experiment, n_thread) and return the tail.
static std::vector<Combined> breakdown_heatmap(const std::string& experiment,
                                               const std::vector<int>& runs,
                                               const std::string& dim,
                                               int n_thread,
                                               const std::string& result_dir) {
    std::vector<Combined> combined;
    for (int run : runs) {
        const std::string base = result_dir + "/" + experiment + "_"
                               + std::to_string(n_thread) + "_DIM-" + dim
                               + "_" + std::to_string(run) + "_";
        ParsedLog client = parse_log(base + "client_breakdown.log", false);
        ParsedLog server = parse_log(base + "server_breakdown.log", true);
        std::vector<Combined> c = combine_e2e(client, server);
        combined.insert(combined.end(), c.begin(), c.end());
    }
    return tail_e2e(std::move(combined));
}

int main() {
    const std::string result_dir = "/data2/projects/latency/httpd_wrk2_logs_3000_breakdown";
    const std::vector<std::string> experiments = {"nirqbreakdown"};
    const std::string dim = "off";

    const std::vector<int> threads = {22, 24, 26, 28}; // for nirq dim off
    // const std::vector<int> threads = {18, 20, 22, 24, 26, 26, 28, 30, 32}; // for nirq dim on
    const std::vector<int> runs = {0, 1, 2};

    for (const std::string& experiment : experiments) {
        for (int n_thread : threads) {
            const std::string heatmap_path = result_dir + "/results/heatmap_"
                                           + experiment + "_" + dim + "_"
                                           + std::to_string(n_thread) + "_99.npy";

            std::vector<Combined> tail =
                breakdown_heatmap(experiment, runs, dim, n_thread, result_dir);

            if (!save_npy(heatmap_path, tail)) return 1;
            std::cout << "Generated breakdown heatmap for " << experiment
                      << " with " << n_thread << " threads.\n";
        }
    }
    return 0;
}