"""Build results/SUMMARY.md from the raw data files. Every number in the README comes from here.

usage: python summarize.py > results/SUMMARY.md
"""
import collections, json, re, statistics as st
from pathlib import Path

R = Path(__file__).parent / "results"


def jl(name):
    return [json.loads(l) for l in open(R / name, encoding="utf-8")]


def fmt(xs, nd=1):
    return " / ".join(f"{x:.{nd}f}" for x in xs)


# ---------------- 1. chunk generation speed ----------------
print("## 1. Chunk generation speed (radius 1024 blocks = 16,641 chunks, seed 20260927)\n")
print("Runs interleaved as vanilla, c2me, c2me-lux, c2me-ocl, repeated 3 times.\n")
print("| config | chunks/s per run | mean | x vanilla |")
print("|---|---|---|---|")
rs = [r for r in jl("chunkgen_speed.jsonl") if r["radius"] == 1024]  # later rows are world-building runs at other radii
g = collections.defaultdict(list)
for r in rs: g[r["server"]].append(r["chunks_per_s"])
base = st.mean(g["vanilla"])
for k in ["vanilla", "c2me", "c2me-lux", "c2me-ocl"]:
    print(f"| {k} | {fmt(g[k])} | {st.mean(g[k]):.1f} | {st.mean(g[k]) / base:.1f} |")
print("\nThe first c2me run (and to a lesser extent c2me-lux) came right after vanilla's 6-7 minute save; "
      "treat it as an outlier. Excluding it, c2me = "
      f"{st.mean(g['c2me'][1:]):.1f} chunks/s ({st.mean(g['c2me'][1:]) / base:.1f}x).\n")

# ---------------- 2. cores used ----------------
print("## 2. CPU cores used during generation (radius 512 blocks = 4,225 chunks)\n")
print("| config | chunks/s | mean cores busy (of 20 logical) |")
print("|---|---|---|")
for r in jl("chunkgen_parity_runs.jsonl"):
    print(f"| {r['server']} | {r['chunks_per_s']:.1f} | {r['cpu_cores_mean']:.2f} |")

# ---------------- 3. terrain parity ----------------
print("\n## 3. Does the GPU path produce the same terrain? (central 625 chunks = 61,440,000 blocks)\n")
print("| pair | any block differs | terrain shape differs (ground/fluid/air) | shape, y 56..79 |")
print("|---|---|---|---|")
for a, b, label in [("vanilla_A", "vanilla_B", "vanilla vs vanilla (baseline)"), ("vanilla_A", "c2me_A", "vanilla vs c2me"),
                    ("vanilla_A", "ocl_A", "vanilla vs c2me-ocl (GPU)"), ("ocl_A", "ocl_B", "c2me-ocl vs c2me-ocl")]:
    full = (R / "parity" / f"{a}__{b}.txt").read_text()
    shape = (R / "parity" / f"T_{a}__{b}.txt").read_text()
    p_full = re.search(r"\(([\d.]+%)\)", full).group(1)
    p_shape = re.search(r"differing=[\d,]+\s+\(([\d.]+%)\)", shape).group(1)
    p_surf = re.search(r"56\.\.79.*?\s([\d.]+%)", shape).group(1)
    print(f"| {label} | {p_full} | {p_shape} | {p_surf} |")

# ---------------- 4. mobs on GPU ----------------
print("\n## 4. Mob pushing: CPU vs GPU (ms per tick, median)\n")
print("| scenario | mobs | CPU 1 core | CPU all cores | GPU fp64 | GPU fp32 | fp32 max rel. error |")
print("|---|---|---|---|---|---|---|")
for r in json.load(open(R / "mobs_push.json")):
    print(f"| {r['scenario']} | {r['n']:,} | {r['cpu1_ms']:.3g} | {r['cpuN_ms']:.3g} | {r['gpu64_ms']:.3g} | {r['gpu32_ms']:.3g} | {r['gpu32_max_rel_err']:.2g} |")
print("\n## 5. Pathfinding: per-mob A* vs one shared flow field (128x128 map, 25% walls, ms)\n")
print("| mobs | A* CPU 1 core | A* CPU all cores | flow field CPU 1 core | flow field GPU | A* == BFS | GPU field == BFS |")
print("|---|---|---|---|---|---|---|")
for r in json.load(open(R / "mobs_path.json")):
    print(f"| {r['mobs']:,} | {r['astar_cpu1_ms']:.3g} | {r['astar_cpuN_ms']:.3g} | {r['flow_bfs_cpu1_ms']:.3g} | {r['flow_gpu_ms']:.3g} | {r['astar_matches_bfs']} | {r['gpu_field_matches_bfs']} |")

# ---------------- 6. servers ----------------
num = r"(\d+(?:\.\d+)?)"


def parse(r):
    t = r["report_tail"]
    if r["server"] == "folia":
        med = [float(m.group(1)) for l in t if (m := re.search(r"Median Region TPS: " + num, l))]
        mspt = [float(m.group(1)) for l in t if (m := re.search(num + r" MSPT at", l))]
        regions = [int(m.group(1)) for l in t if (m := re.search(r"Total regions: (\d+)", l))]
        return st.median(med[-6:]), max(mspt[-6:]), max(regions)
    tps = [[float(x) for x in re.findall(num, m.group(1))] for l in t if (m := re.search(r"TPS from last [^:]*: ([\d., ]+)", l))]
    one_min = [(v[1] if len(v) == 4 else v[0]) for v in tps]
    mspt = []
    for i, l in enumerate(t):
        if "Server tick times" in l and i + 1 < len(t):
            vals = re.findall(num + "/" + num + "/" + num, t[i + 1])
            if len(vals) >= 3: mspt.append(float(vals[2][0]))
    return one_min[-1], mspt[-1], None


print("\n## 6. Paper vs Folia vs ShreddedPaper, players spread out (16 groups 1,920 blocks apart, 32 bots)\n")
print("TPS = server-reported (Folia: median region; others: 1-minute average). MSPT = 1-minute average "
      "(Folia: worst of the top-3 regions). Cores = CPU time of the server process / wall time.\n")
print("| villagers | server | TPS per run | MSPT per run | cores per run |")
print("|---|---|---|---|---|")
rows = [r for r in jl("servers_run1.jsonl") if r["server"] != "folia"] + [r for r in jl("servers_folia_rerun.jsonl") if r["server"] == "folia"]
g = collections.defaultdict(list)
for r in rows: g[(r["villagers_target"], r["server"])].append((parse(r), r["server_cores"]))
for (v, s), xs in sorted(g.items()):
    print(f"| {v:,} | {s} | {fmt([x[0][0] for x in xs])} | {fmt([x[0][1] for x in xs])} | {fmt([x[1] for x in xs], 2)} |")
print("\nMethod check (villagers spawned one /summon at a time instead of via a datapack function, 4,800 villagers): ")
for r in jl("servers_folia_rerun.jsonl"):
    if r["server"] != "folia":
        (tps, mspt, _), c = parse(r), r["server_cores"]
        print(f"- {r['server']}: TPS {tps:.1f}, MSPT {mspt:.1f}, cores {c:.2f}")

print("\n## 7. Spread out vs clustered (4,800 villagers, 16 groups, 32 bots)\n")
print("| spacing | server | TPS per run | MSPT per run | cores per run | Folia regions |")
print("|---|---|---|---|---|---|")
g = collections.defaultdict(list)
for r in jl("servers_clustered_vs_spread.jsonl"): g[(r["spacing"], r["server"])].append((parse(r), r["server_cores"]))
for (sp, s), xs in sorted(g.items(), key=lambda x: (-x[0][0], x[0][1])):
    reg = [x[0][2] for x in xs] if s == "folia" else "-"
    print(f"| {sp} | {s} | {fmt([x[0][0] for x in xs], 2)} | {fmt([x[0][1] for x in xs])} | {fmt([x[1] for x in xs], 2)} | {reg} |")

print("\n## 8. Where Paper's main thread spends its time (JFR, 4,800 villagers)\n")
for f in sorted((R / "jfr_breakdown").glob("*.txt")):
    print(f"### {f.stem}\n```\n{f.read_text().strip()}\n```")
