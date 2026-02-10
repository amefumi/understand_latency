#!/usr/bin/env python3
from bcc import BPF
import time, os

VMLINUX_BUILD = f"/lib/modules/{os.uname().release}/build"
CFLAGS = [f"-I{VMLINUX_BUILD}"]

bpf_text = r"""
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>
#include "kernel/sched/sched.h"

struct rec_t {
    u64 ts;
    u32 cpu;
    u32 tid;        // current thread id
    u32 which;
    u32 nr_running;
    u64 vruntime;
    s64 avg_vruntime;
    u64 avg_load;
    s64 vlag;
    u64 se_ptr;
    u64 cfs_ptr;
};

BPF_ARRAY(recs, struct rec_t, 100);
BPF_ARRAY(idx, u32, 1);

/* tid -> saved args (as u64 addresses), separate per function */
BPF_HASH(arg_se_enq,  u32, u64);
BPF_HASH(arg_cfs_enq, u32, u64);
BPF_HASH(arg_se_deq,  u32, u64);
BPF_HASH(arg_cfs_deq, u32, u64);

static __always_inline int record_ret_common(u32 which, u64 se_addr, u64 cfs_addr)
{
    u32 key0 = 0;
    u32 *ip = idx.lookup(&key0);
    u32 i = ip ? *ip : 0;
    if (i >= 100) return 0;

    u32 cpu = bpf_get_smp_processor_id();
    if (cpu != 32) return 0;

    struct rec_t r = {};
    r.ts = bpf_ktime_get_ns();
    r.cpu = cpu;
    r.tid = (u32)bpf_get_current_pid_tgid();
    r.which = which;
    r.se_ptr  = se_addr;
    r.cfs_ptr = cfs_addr;

    bpf_probe_read_kernel(&r.nr_running, sizeof(r.nr_running),
        (void *)(cfs_addr + offsetof(struct cfs_rq, nr_running)));
    bpf_probe_read_kernel(&r.vruntime, sizeof(r.vruntime),
        (void *)(se_addr + offsetof(struct sched_entity, vruntime)));
    bpf_probe_read_kernel(&r.vlag, sizeof(r.vlag),
        (void *)(se_addr + offsetof(struct sched_entity, vlag)));
    bpf_probe_read_kernel(&r.avg_vruntime, sizeof(r.avg_vruntime),
        (void *)(cfs_addr + offsetof(struct cfs_rq, avg_vruntime)));
    bpf_probe_read_kernel(&r.avg_load, sizeof(r.avg_load),
        (void *)(cfs_addr + offsetof(struct cfs_rq, avg_load)));
        

    recs.update(&i, &r);

    i++;
    idx.update(&key0, &i);
    return 0;
}

static __always_inline int record_ret_enq(void)
{
    u32 tid = (u32)bpf_get_current_pid_tgid();
    u64 *seu  = arg_se_enq.lookup(&tid);
    u64 *cfsu = arg_cfs_enq.lookup(&tid);
    if (!seu || !cfsu) return 0;

    u64 se_addr  = *seu;
    u64 cfs_addr = *cfsu;

    arg_se_enq.delete(&tid);
    arg_cfs_enq.delete(&tid);

    return record_ret_common(1, se_addr, cfs_addr);
}

static __always_inline int record_ret_deq(void)
{
    u32 tid = (u32)bpf_get_current_pid_tgid();
    u64 *seu  = arg_se_deq.lookup(&tid);
    u64 *cfsu = arg_cfs_deq.lookup(&tid);
    if (!seu || !cfsu) return 0;

    u64 se_addr  = *seu;
    u64 cfs_addr = *cfsu;

    arg_se_deq.delete(&tid);
    arg_cfs_deq.delete(&tid);

    return record_ret_common(2, se_addr, cfs_addr);
}

int kprobe__enqueue_entity(struct pt_regs *ctx)
{
    if (bpf_get_smp_processor_id() != 32) return 0;
    u32 tid = (u32)bpf_get_current_pid_tgid();
    u64 cfs = (u64)PT_REGS_PARM1(ctx);
    u64 se  = (u64)PT_REGS_PARM2(ctx);
    arg_cfs_enq.update(&tid, &cfs);
    arg_se_enq.update(&tid, &se);
    return 0;
}
int kretprobe__enqueue_entity(struct pt_regs *ctx)
{
    return record_ret_enq();
}

int kprobe__dequeue_entity(struct pt_regs *ctx)
{
    if (bpf_get_smp_processor_id() != 32) return 0;
    u32 tid = (u32)bpf_get_current_pid_tgid();
    u64 cfs = (u64)PT_REGS_PARM1(ctx);
    u64 se  = (u64)PT_REGS_PARM2(ctx);
    arg_cfs_deq.update(&tid, &cfs);
    arg_se_deq.update(&tid, &se);
    return 0;
}
int kretprobe__dequeue_entity(struct pt_regs *ctx)
{
    return record_ret_deq();
}

"""

b = BPF(text=bpf_text, cflags=CFLAGS)

# wait for 100 samples
while b["idx"][0].value < 100:
    time.sleep(0.01)

# print after end
for k in range(100):
    r = b["recs"][k]
    which = "enqueue_ret" if r.which == 1 else "dequeue_ret"
    print(f"{k} {which} ts={r.ts} cpu={r.cpu} tid={r.tid} "
          f"nr_running={r.nr_running} vruntime={r.vruntime} vlag={r.vlag} avg_vruntime={r.avg_vruntime} avg_load={r.avg_load} "
          f"se=0x{r.se_ptr:x} cfs=0x{r.cfs_ptr:x}")

