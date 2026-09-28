import re, subprocess, time
from srv import Server, ROOT
ansi = re.compile(r"\x1b\[[0-9;]*m")
s = Server("folia", world="shared_r2450"); s.wait_ready()
def report(tag):
    mark = len(s.lines); s.send("tps"); time.sleep(1.5)
    out = [ansi.sub("", l.strip()) for l in s.lines[mark:]]
    print(tag, " | ".join(l for l in out if any(k in l for k in ("Total regions", "Region around", "Chunks:"))), flush=True)
report("start")
procs = []
for i, (x, z) in enumerate([(-2304, -2304), (-2304 + 2304, -2304), (-2304, -2304 + 1920)]):
    s.send(f"op d{i}")
    procs.append(subprocess.Popen(["node", str(ROOT / "bots" / "one.js"), f"d{i}", str(x), str(z)], stdout=subprocess.PIPE, text=True))
    time.sleep(20); report(f"after bot{i} ({x},{z})")
time.sleep(30); report("after 30s more")
for p in procs: p.kill()
for p in procs: print(p.stdout.read().strip())
s.stop()
