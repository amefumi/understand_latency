// pmu_check.c — deterministic pointer-chase microbenchmark.
//
// Dual mode:
//   * latency_pmu loaded  -> read PMCs via rdpmc and report counter deltas.
//   * latency_pmu absent  -> WORKLOAD-ONLY: just run the chase (no rdpmc), so
//                            you can wrap the binary in perf, which owns the
//                            counters in that case.
//
// Build:
//   gcc -O2 -o pmu_check pmu_check.c
//
// With the module (rdpmc):
//   sudo insmod latency_pmu.ko cpus=32,96      # module sets CR4.PCE on 32,96
//   sudo taskset -c 32 ./pmu_check 32          # cpu [bufMiB] [stepsM]
//
// With perf (workload only):
//   sudo rmmod latency_pmu                      # free the counters for perf
//   perf stat -C 32 \
//     -e cpu/event=0x24,umask=0xe1/ \
//     -e cpu/event=0x2a,umask=0x01,offcore_rsp=0x10001/ \
//     -e cpu/event=0x2b,umask=0x01,offcore_rsp=0x3fbfc00001/ \
//     -- taskset -c 32 ./pmu_check 32 1024 200
//   (perf wraps the WHOLE process, so the one-time buffer build is included;
//    use a large stepsM so the build is a small fraction, or pass perf -D <ms>
//    ~= the reported setup time to start counting at the chase.)
//
// Counter index -> event (MUST match latency_pmu.ko counters[] order):
//   PMC0 : L2_RQSTS.ALL_DEMAND_DATA_RD
//   PMC1 : OCR.DEMAND_DATA_RD.ANY_RESPONSE
//   PMC2 : OCR.DEMAND_DATA_RD.L3_MISS

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sched.h>
#include <signal.h>
#include <setjmp.h>
#include <unistd.h>
#include <time.h>

#define NUM_COUNTERS 3
#define CACHELINE    64
#define MODULE_SYSFS "/sys/module/latency_pmu"

static const char *names[NUM_COUNTERS] = {
    "L2_RQSTS.ALL_DEMAND_DATA_RD",
    "OCR.DEMAND_DATA_RD.ANY_RESPONSE",
    "OCR.DEMAND_DATA_RD.L3_MISS",
};

static inline uint64_t rdpmc(uint32_t idx)
{
    uint32_t lo, hi;
	asm volatile("rdpmc"
		     : "=a"(lo), "=d"(hi)
		     : "c"(idx));
	return ((uint64_t)hi << 32) | lo;
}

// Catch a #GP from rdpmc (CR4.PCE not set) and fall back to workload-only.
static sigjmp_buf jb;
static void on_sigsegv(int sig) { (void)sig; siglongjmp(jb, 1); }

static uint64_t xs = 0x9e3779b97f4a7c15ULL;
static inline uint64_t xnext(void)
{
    xs ^= xs << 13; xs ^= xs >> 7; xs ^= xs << 17;
    return xs;
}

static inline uint64_t now_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

// The measured region: a dependent pointer chase.
static void *do_chase(void *start, uint64_t steps)
{
    void *p = start;
    for (uint64_t s = 0; s < steps; s++)
        p = *(void **)p;
    __asm__ __volatile__("" :: "r"(p));   // keep it from being optimized away
    return p;
}

int main(int argc, char **argv)
{
    int      cpu     = (argc > 1) ? atoi(argv[1]) : 32;
    uint64_t buf_mib = (argc > 2) ? strtoull(argv[2], NULL, 10) : 1024;
    uint64_t steps_m = (argc > 3) ? strtoull(argv[3], NULL, 10) : 30;

    uint64_t buf_bytes = buf_mib * 1024ULL * 1024ULL;
    uint64_t steps     = steps_m * 1000ULL * 1000ULL;
    size_t   nslots    = buf_bytes / CACHELINE;

    uint64_t before[NUM_COUNTERS], after[NUM_COUNTERS];
    uint64_t t0, t1;

    // Pin to the target CPU.
    cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu, &set);
    if (sched_setaffinity(0, sizeof(set), &set)) { perror("sched_setaffinity"); return 1; }
    printf("pinned to CPU %d, working set %llu MiB (%zu lines), %llu steps\n",
           cpu, (unsigned long long)buf_mib, nslots, (unsigned long long)steps);

    // Decide the mode: rdpmc only if the module is loaded.
    int use_rdpmc = 0;
    if (access(MODULE_SYSFS, F_OK) == 0) {
        // Module present — probe rdpmc, but tolerate a #GP (wrong CPU, etc.).
        signal(SIGSEGV, on_sigsegv);
        if (sigsetjmp(jb, 1) == 0) {
            (void)rdpmc(0);
            use_rdpmc = 1;
        } else {
            fprintf(stderr,
                "latency_pmu is loaded but rdpmc #GP'd on CPU %d "
                "(is this CPU in cpus=? CR4.PCE set?). Workload-only mode.\n", cpu);
        }
        signal(SIGSEGV, SIG_DFL);
        if (use_rdpmc)
            printf("mode: rdpmc (latency_pmu programmed this CPU)\n");
    } else {
        printf("mode: workload-only (latency_pmu not loaded — measure with perf)\n");
    }

    // Build a single-cycle random permutation (Sattolo) over cache lines.
    if (use_rdpmc) {
        t0 = now_ns();
        for (int c = 0; c < NUM_COUNTERS; c++) before[c] = rdpmc(c);
    }

    uint64_t setup0 = now_ns();
    char   *buf  = aligned_alloc(CACHELINE, nslots * CACHELINE);
    size_t *perm = malloc(nslots * sizeof(size_t));
    if (!buf || !perm) { perror("alloc"); return 1; }

    for (size_t i = 0; i < nslots; i++) perm[i] = i;
    for (size_t i = nslots - 1; i > 0; i--) {
        size_t j = (size_t)(xnext() % i);
        size_t t = perm[i]; perm[i] = perm[j]; perm[j] = t;
    }
    for (size_t i = 0; i < nslots; i++) {
        char *cur = buf + perm[i]                * CACHELINE;
        char *nxt = buf + perm[(i + 1) % nslots] * CACHELINE;
        *(void **)cur = (void *)nxt;
    }
    free(perm);
    printf("setup: %.2f ms (buffer build; excluded from rdpmc bracket, "
           "included in a whole-process perf run)\n",
           (double)(now_ns() - setup0) / 1e6);

    // Run the measured chase.
    if (use_rdpmc) {
        do_chase(buf, steps);
        for (int c = 0; c < NUM_COUNTERS; c++) after[c] = rdpmc(c);
        t1 = now_ns();

        printf("\nelapsed %.2f ms, %.2f ns/access\n\n",
               (double)(t1 - t0) / 1e6, (double)(t1 - t0) / (double)steps);
        printf("%-34s %14s %14s\n", "event", "delta", "delta/steps");
        for (int c = 0; c < NUM_COUNTERS; c++) {
            uint64_t d = (after[c] - before[c]);
            printf("PMC%d %-29s %14llu %13.3f\n",
                   c, names[c], (unsigned long long)d, (double)d / (double)steps);
        }
    } else {
        printf("\n===== CHASE BEGIN =====\n");
        t0 = now_ns();
        do_chase(buf, steps);
        t1 = now_ns();
        printf("===== CHASE END =====\n");
        printf("elapsed %.2f ms, %.2f ns/access "
               "(counters measured externally by perf)\n",
               (double)(t1 - t0) / 1e6, (double)(t1 - t0) / (double)steps);
    }

    free(buf);
    return 0;
}
