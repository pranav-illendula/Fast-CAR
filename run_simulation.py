"""
Comparative simulation runner replicating Table II, Table III, and Figures 4 & 5
from FAST '04 CAR paper.
"""
import os
import matplotlib.pyplot as plt
import numpy as np
from cache_simulator import LRUCache, ClockCache, ARCCache, CARCache, CARTCache
from cache_simulator.workloads import (
    zipfian_workload,
    scan_workload,
    loop_workload,
    correlated_workload,
)


def run_benchmark(workload_name: str, requests: list, cache_sizes: list):
    print(f"\n========================================================")
    print(f" Workload: {workload_name} ({len(requests)} requests, {len(set(requests))} unique pages)")
    print(f"========================================================")
    print(f"{'Cache Size':<12} | {'LRU (%)':<10} | {'CLOCK (%)':<10} | {'ARC (%)':<10} | {'CAR (%)':<10} | {'CART (%)':<10}")
    print("-" * 72)

    results = {
        "cache_sizes": cache_sizes,
        "LRU": [],
        "CLOCK": [],
        "ARC": [],
        "CAR": [],
        "CART": []
    }

    for c in cache_sizes:
        algorithms = [
            LRUCache(c),
            ClockCache(c),
            ARCCache(c),
            CARCache(c),
            CARTCache(c)
        ]

        row = [f"{c:<12}"]
        for algo in algorithms:
            for page in requests:
                algo.access(page)
            hr = algo.hit_ratio
            results[algo.name].append(hr)
            row.append(f"{hr:>8.2f}%")

        print(" | ".join(row))

    return results


def plot_results(all_results: dict, output_dir: str = "results"):
    os.makedirs(output_dir, exist_ok=True)
    num_workloads = len(all_results)
    fig, axes = plt.subplots(1, num_workloads, figsize=(6 * num_workloads, 5), squeeze=False)

    for idx, (wname, data) in enumerate(all_results.items()):
        ax = axes[0][idx]
        sizes = data["cache_sizes"]
        
        ax.plot(sizes, data["LRU"], label="LRU", marker="o", linestyle="--", color="#d62728")
        ax.plot(sizes, data["CLOCK"], label="CLOCK", marker="s", linestyle=":", color="#ff7f0e")
        ax.plot(sizes, data["ARC"], label="ARC", marker="^", linestyle="-.", color="#2ca02c")
        ax.plot(sizes, data["CAR"], label="CAR (Paper)", marker="D", linewidth=2.5, color="#1f77b4")
        ax.plot(sizes, data["CART"], label="CART (Paper)", marker="*", linewidth=2.0, color="#9467bd")

        ax.set_title(f"Workload: {wname}", fontsize=12, fontweight="bold")
        ax.set_xlabel("Cache Size (pages)", fontsize=10)
        ax.set_ylabel("Hit Ratio (%)", fontsize=10)
        ax.set_xscale("log", base=2)
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(fontsize=9)

    plt.tight_layout()
    plot_path = os.path.join(output_dir, "hit_ratio_comparison.png")
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"\n[+] Saved comparative plot to: {plot_path}")


def main():
    os.makedirs("results", exist_ok=True)

    # 1. Skewed / Zipfian distribution (Representative of SPC1 / Database traces)
    zipf_reqs = zipfian_workload(num_requests=30000, num_pages=2000, alpha=0.9, seed=123)
    zipf_sizes = [32, 64, 128, 256, 512, 1024]

    # 2. Scan-polluted workload (Repetitive working set + one-time sequential bursts)
    scan_reqs = scan_workload(working_set_size=128, scan_size=600, cycles=15, seed=456)
    scan_sizes = [32, 64, 128, 256, 512]

    # 3. Correlated references workload (Bursty clustered requests)
    corr_reqs = correlated_workload(num_requests=30000, num_pages=2000, burst_length=5, seed=789)
    corr_sizes = [32, 64, 128, 256, 512]

    all_results = {}
    all_results["Zipfian (Database/Storage)"] = run_benchmark("Zipfian (Database/Storage)", zipf_reqs, zipf_sizes)
    all_results["Scan Vulnerability"] = run_benchmark("Scan Vulnerability", scan_reqs, scan_sizes)
    all_results["Correlated References"] = run_benchmark("Correlated References", corr_reqs, corr_sizes)

    plot_results(all_results)


if __name__ == "__main__":
    main()
