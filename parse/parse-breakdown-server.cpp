#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <regex>
#include <string>
#include <unordered_map>
#include <vector>

struct Sample {
  long long rx_hw, rx_alloc, rx_irq, rx_napi, rx_gro, rx_ip, rx_tcp;
  long long rx_read, rx_sleep, rx_ready, rx_wake_up, rx_data_copy, rx_return;
  long long tx_alloc, tx_write, tx_data_copy, tx_tcp, tx_ip, tx_queue, tx_xmit, tx_finish;
};

struct Latency {
  long long rx_irq, rx_napi, rx_ip, rx_tcp, rx_sched, rx_data_copy;
  long long app, tx_data_copy, tx_tcp, tx_ip, tx_queue, tx_xmit, full;
};

static size_t py_percentile_index(double p, size_t n) {
  // Matches Python: v[round(p*len(v)) - 1], clamped to [0, n-1]
  long long idx = (long long)std::llround(p * (double)n) - 1;
  if (idx < 0) idx = 0;
  if ((size_t)idx >= n) idx = (long long)n - 1;
  return (size_t)idx;
}

int main(int argc, char** argv) {
  if (argc < 3) {
    std::cerr << "usage: parse-breakdown-server DIR NUM_APPS\n";
    return 1;
  }

  std::string dir = argv[1];
  int N = std::atoi(argv[2]);
  if (N <= 0) {
    std::cerr << "NUM_APPS must be a positive integer\n";
    return 1;
  }

  std::string path = dir + "/latencies-" + std::to_string(N) + "-server.log";
  std::ifstream in(path);
  if (!in) {
    std::cerr << "failed to open: " << path << " (" << std::strerror(errno) << ")\n";
    return 1;
  }

  const std::regex pattern(
      R"(.*source port: ([0-9]+) destination port: ([0-9]+) -- rx -- hw: ([0-9]+) alloc: ([0-9]+) irq: ([0-9]+) napi: ([0-9]+) gro: ([0-9]+) ip: ([0-9]+) tcp: ([0-9]+) read: ([0-9]+) sleep: ([0-9]+) ready: ([0-9]+) wakeup: ([0-9]+) data copy: ([0-9]+) return: ([0-9]+) -- tx -- alloc: ([0-9]+) write: ([0-9]+) data copy: ([0-9]+) tcp: ([0-9]+) ip: ([0-9]+) queue: ([0-9]+) xmit: ([0-9]+) finish: ([0-9]+).*)");

  std::unordered_map<int, std::vector<Sample>> samples;

  std::string line;
  std::smatch m;
  while (std::getline(in, line)) {
    if (!std::regex_match(line, m, pattern)) continue;
    if (m.size() != 24) continue; // 23 capture groups + full match

    std::vector<long long> ts(23);
    for (int i = 0; i < 23; i++) ts[i] = std::stoll(m[i + 1].str());

    int port = 0; // matches your Python script (collapsed ports)
    Sample s{};

    // ts indices match Python timestamps[]
    s.rx_hw        = ts[2];
    s.rx_alloc     = ts[3];
    s.rx_irq       = ts[4];
    s.rx_napi      = ts[5];
    s.rx_gro       = ts[6];
    s.rx_ip        = ts[7];
    s.rx_tcp       = ts[8];
    s.rx_read      = ts[9];
    s.rx_sleep     = ts[10];
    s.rx_ready     = ts[11];
    s.rx_wake_up   = ts[12];
    s.rx_data_copy = ts[13];
    s.rx_return    = ts[14];
    s.tx_alloc     = ts[15];
    s.tx_write     = ts[16];
    s.tx_data_copy = ts[17];
    s.tx_tcp       = ts[18];
    s.tx_ip        = ts[19];
    s.tx_queue     = ts[20];
    s.tx_xmit      = ts[21];
    s.tx_finish    = ts[22];

    samples[port].push_back(s);
  }

  // Compute latencies with the server-specific wakeup clamp:
  // if rx_ready > rx_wake_up: rx_wake_up = rx_ready
  std::unordered_map<int, std::vector<Latency>> latencies;

  for (auto& kv : samples) {
    int port = kv.first;
    auto& vec = kv.second;
    auto& out = latencies[port];
    out.reserve(vec.size());

    for (auto s : vec) { // copy, so we can modify rx_wake_up like Python
      if (s.rx_ready > s.rx_wake_up) s.rx_wake_up = s.rx_ready;

      Latency L{};
      L.rx_irq       = s.rx_alloc - s.rx_hw;
      L.rx_napi      = s.rx_gro   - s.rx_alloc;
      L.rx_ip        = s.rx_tcp   - s.rx_gro;
      L.rx_tcp       = s.rx_ready - s.rx_tcp;
      L.rx_sched     = s.rx_data_copy - s.rx_ready;
      L.rx_data_copy = s.rx_return - s.rx_data_copy;
      L.app          = s.tx_write  - s.rx_return;
      L.tx_data_copy = s.tx_tcp    - s.tx_write;
      L.tx_tcp       = s.tx_ip     - s.tx_tcp;
      L.tx_ip        = s.tx_queue  - s.tx_ip;
      L.tx_queue     = s.tx_xmit   - s.tx_queue;
      L.tx_xmit      = s.tx_finish - s.tx_xmit;
      L.full         = s.tx_finish - s.rx_hw;

      out.push_back(L);
    }

    std::sort(out.begin(), out.end(),
              [](const Latency& a, const Latency& b) { return a.full < b.full; });
  }

  const std::vector<std::string> categories = {
      "rx_irq","rx_napi","rx_ip","rx_tcp","rx_sched","rx_data_copy","app",
      "tx_data_copy","tx_tcp","tx_ip","tx_queue","tx_xmit","full"
  };

  auto get_field = [&](const Latency& L, const std::string& k) -> long long {
    if (k == "rx_irq") return L.rx_irq;
    if (k == "rx_napi") return L.rx_napi;
    if (k == "rx_ip") return L.rx_ip;
    if (k == "rx_tcp") return L.rx_tcp;
    if (k == "rx_sched") return L.rx_sched;
    if (k == "rx_data_copy") return L.rx_data_copy;
    if (k == "app") return L.app;
    if (k == "tx_data_copy") return L.tx_data_copy;
    if (k == "tx_tcp") return L.tx_tcp;
    if (k == "tx_ip") return L.tx_ip;
    if (k == "tx_queue") return L.tx_queue;
    if (k == "tx_xmit") return L.tx_xmit;
    if (k == "full") return L.full;
    return 0;
  };

  auto print_header = [&]() {
    std::cout << "port";
    for (const auto& c : categories) std::cout << "\t" << c;
    std::cout << "\n";
  };

  // AVG (rounded to 3 decimals like Python)
  print_header();
  for (auto& kv : latencies) {
    int port = kv.first;
    const auto& vec = kv.second;
    if (vec.empty()) continue;

    std::unordered_map<std::string, long double> sum;
    for (const auto& c : categories) sum[c] = 0.0L;

    for (const auto& L : vec) {
      for (const auto& c : categories) sum[c] += (long double)get_field(L, c);
    }

    std::cout << port;
    for (const auto& c : categories) {
      long double mean = sum[c] / (long double)vec.size();
      long double rounded = std::round(mean * 1000.0L) / 1000.0L;
      std::cout << "\t" << (double)rounded;
    }
    std::cout << "\n";
  }

  // P99
  print_header();
  for (auto& kv : latencies) {
    int port = kv.first;
    const auto& vec = kv.second;
    if (vec.empty()) continue;

    std::cout << port;
    for (const auto& c : categories) {
      std::vector<long long> vals;
      vals.reserve(vec.size());
      for (const auto& L : vec) vals.push_back(get_field(L, c));
      std::sort(vals.begin(), vals.end());
      size_t idx = py_percentile_index(0.99, vals.size());
      std::cout << "\t" << vals[idx];
    }
    std::cout << "\n";
  }

  // P99.9
  print_header();
  for (auto& kv : latencies) {
    int port = kv.first;
    const auto& vec = kv.second;
    if (vec.empty()) continue;

    std::cout << port;
    for (const auto& c : categories) {
      std::vector<long long> vals;
      vals.reserve(vec.size());
      for (const auto& L : vec) vals.push_back(get_field(L, c));
      std::sort(vals.begin(), vals.end());
      size_t idx = py_percentile_index(0.999, vals.size());
      std::cout << "\t" << vals[idx];
    }
    std::cout << "\n";
  }

  return 0;
}
