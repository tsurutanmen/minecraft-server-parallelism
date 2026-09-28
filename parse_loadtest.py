"""Summarise loadtest.jsonl: one row per run with the server's own TPS/MSPT reports over the measure window."""
import json, re, statistics as st, sys, collections

rows = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv) > 1 else "loadtest.jsonl", encoding="utf-8")]
num = r"(\d+(?:\.\d+)?)"
out = []
for r in rows:
    t = r["report_tail"]
    rec = {"server": r["server"], "villagers": r["villagers_spawned_by_bots"], "cores": r["server_cores"], "kicked": r["bots_kicked"]}
    if r["server"] == "folia":
        low = [float(m.group(1)) for l in t if (m := re.search(r"Lowest Region TPS: " + num, l))]
        med = [float(m.group(1)) for l in t if (m := re.search(r"Median Region TPS: " + num, l))]
        mspt = [float(m.group(1)) for l in t if (m := re.search(num + r" MSPT at", l))]
        regions = [int(m.group(1)) for l in t if (m := re.search(r"Total regions: (\d+)", l))]
        rec.update(tps=st.median(med[-6:]) if med else None, tps_worst=min(low[-6:]) if low else None,
                   mspt_worst_region=max(mspt[-6:]) if mspt else None, regions=max(regions) if regions else None)
    else:
        tps = []
        for l in t:
            m = re.search(r"TPS from last [^:]*: ([\d., ]+)", l)
            if m: tps.append([float(x) for x in re.findall(num, m.group(1))])
        # Paper: 1m,5m,15m / ShreddedPaper: 5s,1m,5m,15m -> take the 1m figure
        one_min = [(v[1] if len(v) == 4 else v[0]) for v in tps]
        mspt = []
        for i, l in enumerate(t):
            if "Server tick times" in l and i + 1 < len(t):
                vals = re.findall(num + "/" + num + "/" + num, t[i + 1])
                if len(vals) >= 3: mspt.append(float(vals[2][0]))  # 1m avg
        rec.update(tps=one_min[-1] if one_min else None, tps_worst=min(one_min[-6:]) if one_min else None,
                   mspt=mspt[-1] if mspt else None)
    out.append(rec)
g = collections.defaultdict(list)
for r in out: g[(r["server"], r["villagers"])].append(r)
print(f"{'server':9s} {'villagers':>9s} {'TPS (each run)':>18s} {'MSPT':>14s} {'cores':>12s}")
for (s, v), rs in sorted(g.items(), key=lambda x: (x[0][1], x[0][0])):
    tp = [r["tps"] for r in rs]; co = [r["cores"] for r in rs]
    ms = [r.get("mspt", r.get("mspt_worst_region")) for r in rs]
    extra = f" regions={[r.get('regions') for r in rs]}" if s == "folia" else ""
    print(f"{s:9s} {v:9d} {str(tp):>18s} {str(ms):>14s} {str(co):>12s}{extra}")
