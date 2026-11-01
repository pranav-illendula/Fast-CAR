# Fast-CAR Project Technical Report

## 1. Problem Statement and Understanding

### 1.1 What problem does the project address?

Computer systems use caches to keep a limited set of data in fast memory.
Operating systems, databases, and storage systems commonly move data in
fixed-size units such as pages or blocks. When a requested page is already in
the cache, the system can serve it without fetching it again from a slower
storage tier. When the cache is full and a page not currently resident is
requested, the cache must choose a resident page to evict.

The eviction decision matters because it changes future cache hits and misses:

- A **cache hit** finds the requested page in memory and avoids a slower
  backing-store access.
- A **cache miss** does not find the page, so the system would need to fetch it
  and potentially evict another page.
- A **replacement policy** decides which resident page is least valuable to
  keep, based on the request history it can observe.

The central challenge is that future requests are unknown. A policy therefore
uses past accesses as evidence of future reuse. Policies that track only
recency can be harmed by scans; policies that track frequency can mistake a
short-lived burst for sustained popularity. More complex tracking can improve
decisions, but can also add metadata and work to the access path.

This project is a **trace-driven cache simulator** for studying that trade-off.
It models requests by page ID and compares policies under the same request
streams and cache capacities. It does not read or evict actual operating
system pages, manage a database buffer pool, or perform storage I/O.

### 1.2 Research papers and project progression

#### First paper: CAR

The foundation is **“CAR: Clock with Adaptive Replacement”** by Sorav Bansal
and Dharmendra S. Modha, published at the 3rd USENIX Conference on File and
Storage Technologies (FAST '04, 2004). The paper addresses how to combine
recency and frequency adaptation while avoiding the linked-list movement on
every cache hit that makes LRU/ARC-style implementations difficult to scale
under contention.

CAR uses four logical queues:

- **T1:** resident pages that have recently been seen (recency).
- **T2:** resident pages with evidence of repeated use (frequency).
- **B1 and B2:** ghost histories of pages evicted from T1 and T2. They retain
  page identifiers, not page contents.

CAR’s adaptive target `p` controls the desired balance between T1 and T2.
References set a bit rather than moving an entry on every hit. On a miss, the
replacement procedure scans the appropriate queue: a referenced entry receives
a second chance, while an unreferenced entry can be evicted to its ghost
history. A later ghost hit supplies feedback to adjust `p`.

The repository also implements **CART**, the temporal-filtering variant
described alongside CAR in the FAST '04 work. CART adds filter state intended
to avoid treating tightly clustered references as enough evidence of durable
popularity.

#### Second paper: Clock2Q+

The extension implemented in this project is **“Clock2Q+: A Simple and
Efficient Replacement Algorithm for Metadata Cache in VMware vSAN”** by Yiyan
Zhai et al., published in PVLDB 19(12), 2026. Its focus is a different but
related workload challenge: metadata pages can receive many references within
a short operation or traversal. Those correlated references may stop soon
after the burst, so treating them as evidence of lasting popularity can pollute
the cache.

The paper builds on a Small/Main/Ghost organization related to S3-FIFO. Its
key addition is a **correlation window** inside the Small FIFO:

- The Small FIFO is 10% of the cache and the Main Clock is 90%.
- The Ghost FIFO can retain identifiers for 50% of the cache.
- The correlation window is 50% of the Small FIFO, or 5% of the cache under
  the default split.
- A hit on a Small-FIFO entry still inside the correlation window does not
  set its reference bit.
- A hit after the entry has aged beyond the window sets the bit, allowing a
  genuinely reused page to be promoted to the Main Clock.
- A page found in the ghost history is re-admitted directly to the Main Clock.

The conceptual difference is important: **CAR adapts how much space is given
to recency versus frequency using ghost feedback; Clock2Q+ filters short-term
correlation before it can count as evidence for promotion.** Both use
history-based replacement and ghost information, but they respond to
different signals and target different access-pattern problems.

The project also implements **S3-FIFO** as a comparison baseline. S3-FIFO uses
Small, Main, and Ghost queues with bounded frequency counters. Compared with
Clock2Q+, it has no correlation-window gate: hits in the Small queue can
contribute to promotion even when clustered close to insertion. This makes
S3-FIFO a particularly relevant baseline for evaluating the change proposed
by Clock2Q+.

### 1.3 Project objective and questions

The project’s objective is to implement the core Clock2Q+ replacement
mechanism, compare it against CAR/CART and other baselines, and examine how
policy behavior changes across different synthetic request patterns.

The main experimental questions are:

1. How do hit and miss ratios change with cache capacity?
2. How do the policies compare on skewed, scan-polluted, and correlated-page
   requests?
3. Does suppressing promotion evidence during a short correlation window
   change behavior relative to S3-FIFO on the generated correlated workload?
4. Do the implementations preserve their queue and capacity invariants over
   long access sequences?

## 2. Technical Approach

### 2.1 Simulation model

The simulator consumes a sequence of page identifiers. Each policy receives
the same sequence independently at a chosen cache capacity. For each request,
the policy:

1. Checks whether the page is resident.
2. On a hit, updates policy metadata and increments the hit count.
3. On a miss, increments the miss count, decides what to evict if required,
   updates its ghost history if applicable, and admits the requested page.
4. Reports hit and miss ratios after all requests have been processed.

The base class in `cache_simulator/base.py` centralizes capacity validation
and hit/miss/request statistics. Each concrete policy implements
`access(page_id)` and returns `True` on a hit or `False` on a miss.

### 2.2 Policies compared

The main runner compares seven policies:

| Policy | Replacement idea | What it contributes to the comparison |
|---|---|---|
| LRU | Evict the least recently used page. | Familiar recency baseline. |
| CLOCK | Give referenced pages a second chance as a circular hand scans. | Low-metadata recency baseline. |
| ARC | Adapt between recency and frequency using resident and ghost lists. | Adaptive reference point for CAR. |
| CAR | Clock queues, ghost histories, and adaptive target `p`. | Main FAST '04 algorithm. |
| CART | CAR-family replacement with temporal filter state. | Tests filtering of temporally clustered access patterns. |
| S3-FIFO | Small/Main/Ghost FIFO queues and bounded frequency counters. | Baseline immediately related to Clock2Q+. |
| Clock2Q+ | Small/Main/Ghost queues with a correlation-window gate. | The newer research policy implemented in this project. |

#### CAR and CART implementation

`cache_simulator/car.py` stores T1/T2 and B1/B2 as ordered dictionaries.
Resident hits set a reference bit without moving the page to the tail. On a
miss, `_replace()` scans the selected queue and gives referenced pages a
second chance. Evictions enter B1 or B2. A B1 ghost hit raises `p`; a B2 ghost
hit lowers it. Optional `p_history` tracking supports the adaptation plot.

`cache_simulator/cart.py` extends the CAR-family bookkeeping with filter bits
and an additional target. It is included as a baseline for temporal filtering,
not as a substitute for the distinct Clock2Q+ queue structure.

#### S3-FIFO implementation

`cache_simulator/s3fifo.py` tracks each resident entry in either Small or
Main. Hits increment a bounded counter. During replacement, entries in Small
with reuse evidence can be promoted to Main; entries without that evidence are
recorded in Ghost. Main entries with remaining frequency are reinserted with
their counter reduced; an entry reaching zero can be evicted. A ghost
re-reference is admitted directly to Main.

#### Clock2Q+ implementation

`cache_simulator/clock2q.py` uses separate Small, Main, and Ghost queues, plus
a structure tracking which newly admitted Small entries remain inside the
correlation window. Queue capacities are derived from the configured cache
capacity:

```text
small_capacity       = max(1, floor(0.10 * capacity))
main_capacity        = capacity - small_capacity
ghost_capacity       = max(1, floor(0.50 * capacity))
correlation_window   = min(small_capacity, floor(0.05 * capacity))
```

The simulator represents queues using Python `OrderedDict` objects. A Small
hit only sets the reference bit after its page has left the correlation
window. When a Small entry reaches replacement, an entry with a reference bit
can move to Main; otherwise its ID is retained in Ghost. Main uses
second-chance reference-bit scanning. A request matching a Ghost entry is a
miss (the page is not resident) but causes direct admission to Main.

Small caches require integer queue sizes, so the implementation rounds the
paper’s percentages down and enforces a minimum queue size where applicable.
Consequently, very small capacities are useful for invariant testing but do
not reproduce the paper’s exact percentage split.

### 2.3 Workloads

`cache_simulator/workloads.py` supplies the input request streams:

- **Zipfian workload:** generates skewed references in which some page IDs are
  substantially more popular than others.
- **Scan-polluted workload:** repeatedly accesses a hot working set and
  periodically inserts one-time sequential pages.
- **Correlated workload:** groups page IDs into configurable ID ranges. Each
  burst selects several distinct IDs from one group and may repeat each
  selected ID. This is a synthetic model of related metadata references; it
  does not encode relationships derived from a real storage trace.
- **Loop and dynamic-adaptation workloads:** additional generators for cyclic
  access and CAR adaptation experiments.
- **Trace reader:** reads page IDs from a text trace, optionally using the
  second column for multi-column input.

The principal runner uses fixed random seeds, making the generated streams
repeatable. All replacement policies at a given workload and capacity process
the same request sequence.

### 2.4 Experimental procedure and interpretation

Run the unit tests first, then execute the comparative runner:

```bash
python -m unittest tests.test_algorithms -v
python run_simulation.py
```

`run_simulation.py` evaluates all seven policies across multiple capacities
for each workload. The console displays hit and miss percentages, and
`results/hit_ratio_comparison.png` plots hit ratios. The other scripts are
optional:

```bash
python run_adaptation_analysis.py
python run_concurrency_benchmark.py
```

The adaptation script writes `results/adaptation_parameter_p.png`. The
threaded LRU/CAR demonstration writes `results/concurrency_throughput.png`.
The threaded script models locking around Python policy operations; it is not
a native, lock-free implementation or a hardware performance benchmark.

Example measurements from the current deterministic synthetic workloads:

| Workload | Capacity | S3-FIFO hit ratio | Clock2Q+ hit ratio | Interpretation |
|---|---:|---:|---:|---|
| Zipfian | 32 | 96.84% | 96.78% | Both perform well on the generated skew. |
| Scan-polluted | 128 | 43.62% | 43.10% | These policies differ from the CAR/ARC-family leaders on this workload. |
| Correlated references | 512 | 72.63% | 71.75% | Clock2Q+ does not win on this particular synthetic trace. |

These are simulator measurements, not paper-reported results. The Clock2Q+
paper reports results on its evaluated metadata and data traces, including a
largest per-trace relative miss-ratio reduction over S3-FIFO; that result
cannot be inferred from this project's synthetic workload. The current
correlated generator is useful for controlled tests, but it does not
establish that the generated group layout, burst length, or locality matches
production metadata behavior.

### 2.5 Verification and invariants

`tests/test_algorithms.py` checks:

- Correct hit/miss return behavior for representative requests.
- Clock2Q+ reference-bit suppression inside the correlation window and
  promotion after a Small entry ages out of it.
- Ghost-hit re-admission to Main for Clock2Q+ and S3-FIFO.
- S3-FIFO promotion of reused Small entries and ghosting of cold entries.
- Resident capacity bounds, queue bounds where fixed by policy, disjoint
  resident and ghost IDs, and correlation-window membership.
- Correlated generator bursts contain multiple distinct related pages.

The test suite also retains coverage for the existing LRU, CLOCK, ARC, CAR,
CART, and scan-resistance behavior.

## 3. Technical Architecture

### 3.1 Component architecture

```text
                      +------------------------+
                      | run_simulation.py      |
                      | selects workloads,     |
                      | capacities, policies   |
                      +-----------+------------+
                                  |
                  +---------------+----------------+
                  |                                |
       +----------v-----------+       +------------v------------+
       | workloads.py         |       | CachePolicy interface   |
       | Zipfian / scan /     |       | capacity + metrics      |
       | correlated requests  |       +------------+------------+
       +----------+-----------+                    |
                  |                     +----------+-----------+
                  |                     |                      |
                  |              +------v------+        +------v------+
                  |              | CAR / CART  |        | S3-FIFO /   |
                  |              | ARC / LRU / |        | Clock2Q+ /  |
                  |              | CLOCK       |        | CLOCK       |
                  |              +------+-------+        +------+------+
                  |                     |                       |
                  +---------------------+-----------------------+
                                        |
                              +---------v----------+
                              | hit/miss statistics|
                              | console + plot     |
                              +--------------------+
```

### 3.2 Request path

The end-to-end execution flow is:

1. The runner creates a workload stream and selects a cache capacity.
2. It creates a fresh instance of each policy for that capacity.
3. It sends every page ID in the same stream to each policy in sequence.
4. Each policy checks its resident queues and updates its policy-specific
   state.
5. On a miss, the policy performs replacement and admission before the next
   request is processed.
6. The runner collects `hits`, `misses`, `hit_ratio`, and `miss_ratio`.
7. It prints a comparative table and writes a hit-ratio graph.

The result is a deterministic comparison of replacement decisions under a
controlled trace, subject to the generator seed and Python environment.

### 3.3 Repository modules

| Module | Responsibility |
|---|---|
| `cache_simulator/base.py` | Abstract policy interface, positive-capacity validation, request counters, hit/miss ratios. |
| `cache_simulator/lru.py` | LRU baseline. |
| `cache_simulator/clock.py` | Second-Chance CLOCK baseline. |
| `cache_simulator/arc.py` | ARC baseline. |
| `cache_simulator/car.py` | CAR resident/ghost queues, replacement, adaptive target, optional history telemetry. |
| `cache_simulator/cart.py` | CART filter-bit and adaptive queue implementation. |
| `cache_simulator/s3fifo.py` | Small/Main/Ghost FIFO baseline. |
| `cache_simulator/clock2q.py` | Clock2Q+ correlation-window policy. |
| `cache_simulator/workloads.py` | Synthetic workloads, trace input, and CAR adaptation workload. |
| `cache_simulator/__init__.py` | Public exports for policy classes. |
| `tests/test_algorithms.py` | Behavior and invariant tests. |
| `run_simulation.py` | Main comparative benchmark and hit-rate plot. |
| `run_adaptation_analysis.py` | CAR `p` history plot. |
| `run_concurrency_benchmark.py` | Python-threaded LRU/CAR comparison. |
| `results/` | Generated plots; regenerate them by running their corresponding scripts. |

### 3.4 How to extend the project

To add another replacement policy:

1. Add a module under `cache_simulator/` and subclass `CachePolicy`.
2. Implement `access(page_id)` with consistent hit/miss accounting.
3. Define and document the policy’s resident and ghost-state invariants.
4. Export the policy in `cache_simulator/__init__.py`.
5. Add deterministic behavior and invariant tests to
   `tests/test_algorithms.py`.
6. Add the policy to `run_simulation.py`, making sure all policies see the
   same stream for a given run.
7. Run tests and the experiment; report the workload, capacity, seed, and
   whether measurements are synthetic or trace-derived.

## 4. Conclusion

Fast-CAR provides an extensible environment for exploring cache page
replacement through controlled request traces. The first research foundation,
CAR (FAST '04), balances recency and frequency through clock-style queues,
ghost history, and an adaptive target. CART adds temporal filtering to that
family. The second research paper, Clock2Q+ (PVLDB 2026), addresses a more
specific metadata-cache issue: short-lived correlated hits should not
automatically count as evidence that a page is persistently popular.

The project implements Clock2Q+ as a separate policy, includes S3-FIFO as a
direct comparison baseline, expands the correlated workload to span groups of
related page IDs, and measures hit/miss ratios alongside LRU, CLOCK, ARC, CAR,
and CART. Its tests verify key admission, promotion, ghost, and capacity
properties. This gives the project a clear experimental progression from a
classic adaptive replacement policy to a newer correlation-aware design.

The current results demonstrate how to compare policies; they do not prove
that Clock2Q+ is universally superior. The simulator uses synthetic traces and
Python queue structures rather than the paper’s real metadata traces and
production vSAN implementation. A rigorous next step would be to use
representative, appropriately licensed page/block traces, run multiple seeds
and workload parameters, and report both absolute miss ratios and relative
changes against S3-FIFO. Any such evaluation should keep trace source,
configuration, and simulator limitations explicit.

### References

1. Sorav Bansal and Dharmendra S. Modha. “CAR: Clock with Adaptive
   Replacement.” Proceedings of the 3rd USENIX Conference on File and Storage
   Technologies (FAST '04), 2004. See the included `Fast - CAR.pdf`.
2. Yiyan Zhai et al. “Clock2Q+: A Simple and Efficient Replacement Algorithm
   for Metadata Cache in VMware vSAN.” Proceedings of the VLDB Endowment,
   19(12), 2026. [https://doi.org/10.14778/3827998.3828002](https://doi.org/10.14778/3827998.3828002)
