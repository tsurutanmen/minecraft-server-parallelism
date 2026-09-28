"""Draw the README figures from results/. usage: python charts.py  (writes docs/*.png)"""
import collections, json, re, statistics as st
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = Path(__file__).parent / "results"
OUT = Path(__file__).parent / "docs"; OUT.mkdir(exist_ok=True)
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = {"paper": "#2a78d6", "folia": "#eb6834", "shredded": "#1baf7a"}  # fixed order: slot 1, 2, 3
NAMES = {"paper": "Paper", "folia": "Folia", "shredded": "ShreddedPaper"}
plt.rcParams.update({"svg.hashsalt": "mc-parallel", "svg.fonttype": "path", "font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK})


def frame(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)


def jl(name):
    return [json.loads(l) for l in open(R / name, encoding="utf-8")]


num = r"(\d+(?:\.\d+)?)"


def tps(r):
    t = r["report_tail"]
    if r["server"].startswith("folia"):
        return st.median([float(m.group(1)) for l in t if (m := re.search(r"Median Region TPS: " + num, l))][-6:])
    v = [[float(x) for x in re.findall(num, m.group(1))] for l in t if (m := re.search(r"TPS from last [^:]*: ([\d., ]+)", l))]
    return [(x[1] if len(x) == 4 else x[0]) for x in v][-1]


# --- 1. spread vs clustered TPS ---
g = collections.defaultdict(list)
for r in jl("servers_clustered_vs_spread.jsonl"): g[(r["spacing"], r["server"])].append(tps(r))
fig, ax = plt.subplots(figsize=(8.4, 4.6), facecolor=SURFACE); frame(ax)
groups = [(1920, "Players spread out\n(16 groups, 1,920 blocks apart)"), (256, "Players clustered\n(16 groups, 256 blocks apart)")]
w = 0.26
for gi, (sp, label) in enumerate(groups):
    for si, s in enumerate(["paper", "folia", "shredded"]):
        vals = g[(sp, s)]; m = st.mean(vals); x = gi + (si - 1) * (w + 0.02)
        ax.bar(x, m, w, color=SERIES[s], label=NAMES[s] if gi == 0 else None, zorder=2)
        ax.text(x, m + 0.35, f"{m:.2f}" if m < 1 else f"{m:.1f}", ha="center", va="bottom", fontsize=10, color=INK)
ax.axhline(20, color=INK2, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
ax.text(-0.45, 20.3, "20 TPS = full speed", ha="left", va="bottom", fontsize=9, color=INK2)
ax.set_xticks([0, 1], [l for _, l in groups]); ax.set_ylim(0, 22.5); ax.set_ylabel("TPS (server-reported, mean of 2 runs)")
ax.set_title("4,800 villagers, 32 bots: Folia collapses when players cluster", loc="left", fontsize=12.5, color=INK, pad=12)
ax.legend(frameon=False, ncol=3, loc="upper right", bbox_to_anchor=(1.0, 0.93))
ax.set_ylim(0, 25)
fig.tight_layout(); fig.savefig(OUT / "servers_spread_vs_clustered.png", dpi=150, facecolor=SURFACE); fig.savefig(OUT / "servers_spread_vs_clustered.svg", facecolor=SURFACE); plt.close(fig)

# --- 2. chunk generation ---
rs = [r for r in jl("chunkgen_speed.jsonl") if r["radius"] == 1024]
g = collections.defaultdict(list)
for r in rs: g[r["server"]].append(r["chunks_per_s"])
cores = collections.defaultdict(list)
for r in jl("chunkgen_parity_runs.jsonl"): cores[r["server"]].append(r["cpu_cores_mean"])
rows = [("vanilla", "Vanilla (Fabric only)", g["vanilla"]), ("c2me", "C2ME", g["c2me"][1:]),
        ("c2me-lux", "C2ME + ScalableLux", g["c2me-lux"][1:]), ("c2me-ocl", "C2ME + OpenCL (RTX 3060)", g["c2me-ocl"])]
fig, ax = plt.subplots(figsize=(8.4, 3.6), facecolor=SURFACE); frame(ax); ax.grid(axis="y", visible=False); ax.grid(axis="x", color=GRID)
for i, (k, label, vals) in enumerate(rows[::-1]):
    m = st.mean(vals)
    ax.barh(i, m, 0.55, color=SERIES["paper"], zorder=2)
    ax.text(m + 6, i, f"{m:.0f} chunks/s  ·  {st.mean(cores[k]):.1f} cores busy", va="center", fontsize=10, color=INK)
ax.set_yticks(range(4), [r[1] for r in rows[::-1]]); ax.set_xlim(0, 820); ax.set_xlabel("chunks generated per second (radius 1,024 blocks)")
ax.set_title("Chunk generation: most of the gain is from using all cores", loc="left", fontsize=12.5, color=INK, pad=12)
fig.tight_layout(); fig.savefig(OUT / "chunkgen.png", dpi=150, facecolor=SURFACE); fig.savefig(OUT / "chunkgen.svg", facecolor=SURFACE); plt.close(fig)

# --- 3. where Paper's tick goes ---
shares = collections.defaultdict(list)
for f in sorted((R / "jfr_breakdown").glob("*.txt")):
    for line in f.read_text().splitlines():
        m = re.match(r"\s*([\d.]+)%\s+of all\s+[\d.]+% of busy\s+(.+)$", line)
        if m: shares[m.group(2)].append(float(m.group(1)))
top = sorted(shares.items(), key=lambda kv: -st.mean(kv[1]))[:8]
fig, ax = plt.subplots(figsize=(8.4, 4.0), facecolor=SURFACE); frame(ax); ax.grid(axis="y", visible=False); ax.grid(axis="x", color=GRID)
for i, (k, v) in enumerate(top[::-1]):
    m = st.mean(v)
    ax.barh(i, m, 0.55, color=SERIES["paper"], zorder=2)
    ax.text(m + 0.8, i, f"{m:.1f}%", va="center", fontsize=10, color=INK)
ax.set_yticks(range(len(top)), [k for k, _ in top[::-1]]); ax.set_xlim(0, 80)
ax.set_xlabel("share of Paper's main-thread samples (JFR, mean of 4 recordings)")
ax.set_title("One kind of work dominates, so splitting by kind caps at ~1.5x", loc="left", fontsize=12.5, color=INK, pad=12)
fig.tight_layout(); fig.savefig(OUT / "paper_tick_breakdown.png", dpi=150, facecolor=SURFACE); fig.savefig(OUT / "paper_tick_breakdown.svg", facecolor=SURFACE); plt.close(fig)
print("wrote", sorted(p.name for p in OUT.glob("*.png")))
