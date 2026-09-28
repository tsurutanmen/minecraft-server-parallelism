#!/bin/bash
# breakdown by kind of work (JFR on Paper) + clustered vs spread on all three servers, 4,800 villagers
cd "$(dirname "$0")"
until grep -q ALL_DONE run_folia_fix.log 2>/dev/null; do sleep 30; done
for rep in 1 2; do
  for sp in 1920 256; do
    for s in paper folia shredded; do
      python loadtest_jfr.py $s 16 2 6 --spacing $sp --tag _sp$sp --measure 120 --warmup 60 || echo "FAIL $s sp$sp rep$rep"
    done
  done
done
echo ALL_DONE
