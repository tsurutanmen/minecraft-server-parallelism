#!/bin/bash
# 3 servers x 3 villager loads x 2 reps, interleaved; 16 groups 1920 blocks apart, 2 bots each
cd "$(dirname "$0")"
for rep in 1 2; do
  for k in 2 6 12; do
    for s in paper folia shredded; do
      python loadtest.py $s 16 2 $k --measure 120 --warmup 60 || echo "FAIL $s k=$k rep$rep"
    done
  done
done
echo ALL_DONE
