#!/bin/bash
# patched Folia A (ownership cache) and B (A + remembered empty POI searches), clustered 256 blocks, 4,800 villagers
cd "$(dirname "$0")"
for rep in 1 2; do
  for s in foliaA foliaB; do
    python loadtest_jfr.py $s 16 2 6 --spacing 256 --tag _sp256 --measure 120 --warmup 60 || echo "FAIL $s rep$rep"
  done
done
python loadtest_jfr.py foliaB 16 2 6 --spacing 1920 --tag _sp1920 --measure 120 --warmup 60 || echo "FAIL foliaB spread"
echo ALL_DONE
