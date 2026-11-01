"""
S3-FIFO: Small, Main, and Ghost FIFO cache replacement policy.
"""
from collections import OrderedDict
from typing import Any

from .base import CachePolicy


class S3FIFOCache(CachePolicy):
    def __init__(self, capacity: int):
        super().__init__(capacity, name="S3-FIFO")
        self.small_capacity = max(1, int(capacity * 0.10))
        self.main_capacity = capacity - self.small_capacity
        self.ghost_capacity = capacity

        # Small and main entries store a saturating frequency counter.
        self.small: OrderedDict[Any, int] = OrderedDict()
        self.main: OrderedDict[Any, int] = OrderedDict()
        self.ghost: OrderedDict[Any, None] = OrderedDict()

    def _remember_ghost(self, page_id: Any) -> None:
        self.ghost.pop(page_id, None)
        self.ghost[page_id] = None
        while len(self.ghost) > self.ghost_capacity:
            self.ghost.popitem(last=False)

    def _evict_main(self) -> None:
        while self.main:
            page_id, frequency = self.main.popitem(last=False)
            if frequency:
                self.main[page_id] = frequency - 1
            else:
                self._remember_ghost(page_id)
                return

    def _evict_small(self) -> None:
        while self.small:
            page_id, frequency = self.small.popitem(last=False)
            if frequency > 0 and self.main_capacity:
                self.main[page_id] = 0
                return
            self._remember_ghost(page_id)
            return

    def _ensure_free(self) -> None:
        while len(self) >= self.capacity:
            if self.main and len(self.main) >= self.main_capacity:
                self._evict_main()
            elif self.small:
                self._evict_small()
            elif self.main:
                self._evict_main()
            else:
                return

    def access(self, page_id: Any) -> bool:
        self.requests += 1

        if page_id in self.small:
            self.small[page_id] = min(3, self.small[page_id] + 1)
            self.hits += 1
            return True

        if page_id in self.main:
            self.main[page_id] = min(3, self.main[page_id] + 1)
            self.hits += 1
            return True

        self.misses += 1
        if page_id in self.ghost and self.main_capacity:
            del self.ghost[page_id]
            self._ensure_free()
            self.main[page_id] = 0
        else:
            self.ghost.pop(page_id, None)
            self._ensure_free()
            self.small[page_id] = 0
        return False

    def __contains__(self, page_id: Any) -> bool:
        return page_id in self.small or page_id in self.main

    def __len__(self) -> int:
        return len(self.small) + len(self.main)
