DURATION_SEC=30
OUTPUT_LOG="dim.log"

# Remove old kprobe and trace log for clean slate
echo "-:mlx5_cq_mod" | sudo tee /sys/kernel/debug/tracing/kprobe_events
sudo trace-cmd clear

# Create a new kprobe
echo 'p:mlx5_cq_mod mlx5_core_modify_cq_moderation cqn=+0(%si):u32 period=%dx:u16 count=%cx:u16' | sudo tee /sys/kernel/debug/tracing/kprobe_events

# Arm the kprobe, and sleep
echo 1 | sudo tee /sys/kernel/debug/tracing/events/kprobes/mlx5_cq_mod/enable
echo "Monitoring for $DURATION_SEC seconds. Press Ctrl+C to stop early."
sleep "$DURATION_SEC"

# Stop the kprobe and save results
echo "Stopping trace..."
echo 0 | sudo tee /sys/kernel/debug/tracing/events/kprobes/mlx5_cq_mod/enable
sudo cat /sys/kernel/debug/tracing/trace > $OUTPUT_LOG
echo "Done. Results saved to $OUTPUT_LOG"
