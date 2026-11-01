"""Reusable simulation helpers for the interactive Streamlit dashboard."""
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from cache_simulator import (
    ARCCache,
    CARCache,
    CARTCache,
    Clock2QCache,
    ClockCache,
    LRUCache,
    S3FIFOCache,
)


POLICY_FACTORIES = {
    "LRU": LRUCache,
    "CLOCK": ClockCache,
    "ARC": ARCCache,
    "CAR": CARCache,
    "CART": CARTCache,
    "S3-FIFO": S3FIFOCache,
    "Clock2Q+": Clock2QCache,
}


def parse_trace_text(text: str, max_requests: Optional[int] = None) -> List[int]:
    """Parse one page ID per line or timestamp/page/size-style text traces."""
    if max_requests is not None and max_requests <= 0:
        raise ValueError("Maximum requests must be positive.")
    requests: List[int] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace(",", " ").split()
        page_field = parts[0] if len(parts) == 1 else parts[1]
        if not requests and page_field.casefold() in {
            "page",
            "page_id",
            "pageid",
            "block",
            "block_id",
            "lba",
        }:
            continue
        try:
            requests.append(int(page_field))
        except ValueError as error:
            raise ValueError(
                f"Line {line_number}: expected an integer page ID, got {page_field!r}."
            ) from error
        if max_requests is not None and len(requests) >= max_requests:
            break
    if not requests:
        raise ValueError("The trace contains no page requests.")
    return requests


def resident_pages(policy) -> set:
    if isinstance(policy, LRUCache):
        return set(policy._cache)
    if isinstance(policy, ClockCache):
        return set(policy._page_to_index)
    if isinstance(policy, (ARCCache, CARCache, CARTCache)):
        return set(policy.T1) | set(policy.T2)
    if isinstance(policy, (Clock2QCache, S3FIFOCache)):
        return set(policy.small) | set(policy.main)
    raise TypeError(f"Unsupported cache policy: {type(policy).__name__}")


def policy_state(policy) -> List[Dict[str, str]]:
    """Return visible queue state in policy order for the replay inspector."""
    rows: List[Dict[str, str]] = []

    def add(queue: str, pages: Iterable, describe) -> None:
        for position, (page, metadata) in enumerate(pages, start=1):
            rows.append(
                {
                    "Queue": queue,
                    "Position": str(position),
                    "Page ID": str(page),
                    "Policy metadata": describe(metadata),
                }
            )

    if isinstance(policy, LRUCache):
        add("LRU → MRU", policy._cache.items(), lambda _: "resident")
    elif isinstance(policy, ClockCache):
        pages = []
        for slot, page in enumerate(policy._slots):
            if page is not None:
                marker = "hand → " if slot == policy._hand else ""
                pages.append((page, f"{marker}ref={policy._bits[slot]}, slot={slot}"))
        add("CLOCK ring", pages, str)
    elif isinstance(policy, ARCCache):
        add("T1 · recency", policy.T1.items(), lambda _: "resident")
        add("T2 · frequency", policy.T2.items(), lambda _: "resident")
        add("B1 · ghost T1", policy.B1.items(), lambda _: "ID only")
        add("B2 · ghost T2", policy.B2.items(), lambda _: "ID only")
    elif isinstance(policy, CARCache):
        add("T1 · recency", policy.T1.items(), lambda bit: f"ref={bit}")
        add("T2 · frequency", policy.T2.items(), lambda bit: f"ref={bit}")
        add("B1 · ghost T1", policy.B1.items(), lambda _: "ID only")
        add("B2 · ghost T2", policy.B2.items(), lambda _: "ID only")
    elif isinstance(policy, CARTCache):
        add(
            "T1 · temporal filter",
            policy.T1.items(),
            lambda value: f"ref={value[0]}, filter={value[1]}",
        )
        add("T2 · frequency", policy.T2.items(), lambda value: f"ref={value[0]}")
        add("B1 · ghost T1", policy.B1.items(), lambda _: "ID only")
        add("B2 · ghost T2", policy.B2.items(), lambda _: "ID only")
    elif isinstance(policy, S3FIFOCache):
        add("Small FIFO", policy.small.items(), lambda count: f"frequency={count}")
        add("Main FIFO", policy.main.items(), lambda count: f"frequency={count}")
        add("Ghost FIFO", ((page, None) for page in policy.ghost), lambda _: "ID only")
    elif isinstance(policy, Clock2QCache):
        for position, (page, bit) in enumerate(policy.small.items(), start=1):
            in_window = page in policy._correlation_window
            rows.append(
                {
                    "Queue": "Small FIFO",
                    "Position": str(position),
                    "Page ID": str(page),
                    "Policy metadata": (
                        f"ref={bit}; correlation-window hit suppressed"
                        if in_window
                        else f"ref={bit}"
                    ),
                }
            )
        add("Main Clock", policy.main.items(), lambda bit: f"ref={bit}")
        add("Ghost FIFO", ((page, None) for page in policy.ghost), lambda _: "ID only")
        if policy._correlation_window:
            rows.append(
                {
                    "Queue": "Correlation window",
                    "Position": "—",
                    "Page ID": ", ".join(map(str, policy._correlation_window)),
                    "Policy metadata": "small entries whose hits are filtered",
                }
            )
    else:
        raise TypeError(f"Unsupported cache policy: {type(policy).__name__}")

    return rows


def policy_parameters(policy) -> List[str]:
    parameters: List[str] = []
    if hasattr(policy, "p"):
        parameters.append(f"p = {policy.p:.2f}")
    if hasattr(policy, "q"):
        parameters.append(f"q = {policy.q:.2f}")
    if hasattr(policy, "small_capacity"):
        parameters.append(f"Small = {policy.small_capacity}")
    if hasattr(policy, "main_capacity"):
        parameters.append(f"Main = {policy.main_capacity}")
    if hasattr(policy, "ghost_capacity"):
        parameters.append(f"Ghost limit = {policy.ghost_capacity}")
    if hasattr(policy, "correlation_window"):
        parameters.append(f"Correlation window = {policy.correlation_window}")
    return parameters


def replay_prefix(
    policy_name: str, requests: Sequence[int], capacity: int, request_count: int
) -> Tuple[object, Optional[Dict[str, object]]]:
    """Replay a trace prefix and return the final policy state and last event."""
    if policy_name not in POLICY_FACTORIES:
        raise ValueError(f"Unknown policy: {policy_name}")
    if request_count < 0 or request_count > len(requests):
        raise ValueError("Request count must be between zero and the trace length.")

    policy = POLICY_FACTORIES[policy_name](capacity)
    event = None
    for index, page_id in enumerate(requests[:request_count], start=1):
        before = resident_pages(policy)
        hit = policy.access(page_id)
        after = resident_pages(policy)
        if index == request_count:
            event = {
                "request_number": index,
                "page_id": page_id,
                "hit": hit,
                "evicted_pages": sorted(before - after, key=str),
                "resident_before": len(before),
                "resident_after": len(after),
            }
    return policy, event


def compare_policies(
    requests: Sequence[int], capacities: Sequence[int]
) -> List[Dict[str, object]]:
    """Measure all policies on identical requests at each selected capacity."""
    results: List[Dict[str, object]] = []
    for capacity in capacities:
        for name, factory in POLICY_FACTORIES.items():
            policy = factory(capacity)
            for page_id in requests:
                policy.access(page_id)
            results.append(
                {
                    "Policy": name,
                    "Capacity": capacity,
                    "Requests": policy.requests,
                    "Hits": policy.hits,
                    "Misses": policy.misses,
                    "Hit rate (%)": policy.hit_ratio,
                    "Miss rate (%)": policy.miss_ratio,
                    "Misses per 1,000": policy.misses * 1000 / max(1, policy.requests),
                }
            )
    return results


def hit_rate_timeline(
    requests: Sequence[int], capacity: int, sample_points: int = 250
) -> List[Dict[str, object]]:
    """Sample cumulative hit rates for every policy over a shared trace."""
    interval = max(1, len(requests) // max(1, sample_points))
    policies = {name: factory(capacity) for name, factory in POLICY_FACTORIES.items()}
    timeline: List[Dict[str, object]] = []
    for index, page_id in enumerate(requests, start=1):
        for policy in policies.values():
            policy.access(page_id)
        if index % interval == 0 or index == len(requests):
            for name, policy in policies.items():
                timeline.append(
                    {
                        "Requests processed": index,
                        "Policy": name,
                        "Cumulative hit rate (%)": policy.hit_ratio,
                    }
                )
    return timeline
