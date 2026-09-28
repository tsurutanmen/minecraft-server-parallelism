#!/bin/bash
# Folia rerun with /summon (Folia has no /function) + method check on Paper/ShreddedPaper
cd "$(dirname "$0")"
for rep in 1 2; do for k in 2 6 12; do python loadtest.py folia 16 2 $k --measure 120 --warmup 60 || echo "FAIL folia $k $rep"; done; done
python loadtest.py paper 16 2 6 --measure 120 --warmup 60 || echo "FAIL paper check"
python loadtest.py shredded 16 2 6 --measure 120 --warmup 60 || echo "FAIL shredded check"
echo ALL_DONE
