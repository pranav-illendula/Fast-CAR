"""
Base interface and metrics tracking for Cache Replacement Algorithms.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class CachePolicy(ABC):
    def __init__(self, capacity: int, name: str = "BaseCache"):
        if capacity <= 0:
            raise ValueError(f"Capacity must be positive, got {capacity}")
        self.capacity = capacity
        self.name = name
        self.hits = 0
        self.misses = 0
        self.requests = 0

    @abstractmethod
    def access(self, page_id: Any) -> bool:
        """
        Request a page from cache.
        Returns:
            True if cache hit, False if cache miss.
        """
        pass

    @property
    def hit_ratio(self) -> float:
        """Percentage of requests that resulted in a cache hit."""
        if self.requests == 0:
            return 0.0
        return (self.hits / self.requests) * 100.0

    @property
    def miss_ratio(self) -> float:
        """Percentage of requests that resulted in a cache miss."""
        if self.requests == 0:
            return 0.0
        return (self.misses / self.requests) * 100.0

    def stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "capacity": self.capacity,
            "requests": self.requests,
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": self.hit_ratio,
        }

    def reset_stats(self) -> None:
        self.hits = 0
        self.misses = 0
        self.requests = 0
