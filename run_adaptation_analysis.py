"""
Script to reproduce Figure 6 from FAST '04:
Tracking the CAR adaptation parameter p (target size for T1) over virtual time.
"""
import os
import matplotlib.pyplot as plt
from cache_simulator import CARCache
from cache_simulator.workloads import dynamic_adaptation_workload


def main():
    os.makedirs("results", exist_ok=True)
    cache_size = 1000

    print(f"Generating dynamic workload with cache size c = {cache_size}...")
    workload = dynamic_adaptation_workload(cache_size, seed=42)
    print(f"Total virtual requests: {len(workload)}")

    car = CARCache(capacity=cache_size, track_p_history=True)

    for req in workload:
        car.access(req)

    print(f"Simulation finished. Hit ratio: {car.hit_ratio:.2f}%")

    # Extract time series of p
    times = [entry[0] for entry in car.p_history]
    p_values = [entry[1] for entry in car.p_history]

    # Subsample if large for crisp plotting
    step = max(1, len(times) // 2000)
    times_sub = times[::step]
    p_sub = p_values[::step]

    plt.figure(figsize=(10, 5))
    plt.plot(times_sub, p_sub, color="#1f77b4", linewidth=1.5, label="Target Size p (for T1)")
    plt.axhline(y=cache_size, color="r", linestyle="--", alpha=0.5, label="Max (p = c: All Recency)")
    plt.axhline(y=0, color="g", linestyle="--", alpha=0.5, label="Min (p = 0: All Frequency)")

    plt.title(f"CAR Adaptation Parameter p vs. Virtual Time (Replicating Fig. 6, c={cache_size})", fontsize=12, fontweight="bold")
    plt.xlabel("Virtual Time (Request Number)", fontsize=11)
    plt.ylabel("Target Size for List T1 (p)", fontsize=11)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper right", fontsize=10)

    plot_path = os.path.join("results", "adaptation_parameter_p.png")
    plt.savefig(plot_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"[+] Saved Figure 6 adaptation plot to: {plot_path}")


if __name__ == "__main__":
    main()
