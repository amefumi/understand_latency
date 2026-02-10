import re
import sys
from collections import defaultdict

def analyze_perf_report(file_path):
    """
    Parses perf report output and calculates cache miss statistics per PID.
    """
    
    # Data structures to hold the aggregation
    # Structure: { pid: total_samples }
    pid_total_misses = defaultdict(int)
    
    # Structure: { pid: { symbol_name: sample_count } }
    pid_symbol_misses = defaultdict(lambda: defaultdict(int))
    
    # Regex to match the data lines.
    # It matches:
    # 1. Percentage (ignored)
    # 2. Sample Count (Captured)
    # 3. PID (Captured)
    # 4. Command Name (Ignored, but matched)
    # 5. Symbol Name (Captured)
    #
    # Example line: 
    # 0.13%          6607    42982:netdriver_test_  [k] psi_group_change
    regex_pattern = re.compile(r"^\s*[0-9.]+%\s+(\d+)\s+(\d+):(\S+)\s+(.+)$")

    try:
        with open(file_path, 'r') as f:
            for line in f:
                # Strip trailing newline
                line = line.rstrip()
                
                # Skip comments and empty lines
                if line.startswith('#') or not line.strip():
                    continue
                
                # Apply regex
                match = regex_pattern.match(line)
                
                if match:
                    samples = int(match.group(1))
                    pid = int(match.group(2))
                    # comm = match.group(3) # We don't strictly need the command name for logic, just PID
                    symbol = match.group(4).strip()
                    
                    # Aggregation Logic
                    pid_total_misses[pid] += samples
                    pid_symbol_misses[pid][symbol] += samples

    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return

    # ---------------------------------------------------------
    # OUTPUT SECTION 1: Total Cache Miss Samples per Thread (PID)
    # ---------------------------------------------------------
    print("="*60)
    print(f"{'PID':<10} | {'Total Cache Miss Samples':<25}")
    print("="*60)
    
    # Sort PIDs by total misses (Descending)
    sorted_pids = sorted(pid_total_misses.items(), key=lambda x: x[1], reverse=True)
    
    for pid, total in sorted_pids:
        print(f"{pid} {total}")

    print("\n" + "="*60)
    print("DETAILED BREAKDOWN PER THREAD (Symbols with >10 samples)")
    print("="*60)

    # ---------------------------------------------------------
    # OUTPUT SECTION 2: Breakdown by Symbol per Thread
    # ---------------------------------------------------------
    all_symbols = set()
    for pid, total in sorted_pids:
        print(f"\nPID: {pid} (Total Misses: {total:,})")
        print(f"{'-'*50}")
        print(f"{'Samples':<15} | {'Symbol'}")
        print(f"{'-'*50}")
        
        # Get symbols for this PID
        symbols = pid_symbol_misses[pid]
        symbols_name = []
        for sym in symbols.keys():
            symbols_name.append(sym)
        print(f"Total unique symbols: {len(symbols_name)}")
        print(f"{'-'*50}")
        all_symbols.update(symbols_name)

        # Filter: Exclude symbols with < 10 calls
        filtered_symbols = {k: v for k, v in symbols.items() if v >= 5}
        
        # Sort by Sample Count (Descending) 
        # (Note: If you strictly wanted alphabetical sort, change key=lambda x: x[0])
        sorted_symbols = sorted(filtered_symbols.items(), key=lambda x: x[1], reverse=True)
        
        if not sorted_symbols:
            print("  (No symbols > 10 samples)")
        
        for sym, count in sorted_symbols:
            print(f"{count:<15,} | {sym}")
    # print(all_symbols)

if __name__ == "__main__":
    # Check if filename is provided
    if len(sys.argv) < 2:
        print("Usage: python3 perf_analyzer.py <filename>")
        print("Example: python3 perf_analyzer.py result.txt")
    else:
        analyze_perf_report(sys.argv[1])