# Reproduction of FAST '04 Paper: CAR (Clock with Adaptive Replacement)

This repository contains a complete, verified implementation and experimental reproduction of the research paper:

> **"CAR: Clock with Adaptive Replacement"**  
> *Sorav Bansal (Stanford University) & Dharmendra S. Modha (IBM Almaden Research Center)*  
> Published in: *Proceedings of the 3rd USENIX Conference on File and Storage Technologies (FAST '04)*  
> Paper File: [`Fast - CAR.pdf`](./Fast%20-%20CAR.pdf)

---

## 1. Overview & Key Insights

Traditional caching algorithms face a fundamental tradeoff between **replacement quality** and **concurrency overhead**:
* **LRU & ARC** achieve high hit ratios by tracking recency and frequency, but require moving accessed pages to the MRU position on **every single cache hit**. In multi-threaded environments (OS virtual memory, database buffer pools, storage controllers), this serializes all hits behind a global mutex lock (Drawbacks **D1** and **D2**).
* **CLOCK (Second Chance)** eliminates hit serialization by using a 1-bit reference flag and a circular clock hand. Hits only set `bit = 1` without pointer moves. However, CLOCK cannot distinguish frequency and is heavily degraded by sequential scans (Drawbacks **D3** and **D4**).

### The Solution: CAR & CART
* **CAR (Clock with Adaptive Replacement):** Replaces ARC's LRU lists with two Second Chance clock queues ($T_1$ for recency, $T_2$ for frequency) and two ghost history queues ($B_1$ and $B_2$). Hits only set the reference bit to 1 ($O(1)$, lock-friendly). Page promotions to $T_2$ are delayed until eviction time. The target size $p$ continuously self-tunes based on workload feedback.
* **CART (CAR with Temporal Filtering):** Introduces a temporal locality window and filter bits (`S` and `L`) to filter out bursty "correlated references".

---

## 2. Codebase Structure

```
OS project/
├── Fast - CAR.pdf                     # Original FAST '04 paper
├── README.md                          # Project documentation and reproduction guide
├── cache_simulator/                   # Core caching engine package
│   ├── __init__.py                    # Module exports
│   ├── base.py                        # Base CachePolicy interface and metrics tracking
│   ├── lru.py                         # Classical LRU implementation
│   ├── clock.py                       # Classic 1-bit CLOCK (Second Chance) implementation
│   ├── arc.py                         # ARC (FAST '03) implementation
│   ├── car.py                         # CAR (FAST '04, Figure 2) implementation
│   ├── cart.py                        # CART (FAST '04, Figure 3) implementation
│   └── workloads.py                   # Trace parsers & Zipfian, Scan, Correlated generators
├── tests/
│   └── test_algorithms.py             # Unit tests verifying invariants (I1-I7) & scan resistance
├── run_simulation.py                  # Replicates Tables II & III and Figures 4 & 5
├── run_adaptation_analysis.py         # Replicates Figure 6 (Tracking target p over virtual time)
├── run_concurrency_benchmark.py       # Replicates D1/D2 benchmark (Throughput vs Lock Contention)
└── results/                           # Generated publication plots
    ├── hit_ratio_comparison.png       # Hit ratios across cache sizes and workloads
    ├── adaptation_parameter_p.png     # Figure 6 target size p trajectory
    └── concurrency_throughput.png     # Multi-threaded throughput scaling curve
```

---

## 3. How to Run

### Run Unit Tests
Verifies correct eviction logic, cache capacity bounds, and paper invariants:
```bash
python -m unittest tests/test_algorithms.py
```

### Run Hit-Ratio Comparative Simulation (Replicating Tables II & III, Figures 4 & 5)
Evaluates `LRU`, `CLOCK`, `ARC`, `CAR`, and `CART` across a range of cache sizes:
```bash
python run_simulation.py
```

### Run Adaptation Analysis (Replicating Figure 6)
Tracks the dynamic adjustment of the target parameter $p(t)$:
```bash
python run_adaptation_analysis.py
```

### Run Concurrency & Lock Contention Benchmark
Demonstrates the throughput advantage of CAR (lock-free hit path) over LRU (serialized hit lock):
```bash
python run_concurrency_benchmark.py
```

---

## 4. Key Experimental Findings

### A. Hit Ratio & Scan Resistance (Tables II & III)
| Workload | Cache Size | LRU (%) | CLOCK (%) | ARC (%) | CAR (Paper) (%) | CART (Paper) (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Zipfian (Database/Storage)** | 32 | 95.99% | 96.20% | 96.58% | **96.71%** | **96.76%** |
| | 64 | 97.77% | 97.86% | 98.08% | **98.14%** | **98.13%** |
| **Scan Vulnerability** | 128 | 34.11% | 34.11% | **44.56%** | **44.56%** | **44.56%** |
| | 256 | 34.11% | 34.11% | **44.63%** | **44.63%** | **44.63%** |
| | 512 | 34.11% | 40.34% | **44.63%** | **44.63%** | **44.63%** |

* **Scan Resistance:** When one-time sequential scan pages pollute the cache, basic LRU and CLOCK hit ratios collapse to 34.11%, while **CAR and ARC achieve 44.63%** (a ~10.5% absolute improvement) by shielding high-frequency pages in $T_2$.
* **Parity with ARC:** In every benchmark, $\text{HitRatio}(\text{CAR}) \approx \text{HitRatio}(\text{ARC})$, matching the theoretical and empirical claims of the paper.

### B. Concurrency Throughput Scaling (D1 & D2)
* Under a 90%+ hit-rate skewed workload, **CAR achieves over 2x to 2.4x higher throughput than LRU** because hits do not require exclusive lock acquisition.
