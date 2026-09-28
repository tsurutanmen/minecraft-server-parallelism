"""Run one load test: server + bot swarm, record the server's own TPS/MSPT reports and CPU use.

usage: python loadtest.py <server> <groups> <bots_per_group> <v50_times> [--measure 120] [--warmup 60]
Appends one JSON line to loadtest.jsonl; raw console output is in servers/<server>/run.log.
"""
import argparse, json, subprocess, sys, threading, time
import psutil
from srv import Server, ROOT

ap = argparse.ArgumentParser()
ap.add_argument("server"); ap.add_argument("groups", type=int); ap.add_argument("bpg", type=int); ap.add_argument("k", type=int)
ap.add_argument("--measure", type=int, default=120); ap.add_argument("--warmup", type=int, default=60)
a = ap.parse_args()

busy = subprocess.run(["tasklist", "/FI", "IMAGENAME eq java.exe"], capture_output=True, text=True).stdout
if "java.exe" in busy: sys.exit("another java.exe is running")

s = Server(a.server, world="shared_r3050")
s.wait_ready()
for g in range(a.groups):
    for b in range(a.bpg):
        s.send(f"op g{g}b{b}")
launch = a.groups * a.bpg * 0.25 + 35 + a.k * 50 * 0.045 + 12
bots = subprocess.Popen(["node", str(ROOT / "bots" / "load.js"), str(a.groups), str(a.bpg), str(a.k),
                         str(int(launch + a.warmup + a.measure + 10))],
                        stdout=open(s.dir / "bots.log", "w"), stderr=subprocess.STDOUT)
time.sleep(launch + a.warmup)
mark = len(s.lines)
jp = psutil.Process(s.p.pid); np_ = psutil.Process(bots.pid)
c0 = sum(jp.cpu_times()[:2]); n0 = sum(np_.cpu_times()[:2]); t0 = time.time()
for i in range(a.measure // 10):
    s.send("tps"); s.send("mspt")
    time.sleep(10)
cores = (sum(jp.cpu_times()[:2]) - c0) / (time.time() - t0)
node_cores = (sum(np_.cpu_times()[:2]) - n0) / (time.time() - t0)
import re as _re
_ansi = _re.compile(r"\[[0-9;]*m")
report = [_ansi.sub("", l.rstrip()) for l in s.lines[mark:]
          if not any(k in l for k in ("issued server command", "joined the game", "left the game", "logged in", "lost connection", "UUID of player", "Summoned"))]
bots.wait(120)
s.stop()
villagers_spawned = sum(1 for l in open(s.dir / "bots.log") if "SPAWNED_VILLAGERS" in l) * a.k * 50
kicked = [l for l in open(s.dir / "bots.log") if "KICKED" in l]
rec = {"server": a.server, "groups": a.groups, "bots_per_group": a.bpg, "villagers_target": a.groups * a.k * 50,
       "villagers_spawned_by_bots": villagers_spawned,
       "villagers_counted_by_bots": sum(int(l.split()[-1]) for l in open(s.dir / "bots.log") if "VILLAGER_COUNT" in l), "bots_kicked": len(kicked),
       "server_cores": round(cores, 2), "bot_process_cores": round(node_cores, 2),
       "report_tail": report[-80:], "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
with open(ROOT / "loadtest.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print(json.dumps({k: v for k, v in rec.items() if k != "report_tail"}))
print("\n".join(report[-25:]))
