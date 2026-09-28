"""Chunk generation benchmark: start a server, pregenerate a fixed square with Chunky, time it.

usage: python bench.py <server-dir> <radius-blocks> [--keep-world]
Appends one JSON line per run to results.jsonl.
"""
import json, os, re, shutil, subprocess, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).parent
JAVA = next((ROOT / "jdk").glob("jdk-25*")) / "bin" / "java.exe"

def main():
    # a server left over from an earlier run would compete for CPU/GPU
    busy = subprocess.run(["tasklist", "/FI", "IMAGENAME eq java.exe"], capture_output=True, text=True).stdout
    if "java.exe" in busy:
        sys.exit("another java.exe is running; refusing to benchmark")
    sdir = ROOT / "servers" / sys.argv[1]
    radius = int(sys.argv[2])
    if "--keep-world" not in sys.argv:
        shutil.rmtree(sdir / "world", ignore_errors=True)
    log = open(sdir / "bench.log", "w", encoding="utf-8")
    p = subprocess.Popen(
        [str(JAVA), "-Xms8G", "-Xmx8G", "-jar", "server.jar", "--nogui"],
        cwd=sdir, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1)
    lines = []
    ev = {"done": threading.Event(), "finished": threading.Event()}
    result = {}
    def reader():
        for line in p.stdout:
            log.write(line); log.flush(); lines.append(line)
            if "Done (" in line and "For help" in line:
                ev["done"].set()
            m = re.search(r"Task finished for .*?Processed: (\d+) chunks.*?Total time: ([\d:]+)", line)
            if m:
                result["chunks"] = int(m.group(1)); result["chunky_time"] = m.group(2)
                ev["finished"].set()
    threading.Thread(target=reader, daemon=True).start()
    def send(cmd):
        p.stdin.write(cmd + "\n"); p.stdin.flush()
    t_start = time.time()
    if not ev["done"].wait(600):
        p.kill(); sys.exit("server did not start")
    startup = time.time() - t_start
    send("chunky world minecraft:overworld"); send("chunky center 0 0")
    send(f"chunky radius {radius}"); send("chunky silent"); send("chunky start")
    t0 = time.time()
    cpu = []
    def sampler():
        import psutil
        proc = psutil.Process(p.pid)
        last = sum(proc.cpu_times()[:2]); lt = time.time()
        while not ev["finished"].wait(2):
            now = sum(proc.cpu_times()[:2]); nt = time.time()
            cpu.append((now - last) / (nt - lt)); last, lt = now, nt
    threading.Thread(target=sampler, daemon=True).start()
    if not ev["finished"].wait(7200):
        send("stop"); sys.exit("pregen did not finish")
    gen = time.time() - t0
    send("stop")
    t_stop = time.time()
    try:
        p.wait(3600)
    except subprocess.TimeoutExpired:
        p.kill(); p.wait()
    rec = {"stop_s": round(time.time() - t_stop, 1), "server": sys.argv[1], "radius": radius, "startup_s": round(startup, 1),
           "gen_wall_s": round(gen, 1), **result,
           "chunks_per_s": round(result.get("chunks", 0) / gen, 1),
           "cpu_cores_mean": round(sum(cpu) / len(cpu), 2) if cpu else None, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(ROOT / (os.environ.get("BENCH_RESULTS", "results") + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))
    if "--save-world-as" in sys.argv:
        dst = ROOT / "worlds" / sys.argv[sys.argv.index("--save-world-as") + 1]
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(sdir / "world", dst)

if __name__ == "__main__":
    main()
