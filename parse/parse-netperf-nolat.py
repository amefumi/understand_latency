#!/usr/bin/env python3
"""Parse netperf throughput logs and print the average throughput.

Usage: parse-netperf-nolat.py DIR N

Reads N logs named "netperf-{index}_throughput.log" (index 0..N-1) from DIR.
Each log has one line: "{thread_pid} {source_port} {throughput}".
"""
import os
import sys


def main():
    if len(sys.argv) != 3:
        sys.exit(f"Usage: {sys.argv[0]} DIR N")

    directory = sys.argv[1]
    n = int(sys.argv[2])

    throughputs = []
    for i in range(n):
        path = os.path.join(directory, f"netperf-{i}_throughput.log")
        with open(path) as f:
            line = f.readline().strip()
        if not line:
            sys.stderr.write(f"warning: empty log {path}\n")
            continue
        # Format: thread_pid source_port throughput
        throughputs.append(float(line.split()[2]))

    if not throughputs:
        sys.exit("error: no throughput values found")

    avg = sum(throughputs) / len(throughputs)
    print(avg)


if __name__ == "__main__":
    main()