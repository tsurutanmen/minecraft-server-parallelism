import re, subprocess, time
from srv import Server, ROOT
s = Server("folia", world="shared_r2450")
s.wait_ready()
for g in range(16): s.send(f"op g{g}b0")
bots = subprocess.Popen(["node", str(ROOT / "bots" / "load.js"), "4", "1", "0", "200"],
                        stdout=open(s.dir / "bots.log", "w"), stderr=subprocess.STDOUT)
ansi = re.compile(r"\x1b\[[0-9;]*m")
for i in range(13):
    time.sleep(15)
    mark = len(s.lines); s.send("tps"); time.sleep(1.5)
    out = [ansi.sub("", l.rstrip()) for l in s.lines[mark:]]
    keep = [l for l in out if any(k in l for k in ("Total regions", "Region around", "Chunks:", "Online Players"))]
    print(f"t={15*(i+1)}s", " | ".join(x.strip() for x in keep), flush=True)
bots.wait(60); s.stop()
