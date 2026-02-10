// rx_sched.c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <stdint.h>
#include <errno.h>

#define MAX_PORT 65536
#define LINE_MAXLEN 4096

typedef struct {
    int *data;
    size_t size;
    size_t cap;
} Vec;

static void vec_init(Vec *v) {
    v->data = NULL; v->size = 0; v->cap = 0;
}
static void vec_free(Vec *v) {
    free(v->data);
    v->data = NULL; v->size = 0; v->cap = 0;
}
static void vec_push(Vec *v, int x) {
    if (v->size == v->cap) {
        size_t nc = (v->cap == 0) ? 256 : v->cap * 2;
        int *nd = (int*)realloc(v->data, nc * sizeof(int));
        if (!nd) { perror("realloc"); exit(1); }
        v->data = nd;
        v->cap = nc;
    }
    v->data[v->size++] = x;
}

static int cmp_int(const void *a, const void *b) {
    int x = *(const int*)a, y = *(const int*)b;
    return (x > y) - (x < y);
}

typedef struct {
    int iodepth;
    double rx_sched_mean;
    int rx_sched_mid;
    int rx_sched_p999;
    int client_p999;
    int server_p999;
} Result;

typedef struct {
    const char *experiment_dir;
    int n_thread;
    int iodepth;
    int dim;
    const int *runs;
    int nruns;
    Result *out;   // 写到 out 指向的 Result
} WorkerArg;

// 解析一个 log，结果写到 ports[port] 动态数组里
// is_server=1: 取 dst port；is_server=0: 取 src port（对应你 Python 逻辑）
static void breakdown_parser(const char *path, int is_server, Vec ports[MAX_PORT]) {
    FILE *fp = fopen(path, "r");
    if (!fp) {
        fprintf(stderr, "Failed to open %s: %s\n", path, strerror(errno));
        exit(1);
    }

    int count[MAX_PORT];
    memset(count, 0, sizeof(count));

    char line[LINE_MAXLEN];
    while (fgets(line, sizeof(line), fp)) {
        // 找到 "source port:" 起点再 sscanf
        char *p = strstr(line, "source port:");
        if (!p) continue;

        int src=0, dst=0, val=0;
        // 注意格式字符串要匹配你日志中的固定片段
        // 这里假设包含 "... source port: %d destination port: %d -- rx -rx_sched: %d ..."
        if (sscanf(p, "source port: %d destination port: %d -- rx -rx_sched: %d",
                   &src, &dst, &val) == 3) {

            int port = is_server ? dst : src;
            if (port < 0 || port >= MAX_PORT) continue;

            // skip first 100 samples per port
            if (count[port] >= 100) {
                vec_push(&ports[port], val);
            }
            count[port] += 1;
        }
    }

    fclose(fp);
}

// combine：把 client+server 对齐相加到 combined；并把 client/server 各自样本全部汇总
static void rx_sched_combine(Vec client_ports[MAX_PORT],
                            Vec server_ports[MAX_PORT],
                            Vec *combined, Vec *combined_clients, Vec *combined_servers) {
    for (int port = 0; port < MAX_PORT; port++) {
        Vec *c = &client_ports[port];
        Vec *s = &server_ports[port];

        if (c->size == 0 && s->size == 0) continue;

        // 汇总 client/server（Python 是全 extend）
        for (size_t i = 0; i < c->size; i++) vec_push(combined_clients, c->data[i]);
        for (size_t i = 0; i < s->size; i++) vec_push(combined_servers, s->data[i]);

        if (c->size > 0 && s->size > 0) {
            size_t n = (c->size < s->size) ? c->size : s->size;
            for (size_t i = 0; i < n; i++) {
                vec_push(combined, c->data[i] + s->data[i]);
            }
        }
    }
}

static void compute_stats(Vec *v, double *mean_out, int *mid_out, int *p999_out) {
    if (v->size == 0) {
        *mean_out = 0.0;
        *mid_out = 0;
        *p999_out = 0;
        return;
    }

    // mean
    long double sum = 0;
    for (size_t i = 0; i < v->size; i++) sum += (long double)v->data[i];
    *mean_out = (double)(sum / (long double)v->size);

    // sort for mid/p999
    qsort(v->data, v->size, sizeof(int), cmp_int);

    *mid_out = v->data[v->size / 2];

    // idx = floor(n*0.999) - 1, clamp
    size_t n = v->size;
    long long idx_ll = (long long)((long double)n * 0.999L) - 1LL;
    if (idx_ll < 0) idx_ll = 0;
    if ((size_t)idx_ll >= n) idx_ll = (long long)n - 1;
    *p999_out = v->data[(size_t)idx_ll];
}

static void *worker_thread(void *arg_) {
    WorkerArg *arg = (WorkerArg*)arg_;

    Vec combined, combined_clients, combined_servers;
    vec_init(&combined);
    vec_init(&combined_clients);
    vec_init(&combined_servers);

    for (int r = 0; r < arg->nruns; r++) {
        int run = arg->runs[r];

        char client_path[1024];
        char server_path[1024];

        // 路径严格对齐你 Python 的 join
        // {dir}/{n_thread}_64_{iodepth}_{dim}_1_1_0_0_1_{run}/latencies-{n_thread}.log
        snprintf(client_path, sizeof(client_path),
                 "%s/%d_64_%d_%d_1_1_0_0_1_%d/latencies-%d.log",
                 arg->experiment_dir, arg->n_thread, arg->iodepth, arg->dim, run, arg->n_thread);

        snprintf(server_path, sizeof(server_path),
                 "%s/%d_64_%d_%d_1_1_0_0_1_%d/latencies-%d-server.log",
                 arg->experiment_dir, arg->n_thread, arg->iodepth, arg->dim, run, arg->n_thread);

        // 每个 run 单独 parse 到 ports[65536]
        Vec client_ports[MAX_PORT];
        Vec server_ports[MAX_PORT];
        for (int i = 0; i < MAX_PORT; i++) { vec_init(&client_ports[i]); vec_init(&server_ports[i]); }

        breakdown_parser(client_path, 0, client_ports);
        breakdown_parser(server_path, 1, server_ports);

        rx_sched_combine(client_ports, server_ports, &combined, &combined_clients, &combined_servers);

        for (int i = 0; i < MAX_PORT; i++) { vec_free(&client_ports[i]); vec_free(&server_ports[i]); }
    }

    // 统计 combined / clients / servers
    double mean = 0;
    int mid = 0, p999 = 0, cp999 = 0, sp999 = 0;

    compute_stats(&combined, &mean, &mid, &p999);

    // client/server p999
    double tmp_mean;
    int tmp_mid;
    compute_stats(&combined_clients, &tmp_mean, &tmp_mid, &cp999);
    compute_stats(&combined_servers, &tmp_mean, &tmp_mid, &sp999);

    arg->out->iodepth = arg->iodepth;
    arg->out->rx_sched_mean = mean;
    arg->out->rx_sched_mid  = mid;
    arg->out->rx_sched_p999 = p999;
    arg->out->client_p999   = cp999;
    arg->out->server_p999   = sp999;

    vec_free(&combined);
    vec_free(&combined_clients);
    vec_free(&combined_servers);
    return NULL;
}

static int cmp_result_iodepth(const void *a, const void *b) {
    const Result *ra = (const Result*)a;
    const Result *rb = (const Result*)b;
    return (ra->iodepth > rb->iodepth) - (ra->iodepth < rb->iodepth);
}

int main(int argc, char **argv) {
    const char *result_dir = "/data0/projects/latency/";
    const char *experiment_name = "sirq_pcbs_breakdown_iodepth_3_1";
    int threads = 32;
    int dim = 1;

    int iodepths[] = {48, 64, 80, 96};
    // int iodepths[] = {20, 24, 32};
    int niodepths = (int)(sizeof(iodepths)/sizeof(iodepths[0]));

    int runs[] = {0, 1, 2,};
    int nruns = (int)(sizeof(runs)/sizeof(runs[0]));

    char experiment_dir[1024];
    snprintf(experiment_dir, sizeof(experiment_dir), "%s/%s", result_dir, experiment_name);

    char results_path[1024];
    snprintf(results_path, sizeof(results_path), "%s/rx_sched_combined_iodepth_%d_dimon.data",
             experiment_dir, threads);

    // 写表头
    FILE *out = fopen(results_path, "w");
    if (!out) { perror("open results"); return 1; }
    fprintf(out, "iodepth,rx_sched_mean,rx_sched_mid,rx_sched_p999,client_p999,server_p999\n");
    fclose(out);

    pthread_t tids[64];
    WorkerArg args[64];
    Result results[64];

    for (int i = 0; i < niodepths; i++) {
        args[i].experiment_dir = experiment_dir;
        args[i].n_thread = threads;
        args[i].iodepth = iodepths[i];
        args[i].dim = dim;
        args[i].runs = runs;
        args[i].nruns = nruns;
        args[i].out = &results[i];

        int rc = pthread_create(&tids[i], NULL, worker_thread, &args[i]);
        if (rc != 0) {
            fprintf(stderr, "pthread_create failed: %s\n", strerror(rc));
            return 1;
        }
    }

    for (int i = 0; i < niodepths; i++) {
        pthread_join(tids[i], NULL);
    }

    // 按 iodepth 排序
    qsort(results, niodepths, sizeof(Result), cmp_result_iodepth);

    // 统一写入
    out = fopen(results_path, "a");
    if (!out) { perror("open results append"); return 1; }
    for (int i = 0; i < niodepths; i++) {
        Result *r = &results[i];
        fprintf(out, "%d,%.6f,%d,%d,%d,%d\n",
                r->iodepth, r->rx_sched_mean, r->rx_sched_mid,
                r->rx_sched_p999, r->client_p999, r->server_p999);

        printf("Generated breakdown heatmap for %s with %d iodepth.\n",
               experiment_name, r->iodepth);
    }
    fclose(out);

    return 0;
}
