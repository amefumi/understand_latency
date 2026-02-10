#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <regex>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

// ----------------------------- Data structs -----------------------------
struct Sample {
  long long rx_hw, rx_alloc, rx_irq, rx_napi, rx_gro, rx_ip, rx_tcp;
  long long rx_read, rx_sleep, rx_ready, rx_wake_up, rx_data_copy, rx_return;
  long long tx_alloc, tx_write, tx_data_copy, tx_tcp, tx_ip, tx_queue, tx_xmit, tx_finish;
};

struct ClientLatency {
  long long rx_hw;
  long long rx_irq, rx_napi, rx_ip, rx_tcp, rx_sched, rx_data_copy;
  long long app, tx_data_copy, tx_tcp, tx_ip, tx_queue, tx_xmit;
  long long phase_1, phase_2, full;
};

struct ServerLatency {
  long long rx_hw;
  long long rx_irq, rx_napi, rx_ip, rx_tcp, rx_sched, rx_data_copy;
  long long app, tx_data_copy, tx_tcp, tx_ip, tx_queue, tx_xmit;
  long long full;
};

struct Combined {
  // Stored in "us" units (Python divides by 1e3)
  double client_app;
  double client_tx_data_copy, client_tx_tcp, client_tx_ip, client_tx_queue, client_tx_xmit;
  double server_rx_irq, server_rx_napi, server_rx_ip, server_rx_tcp, server_rx_sched, server_rx_data_copy;
  double server_app, server_tx_data_copy, server_tx_tcp, server_tx_ip, server_tx_queue, server_tx_xmit;
  double client_rx_irq, client_rx_napi, client_rx_ip, client_rx_tcp, client_rx_sched, client_rx_data_copy;
  double total_full;
};

// ----------------------------- Helpers -----------------------------
static bool read_all_lines(const std::string& path, std::vector<std::string>& lines) {
  std::ifstream in(path);
  if (!in) return false;
  std::string line;
  while (std::getline(in, line)) lines.push_back(line);
  return true;
}

static std::string join_path(const std::string& a, const std::string& b) {
  if (a.empty()) return b;
  if (a.back() == '/') return a + b;
  return a + "/" + b;
}

// Minimal .npy writer (NumPy v1.0) for float64, C-order.
static bool save_npy_f64_2d(const std::string& path,
                           const std::vector<double>& data,
                           size_t rows, size_t cols) {
  // data is row-major, shape (rows, cols)
  if (data.size() != rows * cols) {
    std::cerr << "save_npy_f64_2d: data size mismatch\n";
    return false;
  }

  std::ofstream out(path, std::ios::binary);
  if (!out) {
    std::cerr << "failed to open for write: " << path << " (" << std::strerror(errno) << ")\n";
    return false;
  }

  // Magic + version
  const char magic[] = "\x93NUMPY";
  out.write(magic, 6);
  uint8_t ver_major = 1, ver_minor = 0;
  out.put((char)ver_major);
  out.put((char)ver_minor);

  // Header dict (must end with newline), padded so that
  // (magic+ver+hlen+header) is aligned to 16 bytes.
  // dtype: little-endian float64 => '<f8'
  // fortran_order: False
  // shape: (rows, cols)
  std::string header = "{'descr': '<f8', 'fortran_order': False, 'shape': ("
                     + std::to_string(rows) + ", " + std::to_string(cols) + "), }";
  header.push_back('\n');

  // Pad with spaces to 16-byte alignment after the 10-byte prefix:
  // prefix = 6 (magic) + 2 (ver) + 2 (header_len) = 10 bytes
  size_t header_len = header.size();
  size_t pad = 0;
  while ((10 + header_len + pad) % 16 != 0) pad++;
  header.insert(header.end() - 1, pad, ' '); // insert before '\n'
  header_len = header.size();

  // Write header length as little-endian uint16
  uint16_t hlen = (uint16_t)header_len;
  out.put((char)(hlen & 0xFF));
  out.put((char)((hlen >> 8) & 0xFF));

  out.write(header.data(), (std::streamsize)header.size());

  // Write raw data
  out.write(reinterpret_cast<const char*>(data.data()),
            (std::streamsize)(data.size() * sizeof(double)));

  return out.good();
}

// ----------------------------- Parsers -----------------------------
static const std::regex& log_regex() {
  static const std::regex r(
      R"(.*source port: ([0-9]+) destination port: ([0-9]+) -- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) napi: ([0-9]+) gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) wakeup: ([0-9]+) data copy: ([0-9]+) return: ([0-9]+) -- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) tcp: ([0-9]+) ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+).*)");
  return r;
}

static std::unordered_map<int, std::vector<ClientLatency>>
client_breakdown_parser(const std::string& breakdown_log_path) {
  std::vector<std::string> lines;
  if (!read_all_lines(breakdown_log_path, lines)) {
    std::cerr << "failed to read: " << breakdown_log_path << "\n";
    return {};
  }

  std::unordered_map<int, std::vector<Sample>> samples;
  std::unordered_map<int, int> count;

  std::smatch m;
  for (const auto& line : lines) {
    if (!std::regex_match(line, m, log_regex())) continue;
    if (m.size() != 24) continue; // 23 groups + full match

    // groups: 1..23 => match Python "timestamps"
    // client: port, _, rx_hw, ...
    int port = std::stoi(m[1].str()); // source port
    // int dst_port = std::stoi(m[2].str());

    Sample s{};
    s.rx_hw        = std::stoll(m[3].str());
    s.rx_alloc     = std::stoll(m[4].str());
    s.rx_irq       = std::stoll(m[5].str());
    s.rx_napi      = std::stoll(m[6].str());
    s.rx_gro       = std::stoll(m[7].str());
    s.rx_ip        = std::stoll(m[8].str());
    s.rx_tcp       = std::stoll(m[9].str());
    s.rx_read      = std::stoll(m[10].str());
    s.rx_sleep     = std::stoll(m[11].str());
    s.rx_ready     = std::stoll(m[12].str());
    s.rx_wake_up   = std::stoll(m[13].str());
    s.rx_data_copy = std::stoll(m[14].str());
    s.rx_return    = std::stoll(m[15].str());
    s.tx_alloc     = std::stoll(m[16].str());
    s.tx_write     = std::stoll(m[17].str());
    s.tx_data_copy = std::stoll(m[18].str());
    s.tx_tcp       = std::stoll(m[19].str());
    s.tx_ip        = std::stoll(m[20].str());
    s.tx_queue     = std::stoll(m[21].str());
    s.tx_xmit      = std::stoll(m[22].str());
    s.tx_finish    = std::stoll(m[23].str());

    if (!count.count(port)) count[port] = 0;

    // skip first 2 packets per port (same as Python)
    if (!(count[port] < 2)) {
      samples[port].push_back(s);
    }
    count[port] += 1;
  }

  std::unordered_map<int, std::vector<ClientLatency>> latencies;
  for (auto& kv : samples) {
    int port = kv.first;
    auto& vec = kv.second;
    auto& out = latencies[port];
    out.reserve(vec.size());

    for (const auto& ts : vec) {
      ClientLatency L{};
      L.rx_hw        = ts.rx_hw;
      L.rx_irq       = ts.rx_alloc - ts.rx_hw;
      L.rx_napi      = ts.rx_gro   - ts.rx_alloc;
      L.rx_ip        = ts.rx_tcp   - ts.rx_gro;
      L.rx_tcp       = ts.rx_ready - ts.rx_tcp;
      L.rx_sched     = ts.rx_data_copy - ts.rx_ready;
      L.rx_data_copy = ts.rx_return - ts.rx_data_copy;
      L.app          = ts.tx_write - ts.rx_return;
      L.tx_data_copy = ts.tx_tcp   - ts.tx_write;
      L.tx_tcp       = ts.tx_ip    - ts.tx_tcp;
      L.tx_ip        = ts.tx_queue - ts.tx_ip;
      L.tx_queue     = ts.tx_xmit  - ts.tx_queue;
      L.tx_xmit      = ts.tx_finish - ts.tx_xmit;
      L.phase_1      = ts.rx_return - ts.rx_hw;
      L.phase_2      = ts.tx_finish - ts.rx_return;
      L.full         = ts.tx_finish - ts.rx_hw;
      out.push_back(L);
    }
  }

  return latencies;
}

static std::unordered_map<int, std::vector<ServerLatency>>
server_breakdown_parser(const std::string& breakdown_log_path) {
  std::vector<std::string> lines;
  if (!read_all_lines(breakdown_log_path, lines)) {
    std::cerr << "failed to read: " << breakdown_log_path << "\n";
    return {};
  }

  std::unordered_map<int, std::vector<Sample>> samples;
  std::unordered_map<int, int> count;

  std::smatch m;
  for (const auto& line : lines) {
    if (!std::regex_match(line, m, log_regex())) continue;
    if (m.size() != 24) continue;

    // server: _, port, rx_hw, ...
    int port = std::stoi(m[2].str()); // destination port
    // int src_port = std::stoi(m[1].str());

    Sample s{};
    s.rx_hw        = std::stoll(m[3].str());
    s.rx_alloc     = std::stoll(m[4].str());
    s.rx_irq       = std::stoll(m[5].str());
    s.rx_napi      = std::stoll(m[6].str());
    s.rx_gro       = std::stoll(m[7].str());
    s.rx_ip        = std::stoll(m[8].str());
    s.rx_tcp       = std::stoll(m[9].str());
    s.rx_read      = std::stoll(m[10].str());
    s.rx_sleep     = std::stoll(m[11].str());
    s.rx_ready     = std::stoll(m[12].str());
    s.rx_wake_up   = std::stoll(m[13].str());
    s.rx_data_copy = std::stoll(m[14].str());
    s.rx_return    = std::stoll(m[15].str());
    s.tx_alloc     = std::stoll(m[16].str());
    s.tx_write     = std::stoll(m[17].str());
    s.tx_data_copy = std::stoll(m[18].str());
    s.tx_tcp       = std::stoll(m[19].str());
    s.tx_ip        = std::stoll(m[20].str());
    s.tx_queue     = std::stoll(m[21].str());
    s.tx_xmit      = std::stoll(m[22].str());
    s.tx_finish    = std::stoll(m[23].str());

    if (!count.count(port)) count[port] = 0;

    // skip first 2 packets per port
    if (!(count[port] < 2)) {
      samples[port].push_back(s);
    }
    count[port] += 1;
  }

  std::unordered_map<int, std::vector<ServerLatency>> latencies;
  for (auto& kv : samples) {
    int port = kv.first;
    auto& vec = kv.second;
    auto& out = latencies[port];
    out.reserve(vec.size());

    for (auto ts : vec) { // copy: we may clamp wakeup
      if (ts.rx_ready > ts.rx_wake_up) ts.rx_wake_up = ts.rx_ready;

      ServerLatency L{};
      L.rx_hw        = ts.rx_hw;
      L.rx_irq       = ts.rx_alloc - ts.rx_hw;
      L.rx_napi      = ts.rx_gro   - ts.rx_alloc;
      L.rx_ip        = ts.rx_tcp   - ts.rx_gro;
      L.rx_tcp       = ts.rx_ready - ts.rx_tcp;
      L.rx_sched     = ts.rx_data_copy - ts.rx_ready;
      L.rx_data_copy = ts.rx_return - ts.rx_data_copy;
      L.app          = ts.tx_write - ts.rx_return;
      L.tx_data_copy = ts.tx_tcp   - ts.tx_write;
      L.tx_tcp       = ts.tx_ip    - ts.tx_tcp;
      L.tx_ip        = ts.tx_queue - ts.tx_ip;
      L.tx_queue     = ts.tx_xmit  - ts.tx_queue;
      L.tx_xmit      = ts.tx_finish - ts.tx_xmit;
      L.full         = ts.tx_finish - ts.rx_hw;
      out.push_back(L);
    }
  }

  return latencies;
}

// ----------------------------- Combine / Tail / Heatmap -----------------------------
static std::vector<Combined>
combine_breakdown_e2e(const std::unordered_map<int, std::vector<ClientLatency>>& client_latencies,
                      const std::unordered_map<int, std::vector<ServerLatency>>& server_latencies) {
  std::vector<Combined> combined;

  for (const auto& kv : client_latencies) {
    int port = kv.first;
    auto it = server_latencies.find(port);
    if (it == server_latencies.end()) continue;

    const auto& client_samples = kv.second;
    const auto& server_samples = it->second;

    size_t num_samples = std::min(client_samples.size(), server_samples.size()) / 2;
    for (size_t i = 0; i < num_samples; i++) {
      size_t sender_1 = i * 2;
      size_t receiver_1 = i * 2;
      size_t sender_2 = i * 2 + 1;

      const auto& c1 = client_samples[sender_1];
      const auto& s1 = server_samples[receiver_1];
      const auto& c2 = client_samples[sender_2];

      Combined x{};

      // Python divides by 1e3 here; keep exact same scaling.
      auto to_us = [](long long v) -> double { return (double)v / 1e3; };

      x.client_app          = to_us(c1.app);
      x.client_tx_data_copy = to_us(c1.tx_data_copy);
      x.client_tx_tcp       = to_us(c1.tx_tcp);
      x.client_tx_ip        = to_us(c1.tx_ip);
      x.client_tx_queue     = to_us(c1.tx_queue);
      x.client_tx_xmit      = to_us(c1.tx_xmit);

      x.server_rx_irq       = to_us(s1.rx_irq);
      x.server_rx_napi      = to_us(s1.rx_napi);
      x.server_rx_ip        = to_us(s1.rx_ip);
      x.server_rx_tcp       = to_us(s1.rx_tcp);
      x.server_rx_sched     = to_us(s1.rx_sched);
      x.server_rx_data_copy = to_us(s1.rx_data_copy);

      x.server_app          = to_us(s1.app);
      x.server_tx_data_copy = to_us(s1.tx_data_copy);
      x.server_tx_tcp       = to_us(s1.tx_tcp);
      x.server_tx_ip        = to_us(s1.tx_ip);
      x.server_tx_queue     = to_us(s1.tx_queue);
      x.server_tx_xmit      = to_us(s1.tx_xmit);

      x.client_rx_irq       = to_us(c2.rx_irq);
      x.client_rx_napi      = to_us(c2.rx_napi);
      x.client_rx_ip        = to_us(c2.rx_ip);
      x.client_rx_tcp       = to_us(c2.rx_tcp);
      x.client_rx_sched     = to_us(c2.rx_sched);
      x.client_rx_data_copy = to_us(c2.rx_data_copy);

      x.total_full = to_us(c1.phase_2) + to_us(s1.full) + to_us(c2.phase_1);

      combined.push_back(x);
    }
  }

  return combined;
}

static std::vector<Combined> tail_parser_top_02_percent(std::vector<Combined> v) {
  std::sort(v.begin(), v.end(), [](const Combined& a, const Combined& b) {
    return a.total_full < b.total_full;
  });
  if (v.empty()) return v;

  size_t start = (size_t)std::floor((double)v.size() * 0.998);
  if (start > v.size()) start = v.size();
  return std::vector<Combined>(v.begin() + (long long)start, v.end());
}

// Returns heatmap as row-major (24 x tailN)
static std::vector<double> build_heatmap_24xN(const std::vector<Combined>& tail, size_t& out_rows, size_t& out_cols) {
  out_rows = 24;
  out_cols = tail.size();
  std::vector<double> mat(out_rows * out_cols, 0.0);

  auto set = [&](size_t r, size_t c, double val) {
    mat[r * out_cols + c] = val;
  };

  for (size_t c = 0; c < tail.size(); c++) {
    const auto& s = tail[c];

    // Order matches Python heatmap_tail_parser_e2e(): client (rx.., app, tx..), then server (rx.., app, tx..)
    // (No "total_full" stored in heatmap)
    set(0,  c, s.client_rx_irq);
    set(1,  c, s.client_rx_napi);
    set(2,  c, s.client_rx_ip);
    set(3,  c, s.client_rx_tcp);
    set(4,  c, s.client_rx_sched);
    set(5,  c, s.client_rx_data_copy);
    set(6,  c, s.client_app);
    set(7,  c, s.client_tx_data_copy);
    set(8,  c, s.client_tx_tcp);
    set(9,  c, s.client_tx_ip);
    set(10, c, s.client_tx_queue);
    set(11, c, s.client_tx_xmit);

    set(12, c, s.server_rx_irq);
    set(13, c, s.server_rx_napi);
    set(14, c, s.server_rx_ip);
    set(15, c, s.server_rx_tcp);
    set(16, c, s.server_rx_sched);
    set(17, c, s.server_rx_data_copy);
    set(18, c, s.server_app);
    set(19, c, s.server_tx_data_copy);
    set(20, c, s.server_tx_tcp);
    set(21, c, s.server_tx_ip);
    set(22, c, s.server_tx_queue);
    set(23, c, s.server_tx_xmit);
  }

  return mat;
}

// Equivalent of breakdown_heatmap(...) + np.save(...)
static bool generate_heatmap_for_experiment(const std::string& experiment_dir,
                                            const std::string& experiment_name,
                                            int n_thread,
                                            int dim,
                                            const std::vector<int>& runs) {
  std::vector<Combined> combined_all;

  for (int run : runs) {
    // Python path:
    // breakdown_file_client = .../{n_thread}_64_1_{dim}_1_1_0_0_16_{run}/latencies-{n_thread*16}.log
    // breakdown_file_server = .../{n_thread}_64_1_{dim}_1_1_0_0_16_{run}/latencies-{n_thread*16}-server.log
    std::string subdir = std::to_string(n_thread) + "_64_1_" + std::to_string(dim)
                       + "_1_1_0_0_16_" + std::to_string(run);

    std::string client_file = join_path(join_path(experiment_dir, subdir),
                                        "latencies-" + std::to_string(n_thread * 16) + ".log");
    std::string server_file = join_path(join_path(experiment_dir, subdir),
                                        "latencies-" + std::to_string(n_thread * 16) + "-server.log");

    auto client_lat = client_breakdown_parser(client_file);
    auto server_lat = server_breakdown_parser(server_file);

    auto combined = combine_breakdown_e2e(client_lat, server_lat);
    combined_all.insert(combined_all.end(), combined.begin(), combined.end());
  }

  auto tail = tail_parser_top_02_percent(std::move(combined_all));

  size_t rows = 0, cols = 0;
  auto heatmap = build_heatmap_24xN(tail, rows, cols);

  std::string out_path = join_path(experiment_dir,
      "heatmap_" + experiment_name + "_" + std::to_string(n_thread) + ".npy");

  if (!save_npy_f64_2d(out_path, heatmap, rows, cols)) {
    std::cerr << "failed to write npy: " << out_path << "\n";
    return false;
  }

  std::cout << "Generated breakdown heatmap for " << experiment_name
            << " with " << n_thread << " threads. "
            << "shape=(" << rows << "," << cols << ") -> " << out_path << "\n";
  return true;
}

// ----------------------------- Main -----------------------------
int main(int argc, char** argv) {
  // CLI so you can reuse easily:
  //
  // usage:
  //   breakdown_heatmap_data_cores_parse RESULT_DIR EXPERIMENT N_THREAD DIM RUN0 [RUN1 ...]
  //
  // Example matching your python defaults:
  //   ./breakdown_heatmap_data_cores_parse /data0/projects/latency sirq_pcbs_breakdown_cores_1_1 32 1 0 1 2
  //
  if (argc < 7) {
    std::cerr
      << "usage: " << argv[0] << " RESULT_DIR EXPERIMENT N_THREAD DIM RUN0 [RUN1 ...]\n"
      << "example: " << argv[0] << " /data0/projects/latency sirq_pcbs_breakdown_cores_1_1 32 1 0 1 2\n";
    return 1;
  }

  std::string result_dir = argv[1];
  std::string experiment = argv[2];
  int n_thread = std::atoi(argv[3]);
  int dim = std::atoi(argv[4]);

  std::vector<int> runs;
  for (int i = 5; i < argc; i++) runs.push_back(std::atoi(argv[i]));

  std::string experiment_dir = join_path(result_dir, experiment);

  if (!generate_heatmap_for_experiment(experiment_dir, experiment, n_thread, dim, runs)) {
    return 2;
  }
  return 0;
}
