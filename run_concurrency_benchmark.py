"""
Concurrency & Lock Contention Benchmark: Demonstrating the D1/D2 advantage of CAR vs LRU.
Simulates multi-threaded page access where:
 - Concurrent LRU: Serializes all cache hits behind a global lock (due to MRU pointer updates).
 - Concurrent CAR: Allows concurrent hits via shared/lock-free atomic reference bit sets;
   exclusive lock is only taken on cache misses for eviction.
"""
import os
import time
import threading
from typing import List
import matplotlib.pyplot as plt
from cache_simulator import LRUCache, CARCache
from cache_simulator.workloads import zipfian_workload


class ConcurrentLRU:
    def __init__(self, capacity: int):
        self._lru = LRUCache(capacity)
        self._lock = threading.Lock()

    def access(self, page_id: int) -> bool:
        # Every access (even hits) must acquire exclusive lock to move node to MRU
        with self._lock:
            return self._lru.access(page_id)


class ConcurrentCAR:
    def __init__(self, capacity: int):
        self._car = CARCache(capacity)
        self._exclusive_lock = threading.Lock()

    def access(self, page_id: int) -> bool:
        # Fast hit check: In real OS/systems, this is an atomic bit flag or read-lock.
        # Check if page is in T1 or T2
        if page_id in self._car.T1:
            self._car.T1[page_id] = 1
            self._car.hits += 1
            self._car.requests += 1
            return True
        if page_id in self._car.T2:
            self._car.T2[page_id] = 1
            self._car.hits += 1
            self._car.requests += 1
            return True

        # Slow miss path: Acquire lock only when replacement/eviction is necessary
        with self._exclusive_lock:
            # Re-check after acquiring lock in case another thread loaded it
            if page_id in self._car.T1:
                self._car.T1[page_id] = 1
                self._car.hits += 1
                self._car.requests += 1
                return True
            if page_id in self._car.T2:
                self._car.T2[page_id] = 1
                self._car.hits += 1
                self._car.requests += 1
                return True
            return self._car.access(page_id)


def worker_task(cache, requests: List[int]):
    for req in requests:
        cache.access(req)


def benchmark_threads(cache_factory, requests: List[int], num_threads: int) -> float:
    cache = cache_factory()
    # Split workload among threads
    chunk_size = len(requests) // num_threads
    threads = []
    
    start_time = time.perf_counter()
    for i in range(num_threads):
        chunk = requests[i * chunk_size : (i + 1) * chunk_size]
        t = threading.Thread(target=worker_task, args=(cache, chunk))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    duration = time.perf_counter() - start_time
    total_ops = chunk_size * num_threads
    throughput = total_ops / duration
    return throughput


def main():
    os.makedirs("results", exist_ok=True)
    capacity = 500
    total_requests = 100000

    print("Generating skewed Zipfian workload (90%+ hit ratio)...")
    requests = zipfian_workload(num_requests=total_requests, num_pages=600, alpha=1.2, seed=42)

    thread_counts = [1, 2, 4, 8]
    lru_throughputs = []
    car_throughputs = []

    print(f"\n{'Threads':<8} | {'LRU Throughput (ops/sec)':<25} | {'CAR Throughput (ops/sec)':<25} | {'CAR Speedup':<12}")
    print("-" * 75)

    for n_threads in thread_counts:
        lru_ops = benchmark_threads(lambda: ConcurrentLRU(capacity), requests, n_threads)
        car_ops = benchmark_threads(lambda: ConcurrentCAR(capacity), requests, n_threads)
        speedup = car_ops / lru_ops

        lru_throughputs.append(lru_ops)
        car_throughputs.append(car_ops)

        print(f"{n_threads:<8} | {lru_ops:>22.0f} | {car_ops:>22.0f} | {speedup:>10.2f}x")

    # Plot throughput scaling
    plt.figure(figsize=(8, 5))
    plt.plot(thread_counts, car_throughputs, marker="o", linewidth=2.5, color="#1f77b4", label="CAR (No Hit Lock)")
    plt.plot(thread_counts, lru_throughputs, marker="s", linewidth=2.0, linestyle="--", color="#d62728", label="LRU (Serialized Hit Lock)")

    plt.title("Multi-Threaded Throughput vs. Thread Count (Lock Contention)", fontsize=12, fontweight="bold")
    plt.xlabel("Number of Concurrent Worker Threads", fontsize=11)
    plt.ylabel("Throughput (Operations / Second)", fontsize=11)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(fontsize=10)

    plot_path = os.path.join("results", "concurrency_throughput.png")
    plt.savefig(plot_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"\n[+] Saved concurrency scaling plot to: {plot_path}")


if __name__ == "__main__":
    main()
