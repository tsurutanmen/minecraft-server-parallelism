"""Break the main server thread's time into kinds of work, from a JFR recording.

usage: python analyze_jfr.py <recording.jfr> [--thread "Server thread"] [--top 12]

Every jdk.ExecutionSample on the given thread is assigned to one category by looking
at which method it is inside, checked from the outermost relevant frame inwards:
the callee of ServerLevel.tick decides the kind of work (entities, block entities,
scheduled block ticks, random ticks, chunk system, ...). Samples outside ServerLevel.tick
are labelled by their own top-level caller (network, player list, autosave, idle).

Then prints each category's share, and the Amdahl bound for splitting work by kind:
if each kind ran on its own core in parallel (with perfect synchronisation), a tick
could not get shorter than the largest single kind, so the speed-up is at most
1 / (largest share among the kinds that would be split off).
"""
import argparse, collections, json, shutil, subprocess, sys
from pathlib import Path

JFR = next((Path(__file__).parent / "jdk").glob("jdk-25*")) / "bin" / "jfr.exe"

# (substring in a frame's "Class.method", category), checked innermost-first within the tick subtree
RULES = [
    ("PathNavigation", "entities: pathfinding"),
    ("PathFinder", "entities: pathfinding"),
    ("Brain.tick", "entities: AI (brain)"),
    ("GoalSelector", "entities: AI (goals)"),
    ("Sensor", "entities: AI (sensors)"),
    ("pushEntities", "entities: pushing"),
    ("Entity.move", "entities: movement/collision"),
    ("travel", "entities: movement/collision"),
    ("tickNonPassenger", "entities: other"),
    ("EntityTickList", "entities: other"),
    ("tickBlockEntities", "block entities"),
    ("LevelTicks", "scheduled block/fluid ticks (redstone etc.)"),
    ("tickBlock", "scheduled block/fluid ticks (redstone etc.)"),
    ("tickFluid", "scheduled block/fluid ticks (redstone etc.)"),
    ("tickChunk", "random ticks, weather, spawning"),
    ("NaturalSpawner", "random ticks, weather, spawning"),
    ("ChunkMap", "chunk system / entity tracking"),
    ("ServerChunkCache", "chunk system / entity tracking"),
    ("moonrise", "chunk system / entity tracking"),
    ("Light", "lighting"),
    ("Raid", "raids/other world"),
    ("tickTime", "other world"),
]
OUTSIDE = [
    ("ServerConnectionListener", "network"),
    ("Connection", "network"),
    ("PacketListener", "network"),
    ("PlayerList", "players/list"),
    ("saveEverything", "autosave"),
    ("waitUntilNextTick", "idle (waiting for next tick)"),
    ("managedBlock", "idle (waiting for next tick)"),
    ("Thread.sleep", "idle (waiting for next tick)"),
    ("LockSupport.park", "idle (waiting for next tick)"),
]


def frames(ev):
    st = ev["values"]["stackTrace"]
    if not st: return []
    out = []
    for f in st["frames"]:  # innermost first
        m = f["method"]
        out.append(f'{m["type"]["name"].rsplit(".", 1)[-1]}.{m["name"]}' if m else "?")
    return out


def classify(fr):
    names = fr  # innermost first
    in_level_tick = any(n.endswith("ServerLevel.tick") for n in names)
    if in_level_tick:
        for sub, cat in RULES:
            if any(sub in n for n in names):
                return cat
        return "world tick: other"
    for sub, cat in OUTSIDE:
        if any(sub in n for n in names):
            return cat
    return "server: other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jfr"); ap.add_argument("--thread", default="Server thread"); ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()
    raw = subprocess.run([str(JFR), "print", "--json", "--events", "jdk.ExecutionSample", "--stack-depth", "96", a.jfr],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    evs = json.loads(raw)["recording"]["events"]
    evs = [e for e in evs if (e["values"].get("sampledThread") or {}).get("javaName") == a.thread]
    cnt = collections.Counter(classify(frames(e)) for e in evs)
    total = sum(cnt.values())
    busy = {k: v for k, v in cnt.items() if not k.startswith("idle")}
    busy_total = sum(busy.values())
    print(f"samples on '{a.thread}': {total}  (busy: {busy_total})")
    for k, v in cnt.most_common(a.top):
        print(f"  {v / total:6.1%}  of all  {v / max(busy_total, 1):6.1%} of busy   {k}")
    if busy_total:
        largest = max(busy.values()) / busy_total
        print(f"Amdahl bound for splitting by kind of work: at most {1 / largest:.2f}x "
              f"(largest single kind = {largest:.1%} of busy time)")


if __name__ == "__main__":
    main()
