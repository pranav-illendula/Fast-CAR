# Fast-CAR: Cache Replacement Policy Simulator

This project reproduces and extends the FAST '04 **CAR (Clock with Adaptive
Replacement)** work with a Python cache simulator. It includes classic
baselines, CAR/CART, and implementations of **S3-FIFO** and **Clock2Q+**.
Experiments compare hit and miss ratios for synthetic Zipfian, scan-polluted,
and correlated-page workloads.

The Clock2Q+ implementation is based on:

> Yiyan Zhai et al., “Clock2Q+: A Simple and Efficient Replacement Algorithm
> for Metadata Cache in VMware vSAN,” PVLDB 19(12), 2026.
> [Paper DOI](https://doi.org/10.14778/3827998.3828002)

The repository also includes the original CAR paper, [`Fast - CAR.pdf`](./Fast%20-%20CAR.pdf).
The supplied Clock2Q+ PDF may be available locally as `3827998.3828002.pdf`;
the DOI above is the stable paper reference.

## 1. Clone the project

Install Git and Python 3.10 or later, then clone the repository:

```bash
git clone https://github.com/pranav-illendula/Fast-CAR.git
cd Fast-CAR
```

Run all commands below from the repository root (the directory containing
`run_simulation.py`).

## 2. Set up Python

Create and activate a virtual environment, then install the packages used by
the workload generators and plots.

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell prevents environment activation, run commands using the virtual
environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_simulation.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3. Project files and what they do

```text
Fast-CAR/
├── cache_simulator/               Cache policies and workload generators
│   ├── __init__.py                Public package imports and policy exports
│   ├── base.py                    Shared policy interface and hit/miss statistics
│   ├── lru.py                     Least Recently Used baseline
│   ├── clock.py                   Second-Chance CLOCK baseline
│   ├── arc.py                     Adaptive Replacement Cache baseline
│   ├── car.py                     CAR policy and adaptive target p telemetry
│   ├── cart.py                    CART policy with temporal filtering
│   ├── s3fifo.py                  S3-FIFO comparison policy
│   ├── clock2q.py                 Clock2Q+ research policy
│   └── workloads.py               Synthetic workloads and text trace reader
├── tests/
│   └── test_algorithms.py         Policy behavior and invariant tests
├── results/                       Output folder for generated plots
│   ├── hit_ratio_comparison.png   Hit-ratio comparison from the main runner
│   ├── adaptation_parameter_p.png CAR adaptive target p over virtual time
│   └── concurrency_throughput.png Threaded LRU/CAR throughput comparison
├── run_simulation.py              Runs all policy/workload comparisons
├── run_adaptation_analysis.py      Runs CAR adaptation experiment
├── run_concurrency_benchmark.py    Runs threaded LRU/CAR experiment
├── requirements.txt                External Python package dependencies
├── .gitignore                      Excludes environments, caches, and build files
├── README.md                       Setup, usage, and repository guide
├── PROJECT_TECHNICAL_REPORT.md     Detailed project technical report
├── Fast - CAR.pdf                  Original FAST '04 CAR paper
└── 3827998.3828002.pdf             Clock2Q+ PVLDB 2026 paper (if included)
```

The `results/` images are generated outputs. Run their corresponding scripts
to refresh them after changing workloads or policy implementations.

### Which Python files should I implement or modify?

If extending the research implementation, work primarily in these files:

1. **`cache_simulator/clock2q.py`** — implement or refine Clock2Q+: the Small
   FIFO, Main Clock, Ghost FIFO, and correlation-window behavior.
2. **`cache_simulator/s3fifo.py`** — implement or refine the S3-FIFO baseline
   used to compare against Clock2Q+.
3. **`cache_simulator/workloads.py`** — define the request traces to test,
   including the grouped, correlated-page bursts.
4. **`tests/test_algorithms.py`** — add correctness tests: expected promotions
   and evictions, ghost re-admission, queue bounds, capacity limits, and
   disjoint resident/ghost pages.
5. **`cache_simulator/__init__.py`** — export any new policy so it can be
   imported by the runner and other scripts.
6. **`run_simulation.py`** — include the policy in each comparison and decide
   which workloads and cache capacities to evaluate.

Existing policies and `cache_simulator/base.py` provide the interface to
follow: each policy implements `access(page_id)` and returns `True` on a hit
and `False` on a miss. Use `CachePolicy` for request, hit, and miss accounting.
Keep a new policy in its own module rather than mixing it into CAR or CART.

## 4. Run tests and experiments

### Unit tests

```bash
python -m unittest tests.test_algorithms -v
```

The suite checks the original policies and Clock2Q+/S3-FIFO behavior, including
cache-capacity and queue invariants over multiple cache sizes.

### Main policy comparison

```bash
python run_simulation.py
```

The runner evaluates **LRU, CLOCK, ARC, CAR, CART, S3-FIFO, and Clock2Q+** on:

- **Zipfian:** skewed access frequencies.
- **Scan-polluted:** a repeatedly accessed working set interrupted by one-time
  sequential scans.
- **Correlated references:** bursts visit multiple page IDs from the same
  configurable group, and may repeat each page within the burst.

The console reports `hit/miss (%)` for each policy and cache capacity. Hit and
miss ratios should sum to approximately 100%. The workload generators use
fixed seeds by default so runs are repeatable.

### Optional CAR experiments

```bash
python run_adaptation_analysis.py
python run_concurrency_benchmark.py
```

The first script plots CAR's adaptive target `p`; the second measures the
repository's threaded LRU/CAR benchmark. Treat the concurrency measurements as
a Python simulator demonstration, not as production-system performance data.

## 5. Results

`run_simulation.py` writes `results/hit_ratio_comparison.png` and prints the
numeric measurements. The other scripts write
`results/adaptation_parameter_p.png` and
`results/concurrency_throughput.png`, respectively. These output files can be
regenerated using the commands above.

Example measurements from the included **synthetic** workloads:

| Workload | Capacity | S3-FIFO hit rate | Clock2Q+ hit rate |
|---|---:|---:|---:|
| Zipfian | 32 | 96.84% | 96.78% |
| Scan-polluted | 128 | 43.62% | 43.10% |
| Correlated references | 512 | 72.63% | 71.75% |

These are results from this project's generated traces, not numbers reported
by the Clock2Q+ paper. Results depend on workload shape, seed, and capacity;
compare all policies on the same generated request stream before drawing
conclusions.

## 6. Scope and limitations

The simulator implements Clock2Q+'s core replacement behavior and compares it
with S3-FIFO and the existing policies. It does not reproduce VMware vSAN's
production implementation, real metadata traces, dirty-page-aware eviction,
fine-grained synchronization, or online cache resizing. Synthetic benchmark
results should not be presented as reproductions of the paper's measured
production or trace-based results.
