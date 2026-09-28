## 1. Chunk generation speed (radius 1024 blocks = 16,641 chunks, seed 20260927)

Runs interleaved as vanilla, c2me, c2me-lux, c2me-ocl, repeated 3 times.

| config | chunks/s per run | mean | x vanilla |
|---|---|---|---|
| vanilla | 23.4 / 23.2 / 21.8 | 22.8 | 1.0 |
| c2me | 136.4 / 355.4 / 331.4 | 274.4 | 12.0 |
| c2me-lux | 188.4 / 362.9 / 338.9 | 296.7 | 13.0 |
| c2me-ocl | 483.1 / 457.6 / 489.8 | 476.8 | 20.9 |

The first c2me run (and to a lesser extent c2me-lux) came right after vanilla's 6-7 minute save; treat it as an outlier. Excluding it, c2me = 343.4 chunks/s (15.1x).

## 2. CPU cores used during generation (radius 512 blocks = 4,225 chunks)

| config | chunks/s | mean cores busy (of 20 logical) |
|---|---|---|
| vanilla | 19.1 | 1.13 |
| vanilla | 19.1 | 1.14 |
| c2me | 241.7 | 11.58 |
| c2me-lux | 269.8 | 12.52 |
| c2me-ocl | 316.9 | 11.10 |
| c2me-ocl | 303.8 | 11.32 |

## 3. Does the GPU path produce the same terrain? (central 625 chunks = 61,440,000 blocks)

| pair | any block differs | terrain shape differs (ground/fluid/air) | shape, y 56..79 |
|---|---|---|---|
| vanilla vs vanilla (baseline) | 0.293027% | 0.007575% | 0.011224% |
| vanilla vs c2me | 0.399185% | 0.011616% | 0.044427% |
| vanilla vs c2me-ocl (GPU) | 0.448363% | 0.014551% | 0.071432% |
| c2me-ocl vs c2me-ocl | 0.396198% | 0.010763% | 0.025990% |

## 4. Mob pushing: CPU vs GPU (ms per tick, median)

| scenario | mobs | CPU 1 core | CPU all cores | GPU fp64 | GPU fp32 | fp32 max rel. error |
|---|---|---|---|---|---|---|
| farm | 50 | 0.0115 | 0.0753 | 1.08 | 0.737 | 3.5e-07 |
| farm | 100 | 0.0151 | 0.0305 | 0.826 | 0.734 | 4.3e-07 |
| farm | 200 | 0.0394 | 0.0563 | 1.28 | 1.38 | 7.7e-07 |
| farm | 400 | 0.24 | 0.086 | 5.29 | 1.2 | 7.1e-07 |
| farm | 800 | 1.01 | 0.214 | 4.06 | 0.981 | 6.7e-07 |
| farm | 1,600 | 4.2 | 0.742 | 6.51 | 1.18 | 8.1e-07 |
| dense | 1,000 | 0.247 | 0.105 | 0.984 | 0.743 | 1.8e-06 |
| dense | 4,000 | 1.2 | 0.396 | 1.23 | 0.925 | 4.6e-06 |
| dense | 16,000 | 5.3 | 1.92 | 1.77 | 1.07 | 8.6e-06 |
| dense | 64,000 | 28.1 | 8.54 | 4.62 | 1.89 | 0.11 |
| dense | 256,000 | 144 | 44.4 | 20.4 | 6.75 | 0.12 |
| spread | 1,000 | 0.0727 | 0.13 | 0.755 | 0.725 | 1.5e-06 |
| spread | 4,000 | 0.366 | 0.348 | 0.913 | 0.899 | 2.3e-05 |
| spread | 16,000 | 2.13 | 1.49 | 1.05 | 0.98 | 4.9e-05 |
| spread | 64,000 | 13.6 | 7.34 | 2.05 | 2.05 | 3.8e-05 |
| spread | 256,000 | 124 | 43.2 | 15.8 | 9.27 | 0.23 |

## 5. Pathfinding: per-mob A* vs one shared flow field (128x128 map, 25% walls, ms)

| mobs | A* CPU 1 core | A* CPU all cores | flow field CPU 1 core | flow field GPU | A* == BFS | GPU field == BFS |
|---|---|---|---|---|---|---|
| 10 | 0.153 | 0.194 | 0.161 | 2 | True | True |
| 100 | 1.62 | 1.18 | 0.161 | 2 | True | True |
| 1,000 | 18.5 | 8.7 | 0.161 | 2 | True | True |
| 10,000 | 188 | 76.9 | 0.161 | 2 | True | True |

## 6. Paper vs Folia vs ShreddedPaper, players spread out (16 groups 1,920 blocks apart, 32 bots)

TPS = server-reported (Folia: median region; others: 1-minute average). MSPT = 1-minute average (Folia: worst of the top-3 regions). Cores = CPU time of the server process / wall time.

| villagers | server | TPS per run | MSPT per run | cores per run |
|---|---|---|---|---|
| 1,600 | folia | 20.0 / 20.0 | 12.1 / 12.4 | 4.17 / 4.25 |
| 1,600 | paper | 12.2 / 12.9 | 81.7 / 77.6 | 1.29 / 1.33 |
| 1,600 | shredded | 20.0 / 20.0 | 21.2 / 21.6 | 3.58 / 3.76 |
| 4,800 | folia | 20.0 / 20.0 | 25.9 / 25.3 | 7.97 / 8.26 |
| 4,800 | paper | 4.1 / 3.9 | 244.6 / 253.1 | 1.33 / 1.31 |
| 4,800 | shredded | 20.0 / 20.0 | 39.6 / 42.3 | 6.99 / 7.46 |
| 9,600 | folia | 11.7 / 13.8 | 75.7 / 76.2 | 14.52 / 13.29 |
| 9,600 | paper | 2.1 / 2.0 | 475.4 / 494.9 | 1.34 / 1.30 |
| 9,600 | shredded | 11.7 / 12.0 | 85.6 / 83.5 | 9.35 / 9.32 |

Method check (villagers spawned one /summon at a time instead of via a datapack function, 4,800 villagers): 
- paper: TPS 3.7, MSPT 273.8, cores 1.27
- shredded: TPS 18.8, MSPT 51.7, cores 7.44

## 7. Spread out vs clustered (4,800 villagers, 16 groups, 32 bots)

| spacing | server | TPS per run | MSPT per run | cores per run | Folia regions |
|---|---|---|---|---|---|
| 1920 | folia | 20.00 / 20.00 | 25.9 / 25.1 | 9.35 / 8.71 | [16, 16] |
| 1920 | paper | 2.90 / 3.30 | 348.4 / 307.2 | 1.43 / 1.37 | - |
| 1920 | shredded | 19.30 / 20.00 | 51.9 / 42.6 | 8.62 / 7.68 | - |
| 256 | folia | 0.24 / 0.26 | 4110.1 / 3726.7 | 1.23 / 1.19 | [1, 1] |
| 256 | paper | 2.50 / 3.60 | 407.3 / 280.7 | 1.35 / 1.34 | - |
| 256 | shredded | 17.30 / 17.70 | 57.9 / 56.5 | 5.29 / 5.32 | - |

## 8. Where Paper's main thread spends its time (JFR, 4,800 villagers)

### paper_g16_k6_sp1920_105916
```
samples on 'Server thread': 10771  (busy: 10771)
   68.1%  of all   68.1% of busy   entities: AI (brain)
   11.6%  of all   11.6% of busy   entities: other
    4.9%  of all    4.9% of busy   entities: pushing
    4.4%  of all    4.4% of busy   entities: movement/collision
    3.4%  of all    3.4% of busy   random ticks, weather, spawning
    2.0%  of all    2.0% of busy   chunk system / entity tracking
    1.9%  of all    1.9% of busy   entities: pathfinding
    1.4%  of all    1.4% of busy   network
    1.2%  of all    1.2% of busy   entities: AI (goals)
    0.6%  of all    0.6% of busy   scheduled block/fluid ticks (redstone etc.)
    0.2%  of all    0.2% of busy   block entities
    0.1%  of all    0.1% of busy   server: other
    0.1%  of all    0.1% of busy   world tick: other
    0.0%  of all    0.0% of busy   other world
Amdahl bound for splitting by kind of work: at most 1.47x (largest single kind = 68.1% of busy time)
```
### paper_g16_k6_sp1920_113922
```
samples on 'Server thread': 10848  (busy: 10848)
   69.6%  of all   69.6% of busy   entities: AI (brain)
   10.8%  of all   10.8% of busy   entities: other
    4.9%  of all    4.9% of busy   entities: pushing
    4.3%  of all    4.3% of busy   entities: movement/collision
    3.4%  of all    3.4% of busy   random ticks, weather, spawning
    2.0%  of all    2.0% of busy   chunk system / entity tracking
    1.7%  of all    1.7% of busy   entities: pathfinding
    1.5%  of all    1.5% of busy   network
    1.3%  of all    1.3% of busy   entities: AI (goals)
    0.4%  of all    0.4% of busy   scheduled block/fluid ticks (redstone etc.)
    0.1%  of all    0.1% of busy   block entities
    0.1%  of all    0.1% of busy   world tick: other
    0.1%  of all    0.1% of busy   server: other
Amdahl bound for splitting by kind of work: at most 1.44x (largest single kind = 69.6% of busy time)
```
### paper_g16_k6_sp256_112015
```
samples on 'Server thread': 10908  (busy: 10908)
   65.9%  of all   65.9% of busy   entities: AI (brain)
   12.6%  of all   12.6% of busy   entities: other
    5.5%  of all    5.5% of busy   entities: pushing
    4.7%  of all    4.7% of busy   entities: movement/collision
    4.1%  of all    4.1% of busy   entities: pathfinding
    2.6%  of all    2.6% of busy   random ticks, weather, spawning
    1.8%  of all    1.8% of busy   chunk system / entity tracking
    1.3%  of all    1.3% of busy   network
    1.1%  of all    1.1% of busy   entities: AI (goals)
    0.2%  of all    0.2% of busy   scheduled block/fluid ticks (redstone etc.)
    0.1%  of all    0.1% of busy   block entities
    0.1%  of all    0.1% of busy   server: other
    0.0%  of all    0.0% of busy   world tick: other
Amdahl bound for splitting by kind of work: at most 1.52x (largest single kind = 65.9% of busy time)
```
### paper_g16_k6_sp256_115941
```
samples on 'Server thread': 10865  (busy: 10865)
   67.7%  of all   67.7% of busy   entities: AI (brain)
   11.2%  of all   11.2% of busy   entities: other
    4.7%  of all    4.7% of busy   entities: pushing
    4.4%  of all    4.4% of busy   entities: movement/collision
    4.0%  of all    4.0% of busy   entities: pathfinding
    3.3%  of all    3.3% of busy   random ticks, weather, spawning
    2.2%  of all    2.2% of busy   chunk system / entity tracking
    1.2%  of all    1.2% of busy   entities: AI (goals)
    0.8%  of all    0.8% of busy   network
    0.3%  of all    0.3% of busy   scheduled block/fluid ticks (redstone etc.)
    0.1%  of all    0.1% of busy   block entities
    0.1%  of all    0.1% of busy   server: other
    0.0%  of all    0.0% of busy   world tick: other
    0.0%  of all    0.0% of busy   raids/other world
Amdahl bound for splitting by kind of work: at most 1.48x (largest single kind = 67.7% of busy time)
```
