import subprocess, sys, time
from srv import Server, ROOT
name = sys.argv[1]
s = Server(name, world="shared_r3050"); s.wait_ready(); s.send("op poitest")
r = subprocess.run(["node", str(ROOT / "bots" / "poitest.js")], capture_output=True, text=True, timeout=600)
print(name, "exit", r.returncode); print(r.stdout.strip()[-800:])
s.stop()
