"""Entity pushing (the cramming / mob-farm cost) on CPU 1 core, CPU all cores, and GPU.

Vanilla semantics (Entity.push(Entity), called from LivingEntity.pushEntities):
for every pair of overlapping pushable entities, each tick, from both sides:
    dx = other.x - self.x ; dz = other.z - self.z
    d = max(|dx|, |dz|)
    if d >= 0.01:
        d = sqrt(d); dx /= d; dz /= d
        f = min(1, 1/d); dx *= f * 0.05; dz *= f * 0.05
        self.vel  -= (dx, dz) ; other.vel += (dx, dz)
Pushing only adds to velocities and reads positions, so the result does not depend
on the order entities are processed in (up to floating-point summation order).
That is what makes it safe to parallelise. Each entity here accumulates its own
velocity change from all overlapping neighbours, which is the same total as the
vanilla pairwise updates (each pair is visited from both sides in vanilla).

usage: python push_bench.py [--quick]
"""
import json, math, sys, time
import numpy as np
import numba as nb
import cupy as cp

W, H = 0.6, 1.95          # zombie bounding box
CELL = 1.0                # grid cell >= W, so neighbours are within the 3x3 cells


# ---------------- CPU (numba) ----------------

@nb.njit(cache=True)
def _build_grid(x, z, ncx, ncz, x0, z0):
    n = x.shape[0]
    cid = np.empty(n, np.int64)
    for i in range(n):
        cx = min(max(int((x[i] - x0) / CELL), 0), ncx - 1)
        cz = min(max(int((z[i] - z0) / CELL), 0), ncz - 1)
        cid[i] = cx * ncz + cz
    order = np.argsort(cid, kind="mergesort")
    start = np.full(ncx * ncz + 1, 0, np.int64)
    for i in range(n):
        start[cid[i] + 1] += 1
    for c in range(ncx * ncz):
        start[c + 1] += start[c]
    return cid, order, start


def _push_kernel_body(parallel):
    rng = nb.prange if parallel else range

    @nb.njit(parallel=parallel, cache=True, fastmath=False)
    def push(x, y, z, cid, order, start, ncz, ncx, out):
        n = x.shape[0]
        for i in rng(n):
            ax = 0.0; az = 0.0
            ci = cid[i]; cx = ci // ncz; cz = ci % ncz
            for ox in range(-1, 2):
                gx = cx + ox
                if gx < 0 or gx >= ncx: continue
                for oz in range(-1, 2):
                    gz = cz + oz
                    if gz < 0 or gz >= ncz: continue
                    c = gx * ncz + gz
                    for k in range(start[c], start[c + 1]):
                        j = order[k]
                        if j == i: continue
                        dx = x[j] - x[i]; dz = z[j] - z[i]
                        if abs(dx) >= W or abs(dz) >= W or abs(y[j] - y[i]) >= H: continue
                        d = max(abs(dx), abs(dz))
                        if d >= 0.01:
                            d = math.sqrt(d); dx /= d; dz /= d
                            f = 1.0 / d
                            if f > 1.0: f = 1.0
                            # both sides of the pair push: self gets -delta from its own push
                            # and -delta again when the other entity pushes it
                            ax -= 2.0 * dx * f * 0.05
                            az -= 2.0 * dz * f * 0.05
            out[i, 0] = ax; out[i, 1] = az
    return push


push_cpu_1 = _push_kernel_body(False)
push_cpu_n = _push_kernel_body(True)


def run_cpu(fn, x, y, z, ncx, ncz, x0, z0):
    cid, order, start = _build_grid(x, z, ncx, ncz, x0, z0)
    out = np.empty((x.shape[0], 2))
    fn(x, y, z, cid, order, start, ncz, ncx, out)
    return out


# ---------------- GPU (CuPy raw CUDA) ----------------

CUDA_SRC = r"""
extern "C" __global__ void push(const REAL* x, const REAL* y, const REAL* z,
                                const long long* cid, const long long* order, const long long* start,
                                int ncz, int ncx, int n, REAL* out) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    REAL ax = 0, az = 0;
    long long ci = cid[i]; int cx = ci / ncz, cz = ci % ncz;
    for (int ox = -1; ox <= 1; ++ox) { int gx = cx + ox; if (gx < 0 || gx >= ncx) continue;
      for (int oz = -1; oz <= 1; ++oz) { int gz = cz + oz; if (gz < 0 || gz >= ncz) continue;
        long long c = (long long)gx * ncz + gz;
        for (long long k = start[c]; k < start[c + 1]; ++k) {
          long long j = order[k]; if (j == i) continue;
          REAL dx = x[j] - x[i], dz = z[j] - z[i];
          if (fabs(dx) >= (REAL)0.6 || fabs(dz) >= (REAL)0.6 || fabs(y[j] - y[i]) >= (REAL)1.95) continue;
          REAL d = fmax(fabs(dx), fabs(dz));
          if (d >= (REAL)0.01) {
            d = sqrt(d); dx /= d; dz /= d;
            REAL f = (REAL)1 / d; if (f > (REAL)1) f = 1;
            ax -= (REAL)2 * dx * f * (REAL)0.05;
            az -= (REAL)2 * dz * f * (REAL)0.05;
          }
        } } }
    out[2 * i] = ax; out[2 * i + 1] = az;
}
"""
_kernels = {}


def gpu_kernel(dtype):
    if dtype not in _kernels:
        real = "double" if dtype == np.float64 else "float"
        _kernels[dtype] = cp.RawKernel(CUDA_SRC.replace("REAL", real), "push")
    return _kernels[dtype]


def run_gpu(x, y, z, ncx, ncz, x0, z0, dtype, include_transfer=True):
    """If include_transfer, positions start on the host and results end on the host,
    as they would for a JVM server handing one tick's work to the GPU."""
    xs, ys, zs = (cp.asarray(a.astype(dtype)) for a in (x, y, z))
    cx = cp.clip(((xs - x0) / CELL).astype(cp.int64), 0, ncx - 1)
    cz = cp.clip(((zs - z0) / CELL).astype(cp.int64), 0, ncz - 1)
    cid = cx * ncz + cz
    order = cp.argsort(cid)
    counts = cp.bincount(cid, minlength=ncx * ncz)
    start = cp.concatenate([cp.zeros(1, cp.int64), cp.cumsum(counts)]).astype(cp.int64)
    n = x.shape[0]
    out = cp.empty(2 * n, dtype)
    gpu_kernel(dtype)(((n + 255) // 256,), (256,),
                      (xs, ys, zs, cid, order, start, cp.int32(ncz), cp.int32(ncx), cp.int32(n), out))
    if include_transfer:
        return out.get().reshape(n, 2)
    cp.cuda.Stream.null.synchronize()
    return out


# ---------------- scenarios ----------------

def scenario(kind, n, rng):
    if kind == "farm":        # packed into a 4x4-block pen, like a mob farm kill chamber
        side = 4.0
        x = rng.uniform(0, side, n); z = rng.uniform(0, side, n); y = rng.uniform(0, 0.5, n)
    elif kind == "dense":     # a large crowded area, ~4 mobs per block
        side = math.sqrt(n / 4.0)
        x = rng.uniform(0, side, n); z = rng.uniform(0, side, n); y = np.zeros(n)
    else:                     # spread over the loaded area like a normal survival server
        side = 256.0
        x = rng.uniform(0, side, n); z = rng.uniform(0, side, n); y = rng.uniform(60, 90, n)
    ncx = ncz = int(math.ceil(side / CELL)) + 1
    return x, y, z, ncx, ncz, 0.0, 0.0


def timeit(fn, reps):
    fn()  # warm-up (JIT / kernel compile)
    ts = []
    for _ in range(reps):
        t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
    ts.sort()
    return ts[len(ts) // 2] * 1000  # median ms


def main():
    quick = "--quick" in sys.argv
    rng = np.random.default_rng(20260927)
    sizes = {"farm": [50, 100, 200, 400, 800, 1600],
             "dense": [1000, 4000, 16000, 64000, 256000],
             "spread": [1000, 4000, 16000, 64000, 256000]}
    rows = []
    for kind, ns in sizes.items():
        for n in ns[:3] if quick else ns:
            x, y, z, ncx, ncz, x0, z0 = scenario(kind, n, rng)
            reps = 5 if n * (n if kind == "farm" else 1) > 1e6 else 15
            ref = run_cpu(push_cpu_1, x, y, z, ncx, ncz, x0, z0)
            g64 = run_gpu(x, y, z, ncx, ncz, x0, z0, np.float64)
            g32 = run_gpu(x, y, z, ncx, ncz, x0, z0, np.float32)
            scale = max(np.abs(ref).max(), 1e-12)
            row = {
                "scenario": kind, "n": n,
                "cpu1_ms": timeit(lambda: run_cpu(push_cpu_1, x, y, z, ncx, ncz, x0, z0), reps),
                "cpuN_ms": timeit(lambda: run_cpu(push_cpu_n, x, y, z, ncx, ncz, x0, z0), reps),
                "gpu64_ms": timeit(lambda: run_gpu(x, y, z, ncx, ncz, x0, z0, np.float64), reps),
                "gpu32_ms": timeit(lambda: run_gpu(x, y, z, ncx, ncz, x0, z0, np.float32), reps),
                "gpu32_kernel_only_ms": timeit(lambda: run_gpu(x, y, z, ncx, ncz, x0, z0, np.float32, False), reps),
                "gpu64_max_rel_err": float(np.abs(g64 - ref).max() / scale),
                "gpu32_max_rel_err": float(np.abs(g32 - ref).max() / scale),
            }
            rows.append(row)
            print(json.dumps({k: (float(f"{v:.3g}") if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
    with open("push_results.json", "w") as f:
        json.dump(rows, f, indent=1)


if __name__ == "__main__":
    main()
