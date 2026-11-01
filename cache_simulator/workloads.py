"""
Synthetic Workload Generators & Trace Readers for Cache Replacement Evaluation.
"""
import random
from typing import Iterator, List, Optional
import numpy as np


def zipfian_workload(num_requests: int, num_pages: int, alpha: float = 0.85, seed: int = 42) -> List[int]:
    """
    Generate a Zipfian (power-law) distribution of page accesses.
    Typical in database & storage controller workloads (e.g. SPC1).
    alpha: skew parameter (>0). Higher alpha = more skewed toward hot pages.
    """
    rng = np.random.default_rng(seed)
    # Generate Zipfian samples
    samples = rng.zipf(alpha + 1.0, size=num_requests)
    # Clamp to [1, num_pages]
    return [int(((s - 1) % num_pages) + 1) for s in samples]


def scan_workload(working_set_size: int = 100, scan_size: int = 500, cycles: int = 10, seed: int = 42) -> List[int]:
    """
    Simulates a repetitive hot working set periodically polluted by long sequential scans.
    """
    rng = random.Random(seed)
    stream: List[int] = []
    scan_offset = 10000

    for _ in range(cycles):
        # Hot working set access (repetitive)
        for _ in range(500):
            stream.append(rng.randint(1, working_set_size))

        # Scan sequence of one-time pages
        for i in range(scan_size):
            stream.append(scan_offset + i)
        scan_offset += scan_size

    return stream


def loop_workload(loop_size: int, cycles: int = 5) -> List[int]:
    """
    Generates a cyclical loop of pages: 1, 2, ..., loop_size repeated 'cycles' times.
    """
    return [p for _ in range(cycles) for p in range(1, loop_size + 1)]


def correlated_workload(
    num_requests: int = 20000,
    num_pages: int = 1000,
    burst_length: int = 4,
    burst_prob: float = 0.4,
    seed: int = 42,
    correlation_group_size: int = 8,
) -> List[int]:
    """
    Generate bursts that touch several related pages, with repeated references
    to each page in a burst. Consecutive page-ID groups model co-resident
    metadata pages accessed together.
    """
    if num_requests < 0:
        raise ValueError("num_requests must be non-negative")
    if num_pages < 2:
        raise ValueError("num_pages must be at least 2")
    if burst_length < 2:
        raise ValueError("burst_length must be at least 2")
    if not 0.0 <= burst_prob <= 1.0:
        raise ValueError("burst_prob must be between 0 and 1")
    if correlation_group_size < 2:
        raise ValueError("correlation_group_size must be at least 2")

    rng = random.Random(seed)
    stream: List[int] = []
    groups = [
        list(range(start, min(start + correlation_group_size, num_pages + 1)))
        for start in range(1, num_pages + 1, correlation_group_size)
    ]
    groups = [group for group in groups if len(group) >= 2]

    while len(stream) < num_requests:
        if rng.random() < burst_prob:
            group = rng.choice(groups)
            page_count = rng.randint(2, min(burst_length, len(group)))
            for page in rng.sample(group, page_count):
                stream.extend([page] * rng.randint(2, burst_length))
        else:
            stream.append(rng.randint(1, num_pages))
    return stream[:num_requests]


def dynamic_adaptation_workload(c: int, seed: int = 42) -> List[int]:
    """
    Workload designed to test and reproduce Figure 6:
    Alternates between a recency-dominated phase and a frequency-dominated phase
    to observe the oscillation of the target size parameter p.
    """
    rng = random.Random(seed)
    stream: List[int] = []

    # Phase 1: High recency - sliding window
    for start in range(0, 3 * c, 2):
        stream.extend([start + rng.randint(0, c // 2) for _ in range(20)])

    # Phase 2: High frequency - small fixed hot set
    hot_set = list(range(1, c // 2))
    for _ in range(5 * c):
        stream.append(rng.choice(hot_set))

    # Phase 3: Recency scan
    stream.extend(list(range(10000, 10000 + 4 * c)))

    # Phase 4: Frequency re-access
    for _ in range(5 * c):
        stream.append(rng.choice(hot_set))

    return stream


def read_trace_file(filepath: str, max_requests: Optional[int] = None) -> List[int]:
    """
    Reads a trace file containing one page_id per line or comma/space-separated fields.
    """
    stream = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace(",", " ").split()
            # If line has multiple columns (e.g. timestamp, block, size), take the block ID
            page_id = int(parts[0]) if len(parts) == 1 else int(parts[1])
            stream.append(page_id)
            if max_requests and len(stream) >= max_requests:
                break
    return stream
