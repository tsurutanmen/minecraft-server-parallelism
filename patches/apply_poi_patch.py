"""Apply "remember empty POI searches" to a Paper or Folia source tree (after `applyPatches`).

usage: python apply_poi_patch.py <.../src/minecraft/java>

AcquirePoi anchors are matched by their text, and inserted code takes the anchor line's indentation,
so the same script works on Paper and Folia even though their AcquirePoi is indented differently.
Each file is skipped if it already contains the marker, so running it twice is harmless.
"""
import sys
import textwrap
from pathlib import Path

MARK = "remember empty POI searches"
root = Path(sys.argv[1]) / "net/minecraft/world/entity/ai"


def read(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


# --- PoiManager: count every POI change (same text and indentation in Paper and Folia) -----------
poi = root / "village/poi/PoiManager.java"
s = read(poi)
if MARK in s:
    print("already patched:", poi)
else:
    old = """    @Override
    public void setDirty(final long sectionPos) { // Paper - public
"""
    new = """    // Paper start - remember empty POI searches
    // Every POI add, remove, ticket acquire/release and refresh ends in setDirty, so this counter
    // changes whenever any search result could change.
    private final java.util.concurrent.atomic.AtomicLong changeCount = new java.util.concurrent.atomic.AtomicLong();

    public long getChangeCount() {
        return this.changeCount.get();
    }
    // Paper end - remember empty POI searches

    @Override
    public void setDirty(final long sectionPos) { // Paper - public
        this.changeCount.incrementAndGet(); // Paper - remember empty POI searches
"""
    assert s.count(old) == 1, "PoiManager.setDirty anchor"
    poi.write_text(s.replace(old, new), encoding="utf-8", newline="\n")
    print("patched:", poi)


# --- AcquirePoi: skip searches that are known to find nothing ------------------------------------
def insert_after(lines, anchor, block):
    hits = [i for i, l in enumerate(lines) if anchor in l]
    assert len(hits) == 1, f"anchor {anchor!r} found {len(hits)} times"
    i = hits[0]
    indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
    new = [(indent + l) if l.strip() else "" for l in textwrap.dedent(block).strip("\n").split("\n")]
    return lines[: i + 1] + new + lines[i + 1:]


acq = root / "behavior/AcquirePoi.java"
s = read(acq)
if MARK in s:
    print("already patched:", acq)
else:
    lines = s.split("\n")
    lines = insert_after(lines, "public static final int SCAN_RANGE = 48;", """
        private static final int EMPTY_SEARCH_SLACK = 8; // Paper - remember empty POI searches
    """)
    lines = insert_after(lines, "Long2ObjectMap<AcquirePoi.JitteredLinearRetry> batchCache = new Long2ObjectOpenHashMap<>();", """
        // Paper start - remember empty POI searches
        // [0] = POI change count at the time a search was proven empty, [1] = packed centre of that proof
        final long[] emptySearch = {Long.MIN_VALUE, 0L};
        // Paper end - remember empty POI searches
    """)
    lines = insert_after(lines, "batchCache.long2ObjectEntrySet().removeIf(entry -> !entry.getValue().isStillValid(timestamp));", """
        // Paper start - remember empty POI searches
        // A search was proven empty within SCAN_RANGE + EMPTY_SEARCH_SLACK of emptySearch's centre and no
        // POI changed since. The body is within the slack of that centre on every axis, so a search
        // of SCAN_RANGE around it finds nothing either: skip it, as vanilla would end the same way.
        final BlockPos searchCentre = body.blockPosition();
        final long poiChangeCount = poiManager.getChangeCount();
        if (emptySearch[0] == poiChangeCount) {
            final BlockPos provenCentre = BlockPos.of(emptySearch[1]);
            if (Math.abs(searchCentre.getX() - provenCentre.getX()) <= EMPTY_SEARCH_SLACK
                && Math.abs(searchCentre.getY() - provenCentre.getY()) <= EMPTY_SEARCH_SLACK
                && Math.abs(searchCentre.getZ() - provenCentre.getZ()) <= EMPTY_SEARCH_SLACK) {
                return true;
            }
        }
        // Paper end - remember empty POI searches
    """)
    lines = insert_after(lines, "PoiAccess.findNearestPoiPositions(poiManager, poiType, cacheTest, body.blockPosition(), SCAN_RANGE", """
        // Paper start - remember empty POI searches
        if (poiPositionsRaw.isEmpty()) {
            // cacheTest may have hidden some POIs, so prove emptiness without it, over the wider range.
            // cacheTest is never called when no POI passes the type and occupancy tests, so skipping
            // later searches cannot skip any retry bookkeeping either.
            final java.util.List<Pair<Holder<PoiType>, BlockPos>> proof = new java.util.ArrayList<>(1);
            ca.spottedleaf.moonrise.patches.poi_lookup.PoiAccess.findNearestPoiPositions(poiManager, poiType, null, searchCentre, SCAN_RANGE + EMPTY_SEARCH_SLACK, Double.MAX_VALUE, PoiManager.Occupancy.HAS_SPACE, ca.spottedleaf.moonrise.patches.poi_lookup.PoiAccess.LOAD_FOR_SEARCHING, 1, proof);
            if (proof.isEmpty()) {
                emptySearch[0] = poiChangeCount;
                emptySearch[1] = searchCentre.asLong();
            }
        }
        // Paper end - remember empty POI searches
    """)
    acq.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("patched:", acq)
