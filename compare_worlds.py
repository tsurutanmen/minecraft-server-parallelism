"""Compare two Minecraft worlds block by block (Anvil .mca, 1.18+ section format).

usage: python compare_worlds.py <world_a> <world_b> [--radius-chunks N]

Reports, over chunks that are fully generated ("minecraft:full") in both worlds:
  - the share of differing blocks
  - the same split by height band, so terrain (noise) vs surface/features can be told apart
  - the most frequent (a -> b) block substitutions
"""
import argparse, collections, io, struct, sys, zlib
from pathlib import Path


# --- minimal NBT reader -----------------------------------------------------

def _read_nbt(buf: io.BytesIO, tag: int):
    if tag == 1: return struct.unpack(">b", buf.read(1))[0]
    if tag == 2: return struct.unpack(">h", buf.read(2))[0]
    if tag == 3: return struct.unpack(">i", buf.read(4))[0]
    if tag == 4: return struct.unpack(">q", buf.read(8))[0]
    if tag == 5: return struct.unpack(">f", buf.read(4))[0]
    if tag == 6: return struct.unpack(">d", buf.read(8))[0]
    if tag == 7:
        n = struct.unpack(">i", buf.read(4))[0]; return buf.read(n)
    if tag == 8:
        n = struct.unpack(">H", buf.read(2))[0]; return buf.read(n).decode("utf-8", "replace")
    if tag == 9:
        t = buf.read(1)[0]; n = struct.unpack(">i", buf.read(4))[0]
        return [_read_nbt(buf, t) for _ in range(n)]
    if tag == 10:
        out = {}
        while True:
            t = buf.read(1)[0]
            if t == 0: return out
            n = struct.unpack(">H", buf.read(2))[0]
            name = buf.read(n).decode("utf-8", "replace")
            out[name] = _read_nbt(buf, t)
    if tag == 11:
        n = struct.unpack(">i", buf.read(4))[0]; return struct.unpack(f">{n}i", buf.read(4 * n))
    if tag == 12:
        n = struct.unpack(">i", buf.read(4))[0]; return struct.unpack(f">{n}q", buf.read(8 * n))
    raise ValueError(f"unknown NBT tag {tag}")


def read_nbt(data: bytes):
    buf = io.BytesIO(data)
    t = buf.read(1)[0]
    n = struct.unpack(">H", buf.read(2))[0]; buf.read(n)
    return _read_nbt(buf, t)


# --- region / chunk ----------------------------------------------------------

def iter_chunks(region_dir: Path):
    for mca in region_dir.glob("r.*.*.mca"):
        raw = mca.read_bytes()
        if len(raw) < 8192: continue
        for i in range(1024):
            off = int.from_bytes(raw[i * 4:i * 4 + 3], "big")
            if off == 0: continue
            start = off * 4096
            length = struct.unpack(">i", raw[start:start + 4])[0]
            comp = raw[start + 4]
            payload = raw[start + 5:start + 4 + length]
            if comp == 2: data = zlib.decompress(payload)
            elif comp == 1:
                import gzip; data = gzip.decompress(payload)
            elif comp == 3: data = payload
            else: continue  # external/other compression: skip
            nbt = read_nbt(data)
            yield (nbt["xPos"], nbt["zPos"]), nbt


def section_blocks(sec):
    """Return 4096 block names (index = y*256 + z*16 + x) for one section."""
    bs = sec.get("block_states")
    if not bs: return None
    palette = [p["Name"] for p in bs["palette"]]
    if len(palette) == 1 or "data" not in bs:
        return [palette[0]] * 4096
    bits = max(4, (len(palette) - 1).bit_length())
    per_long = 64 // bits
    mask = (1 << bits) - 1
    out = []
    for v in bs["data"]:
        v &= (1 << 64) - 1
        for k in range(per_long):
            out.append(palette[(v >> (k * bits)) & mask])
            if len(out) == 4096: return out
    return out


def chunk_columns(nbt):
    """dict section_y -> list of 4096 names, only for fully generated chunks."""
    if nbt.get("Status") not in ("minecraft:full", "full"): return None
    out = {}
    for sec in nbt.get("sections", []):
        b = section_blocks(sec)
        if b is not None: out[sec["Y"]] = b
    return out


def load_world(world: Path, radius: int):
    res = {}
    region = world / "dimensions" / "minecraft" / "overworld" / "region"
    if not region.is_dir():
        region = world / "region"  # pre-26.1 layout
    for (cx, cz), nbt in iter_chunks(region):
        if abs(cx) > radius or abs(cz) > radius: continue
        cols = chunk_columns(nbt)
        if cols is not None: res[(cx, cz)] = cols
    return res


FLUID = {"minecraft:water", "minecraft:lava", "minecraft:bubble_column"}
GROUND_WORDS = ("stone", "deepslate", "dirt", "grass_block", "sand", "gravel", "_ore", "granite",
                "diorite", "andesite", "tuff", "clay", "mud", "calcite", "podzol", "mycelium",
                "terracotta", "snow_block", "ice", "bedrock", "coarse_dirt", "rooted_dirt", "dripstone_block",
                "moss_block", "farmland", "dirt_path")


def skeleton(name):
    """Collapse a block into terrain shape: G(round), F(luid) or A(ir incl. plants, trees)."""
    if name in FLUID: return "F"
    if any(w in name for w in GROUND_WORDS) and "leaves" not in name and "_wall" not in name             and "_slab" not in name and "_stairs" not in name and "button" not in name:
        return "G"
    return "A"


BANDS = [(-64, -1, "y<0 (deepslate, caves, aquifers)"), (0, 55, "0..55"),
         (56, 79, "56..79 (surface around sea level)"), (80, 319, "80+ (mountains, trees)")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--radius-chunks", type=int, default=64)
    ap.add_argument("--terrain", action="store_true",
                    help="compare only terrain shape (ground / fluid / air), ignoring which block it is")
    args = ap.parse_args()
    A = load_world(Path(args.a), args.radius_chunks)
    B = load_world(Path(args.b), args.radius_chunks)
    common = sorted(set(A) & set(B))
    total = diff = 0
    band_tot = collections.Counter(); band_diff = collections.Counter()
    subs = collections.Counter()
    chunks_with_diff = 0
    for key in common:
        ca, cb = A[key], B[key]
        cdiff = 0
        for sy in set(ca) & set(cb):
            sa, sb = ca[sy], cb[sy]
            if args.terrain:
                sa = [skeleton(x) for x in sa]; sb = [skeleton(x) for x in sb]
            for i in range(4096):
                y = sy * 16 + i // 256
                band = next(n for lo, hi, n in BANDS if lo <= y <= hi)
                band_tot[band] += 1; total += 1
                if sa[i] != sb[i]:
                    diff += 1; cdiff += 1; band_diff[band] += 1
                    subs[(sa[i], sb[i])] += 1
        if cdiff: chunks_with_diff += 1
    print(f"chunks: A={len(A)} B={len(B)} compared={len(common)}  chunks with any difference={chunks_with_diff}")
    print(f"blocks compared={total:,}  differing={diff:,}  ({diff / max(total, 1):.6%})")
    for _, _, n in BANDS:
        t = band_tot[n]
        if t: print(f"  {n:40s} {band_diff[n] / t:.6%}  ({band_diff[n]:,}/{t:,})")
    print("top substitutions (A -> B):")
    for (a, b), c in subs.most_common(15):
        print(f"  {c:>10,}  {a} -> {b}")


if __name__ == "__main__":
    main()
