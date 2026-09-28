#!/bin/bash
# worlds for the parity check + CPU usage per config, radius 512 blocks
cd "$(dirname "$0")"
export BENCH_RESULTS=parity
python bench.py vanilla 512 --save-world-as vanilla_A
python bench.py vanilla 512 --save-world-as vanilla_B
python bench.py c2me 512 --save-world-as c2me_A
python bench.py c2me-lux 512 --save-world-as c2me_lux_A
python bench.py c2me-ocl 512 --save-world-as ocl_A
python bench.py c2me-ocl 512 --save-world-as ocl_B
echo ALL_DONE
