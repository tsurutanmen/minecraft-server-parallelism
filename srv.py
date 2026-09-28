"""Start/stop a server with a fresh copy of a prepared world, send console commands, read its log."""
import re, shutil, subprocess, threading, time
from pathlib import Path

ROOT = Path(__file__).parent
JAVA = next((ROOT / "jdk").glob("jdk-25*")) / "bin" / "java.exe"


class Server:
    def __init__(self, name, world=None, heap="12G"):
        self.dir = ROOT / "servers" / name
        if world:
            shutil.rmtree(self.dir / "world", ignore_errors=True)
            shutil.copytree(ROOT / "worlds" / world, self.dir / "world")
        self.log = open(self.dir / "run.log", "w", encoding="utf-8")
        self.lines = []
        self.p = subprocess.Popen(
            [str(JAVA), f"-Xms{heap}", f"-Xmx{heap}", "-jar", "server.jar", "--nogui"],
            cwd=self.dir, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1)
        self.ready = threading.Event()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            self.log.write(line); self.log.flush(); self.lines.append(line)
            if "Done (" in line:
                self.ready.set()

    def send(self, cmd):
        self.p.stdin.write(cmd + "\n"); self.p.stdin.flush()

    def wait_ready(self, timeout=600):
        if not self.ready.wait(timeout):
            raise RuntimeError("server did not start")

    def wait_for(self, pattern, since=0, timeout=60):
        rx = re.compile(pattern); t = time.time()
        while time.time() - t < timeout:
            for ln in self.lines[since:]:
                if rx.search(ln): return ln
            time.sleep(0.2)
        return None

    def stop(self, timeout=1800):
        self.send("stop")
        try:
            self.p.wait(timeout)
        except subprocess.TimeoutExpired:
            self.p.kill(); self.p.wait()
