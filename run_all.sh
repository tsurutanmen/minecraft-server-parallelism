#!/bin/bash
# 4 configs x 3 reps, interleaved so drift (heat, background load) spreads evenly
cd "$(dirname "$0")"
for rep in 1 2 3; do
  for s in vanilla c2me c2me-lux c2me-ocl; do
    python bench.py $s 1024 || echo "FAIL $s rep$rep"
  done
done
echo ALL_DONE
