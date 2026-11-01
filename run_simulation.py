"""Compare classic, adaptive, and FIFO cache-replacement policies."""
import os
import matplotlib.pyplot as plt
import numpy as np
from cache_simulator import (
    LRUCache,
    ClockCache,
    ARCCache,
    CARCache,
    CARTCache,
    Clock2QCache,
    S3FIFOCache,
)
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
    results = {"cache_sizes": cache_sizes}
    policy_names = ["LRU", "CLOCK", "ARC", "CAR", "CART", "S3-FIFO", "Clock2Q+"]
    print(
        f"{'Cache Size':<12} | "
        + " | ".join(f"{name} hit/miss (%)" for name in policy_names)
    )
    print("-" * (16 + 23 * len(policy_names)))

    for c in cache_sizes:
        algorithms = [
            LRUCache(c),
            ClockCache(c),
            ARCCache(c),
            CARCache(c),
            CARTCache(c),
            S3FIFOCache(c),
            Clock2QCache(c),
        ]

        row = [f"{c:<12}"]
        for algo in algorithms:
            for page in requests:
                algo.access(page)
            hit_ratio = algo.hit_ratio
            miss_ratio = algo.miss_ratio
            results.setdefault(algo.name, []).append(hit_ratio)
            results.setdefault(f"{algo.name}_miss", []).append(miss_ratio)
            row.append(f"{hit_ratio:5.2f}/{miss_ratio:5.2f}")

        print(" | ".join(row))

    return results


def plot_results(all_results: dict, output_dir: str = "results"):
    os.makedirs(output_dir, exist_ok=True)
    num_workloads = len(all_results)
    fig, axes = plt.subplots(1, num_workloads, figsize=(6 * num_workloads, 5), squeeze=False)

    for idx, (wname, data) in enumerate(all_results.items()):
        ax = axes[0][idx]
        sizes = data["cache_sizes"]
        
        policies = [
            ("LRU", "o", "--", "#d62728"),
            ("CLOCK", "s", ":", "#ff7f0e"),
            ("ARC", "^", "-.", "#2ca02c"),
            ("CAR", "D", "-", "#1f77b4"),
            ("CART", "*", "-", "#9467bd"),
            ("S3-FIFO", "v", "--", "#8c564b"),
            ("Clock2Q+", "P", "-", "#17becf"),
        ]
        for name, marker, linestyle, color in policies:
            ax.plot(
                sizes,
                data[name],
                label=name,
                marker=marker,
                linestyle=linestyle,
                linewidth=2.2 if name in ("CAR", "Clock2Q+") else 1.6,
                color=color,
            )

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

    # 3. Correlated metadata workload (bursts span multiple related pages)
    corr_reqs = correlated_workload(
        num_requests=30000,
        num_pages=2000,
        burst_length=5,
        correlation_group_size=8,
        seed=789,
    )
    corr_sizes = [32, 64, 128, 256, 512]

    all_results = {}
    all_results["Zipfian (Database/Storage)"] = run_benchmark("Zipfian (Database/Storage)", zipf_reqs, zipf_sizes)
    all_results["Scan Vulnerability"] = run_benchmark("Scan Vulnerability", scan_reqs, scan_sizes)
    all_results["Correlated References"] = run_benchmark("Correlated References", corr_reqs, corr_sizes)

    plot_results(all_results)


if __name__ == "__main__":
    main()
