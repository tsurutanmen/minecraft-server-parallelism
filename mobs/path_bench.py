"""Mobs chasing one player: per-mob A* vs one shared flow field (CPU 1 core, CPU all cores, GPU).

Map: 2D walkable grid, 4-connected, unit step cost, random walls. All mobs target
the same player cell, which is the case a flow field is built for (a horde chasing
one player). Correctness check: every A* path length must equal the flow-field
distance from that mob's cell.

usage: python path_bench.py
"""
import json, time
import numpy as np
import numba as nb
import cupy as cp

SIZE = 128        # map is SIZE x SIZE blocks (vanilla follow range for zombies is 35-40 blocks)
WALLS = 0.25


def make_map(rng):
    walk = rng.random((SIZE, SIZE)) > WALLS
    c = SIZE // 2
    walk[c - 1:c + 2, c - 1:c + 2] = True
    return walk, (c, c)


# ---------------- CPU ----------------

@nb.njit(cache=True)
def bfs(walk, ty, tx):
    n = walk.shape[0]
    dist = np.full((n, n), -1, np.int32)
    qy = np.empty(n * n, np.int32); qx = np.empty(n * n, np.int32)
    dist[ty, tx] = 0; qy[0] = ty; qx[0] = tx; head = 0; tail = 1
    while head < tail:
        y = qy[head]; x = qx[head]; head += 1
        for k in range(4):
            yy = y + (1 if k == 0 else -1 if k == 1 else 0)
            xx = x + (1 if k == 2 else -1 if k == 3 else 0)
            if 0 <= yy < n and 0 <= xx < n and walk[yy, xx] and dist[yy, xx] < 0:
                dist[yy, xx] = dist[y, x] + 1
                qy[tail] = yy; qx[tail] = xx; tail += 1
    return dist


@nb.njit(cache=True)
def astar(walk, sy, sx, ty, tx):
    """Binary-heap A* with Manhattan heuristic; returns path length or -1."""
    n = walk.shape[0]
    g = np.full(n * n, 1 << 30, np.int32)
    closed = np.zeros(n * n, np.bool_)
    heap_f = np.empty(4 * n * n, np.int32); heap_v = np.empty(4 * n * n, np.int32); size = 0
    s = sy * n + sx; t = ty * n + tx
    g[s] = 0
    heap_f[0] = abs(sy - ty) + abs(sx - tx); heap_v[0] = s; size = 1
    while size > 0:
        v = heap_v[0]
        size -= 1
        lf = heap_f[size]; lv = heap_v[size]; i = 0
        while True:  # sift down the last element from the root
            c = 2 * i + 1
            if c >= size: break
            if c + 1 < size and heap_f[c + 1] < heap_f[c]: c += 1
            if heap_f[c] >= lf: break
            heap_f[i] = heap_f[c]; heap_v[i] = heap_v[c]; i = c
        heap_f[i] = lf; heap_v[i] = lv
        if closed[v]: continue
        closed[v] = True
        if v == t: return g[v]
        y = v // n; x = v % n
        for k in range(4):
            yy = y + (1 if k == 0 else -1 if k == 1 else 0)
            xx = x + (1 if k == 2 else -1 if k == 3 else 0)
            if 0 <= yy < n and 0 <= xx < n and walk[yy, xx]:
                u = yy * n + xx
                ng = g[v] + 1
                if ng < g[u]:
                    g[u] = ng
                    f = ng + abs(yy - ty) + abs(xx - tx)
                    i = size; size += 1
                    while i > 0:  # sift up
                        p = (i - 1) // 2
                        if heap_f[p] <= f: break
                        heap_f[i] = heap_f[p]; heap_v[i] = heap_v[p]; i = p
                    heap_f[i] = f; heap_v[i] = u
    return -1


def _all_astar(parallel):
    rng_ = nb.prange if parallel else range

    @nb.njit(parallel=parallel, cache=True)
    def run(walk, ys, xs, ty, tx, out):
        for i in rng_(ys.shape[0]):
            out[i] = astar(walk, ys[i], xs[i], ty, tx)
    return run


astar_1 = _all_astar(False)
astar_n = _all_astar(True)


# ---------------- GPU flow field ----------------

RELAX = cp.RawKernel(r"""
extern "C" __global__ void relax(const bool* walk, const int* din, int* dout, int n, int* changed) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n * n) return;
    int d = din[i];
    if (walk[i]) {
        int y = i / n, x = i % n;
        if (y > 0     && din[i - n] >= 0 && (d < 0 || din[i - n] + 1 < d)) d = din[i - n] + 1;
        if (y < n - 1 && din[i + n] >= 0 && (d < 0 || din[i + n] + 1 < d)) d = din[i + n] + 1;
        if (x > 0     && din[i - 1] >= 0 && (d < 0 || din[i - 1] + 1 < d)) d = din[i - 1] + 1;
        if (x < n - 1 && din[i + 1] >= 0 && (d < 0 || din[i + 1] + 1 < d)) d = din[i + 1] + 1;
    }
    dout[i] = d;
    if (d != din[i]) *changed = 1;
}
""", "relax")


def flow_gpu(walk_d, ty, tx, check_every=16):
    n = SIZE
    a = cp.full(n * n, -1, cp.int32); a[ty * n + tx] = 0
    b = cp.empty_like(a); changed = cp.zeros(1, cp.int32)
    grid = ((n * n + 255) // 256,)
    it = 0
    while True:
        if it % check_every == 0: changed[0] = 0
        RELAX(grid, (256,), (walk_d, a, b, cp.int32(n), changed)); a, b = b, a; it += 1
        if it % check_every == 0 and int(changed.get()[0]) == 0:
            return a.reshape(n, n), it


def timeit(fn, reps=7):
    fn()
    ts = []
    for _ in range(reps):
        t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
    ts.sort(); return ts[len(ts) // 2] * 1000


def main():
    rng = np.random.default_rng(20260927)
    walk, (ty, tx) = make_map(rng)
    ref = bfs(walk, ty, tx)
    free = np.argwhere(ref > 0)
    walk_d = cp.asarray(walk.ravel())
    gdist, iters = flow_gpu(walk_d, ty, tx)
    gpu_ok = bool((gdist.get() == ref).all())
    rows = []
    bfs_ms = timeit(lambda: bfs(walk, ty, tx))
    gpu_flow_ms = timeit(lambda: flow_gpu(walk_d, ty, tx)[0].get())  # incl. copying the field back to the host
    for m in [10, 100, 1000, 10000]:
        pick = free[rng.integers(0, len(free), m)]
        ys = pick[:, 0].astype(np.int32); xs = pick[:, 1].astype(np.int32)
        out = np.empty(m, np.int32)
        astar_1(walk, ys, xs, ty, tx, out)
        astar_ok = bool((out == ref[ys, xs]).all())
        row = {"mobs": m, "map": f"{SIZE}x{SIZE}", "walls": WALLS,
               "astar_cpu1_ms": timeit(lambda: astar_1(walk, ys, xs, ty, tx, out), 3 if m >= 10000 else 7),
               "astar_cpuN_ms": timeit(lambda: astar_n(walk, ys, xs, ty, tx, out), 3 if m >= 10000 else 7),
               "flow_bfs_cpu1_ms": bfs_ms, "flow_gpu_ms": gpu_flow_ms, "gpu_relax_iterations": iters,
               "astar_matches_bfs": astar_ok, "gpu_field_matches_bfs": gpu_ok,
               "mean_path_len": float(ref[ys, xs].mean())}
        rows.append(row)
        print(json.dumps({k: (float(f"{v:.3g}") if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
    json.dump(rows, open("path_results.json", "w"), indent=1)


if __name__ == "__main__":
    main()
