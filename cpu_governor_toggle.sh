#!/usr/bin/env bash
# cpu_governor_toggle.sh
# Usage:
#   sudo ./cpu_governor_toggle.sh set       # 指定核心切换到 performance，并把min/max锁到max
#   sudo ./cpu_governor_toggle.sh revert    # 回退到 schedutil，并恢复min/max为出厂范围
#   sudo ./cpu_governor_toggle.sh status    # 查看这些核心的当前 governor / 频率

set -euo pipefail

# 目标核心列表（按你的需求）
CPUS=(32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47
      96 97 98 99 100 101 102 103 104 105 106 107 108 109 110 111)

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "Please run as root: sudo $0 {set|revert|status}" >&2
    exit 1
  fi
}

check_paths() {
  local cpu_path
  for c in "${CPUS[@]}"; do
    cpu_path="/sys/devices/system/cpu/cpu${c}/cpufreq"
    if [[ ! -d "$cpu_path" ]]; then
      echo "WARN: cpu${c} has no cpufreq directory (offline or unsupported)." >&2
    fi
  done
}

show_status_one() {
  local c=$1 p="/sys/devices/system/cpu/cpu${c}/cpufreq"
  if [[ -d $p ]]; then
    local gov cur min max avail
    [[ -f $p/scaling_governor ]] && gov=$(<"$p/scaling_governor") || gov="N/A"
    [[ -f $p/scaling_cur_freq ]] && cur=$(<"$p/scaling_cur_freq") || cur="N/A"
    [[ -f $p/scaling_min_freq ]] && min=$(<"$p/scaling_min_freq") || min="N/A"
    [[ -f $p/scaling_max_freq ]] && max=$(<"$p/scaling_max_freq") || max="N/A"
    [[ -f $p/scaling_available_governors ]] && avail=$(<"$p/scaling_available_governors") || avail="N/A"
    printf "cpu%-3d gov=%-10s cur=%-9s min=%-9s max=%-9s avail=[%s]\n" "$c" "$gov" "$cur" "$min" "$max" "$avail"
  else
    printf "cpu%-3d cpufreq=UNAVAILABLE (offline or unsupported)\n" "$c"
  fi
}

set_governor_one() {
  local c=$1 gov=$2 p="/sys/devices/system/cpu/cpu${c}/cpufreq"
  [[ -d $p ]] || return 0

  # 确认 governor 可用
  if [[ -f $p/scaling_available_governors ]]; then
    if ! grep -qw "$gov" "$p/scaling_available_governors"; then
      echo "WARN: cpu${c} governor '$gov' not in available list; skipping." >&2
      return 0
    fi
  fi

  echo "$gov" > "$p/scaling_governor"
}

lock_freq_to_max_one() {
  local c=$1 p="/sys/devices/system/cpu/cpu${c}/cpufreq"
  [[ -d $p ]] || return 0

  if [[ -f $p/cpuinfo_max_freq ]]; then
    local maxf minf
    maxf=$(<"$p/cpuinfo_max_freq")
    echo "$maxf" > "$p/scaling_max_freq" || true
    echo "$maxf" > "$p/scaling_min_freq" || true
  fi
}

restore_freq_range_one() {
  local c=$1 p="/sys/devices/system/cpu/cpu${c}/cpufreq"
  [[ -d $p ]] || return 0

  # 恢复为芯片报告的最小/最大
  if [[ -f $p/cpuinfo_min_freq && -f $p/cpuinfo_max_freq ]]; then
    local minf maxf
    minf=$(<"$p/cpuinfo_min_freq")
    maxf=$(<"$p/cpuinfo_max_freq")
    echo "$minf" > "$p/scaling_min_freq" || true
    echo "$maxf" > "$p/scaling_max_freq" || true
  fi
}

do_set() {
  echo "==> Switching target CPUs to performance and locking min/max to max"
  for c in "${CPUS[@]}"; do
    set_governor_one "$c" performance
    lock_freq_to_max_one "$c"
  done
  echo "==> Done."
}

do_revert() {
  echo "==> Reverting target CPUs to schedutil and restoring min/max range"
  for c in "${CPUS[@]}"; do
    set_governor_one "$c" schedutil
    restore_freq_range_one "$c"
  done
  echo "==> Done."
}

do_status() {
  echo "==> Status of target CPUs"
  for c in "${CPUS[@]}"; do
    show_status_one "$c"
  done
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    set|revert) require_root ;;
    status) : ;;
    *) echo "Usage: sudo $0 {set|revert|status}"; exit 1 ;;
  esac

  check_paths

  case "$cmd" in
    set)    do_set ;;
    revert) do_revert ;;
    status) do_status ;;
  esac
}

main "$@"
