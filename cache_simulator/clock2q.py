"""
Clock2Q+: a correlation-window-aware clock replacement policy.

Based on "Clock2Q+: A Simple and Efficient Replacement Algorithm for
Metadata Cache in VMware vSAN" (PVLDB 19(12), 2026).
"""
from collections import OrderedDict
from typing import Any

from .base import CachePolicy


class Clock2QCache(CachePolicy):
    def __init__(self, capacity: int):
        super().__init__(capacity, name="Clock2Q+")
        self.small_capacity = max(1, int(capacity * 0.10))
        self.main_capacity = capacity - self.small_capacity
        self.ghost_capacity = max(1, int(capacity * 0.50))
        self.correlation_window = min(
            self.small_capacity,
            int(capacity * 0.05),
        )

        # Ordered dictionaries represent FIFO queues; values are reference bits.
        self.small: OrderedDict[Any, int] = OrderedDict()
        self.main: OrderedDict[Any, int] = OrderedDict()
        self.ghost: OrderedDict[Any, None] = OrderedDict()
        self._correlation_window: OrderedDict[Any, None] = OrderedDict()

    def _remember_ghost(self, page_id: Any) -> None:
        self.ghost.pop(page_id, None)
        self.ghost[page_id] = None
        while len(self.ghost) > self.ghost_capacity:
            self.ghost.popitem(last=False)

    def _add_to_small(self, page_id: Any) -> None:
        self.small[page_id] = 0
        if self.correlation_window:
            self._correlation_window[page_id] = None
            while len(self._correlation_window) > self.correlation_window:
                self._correlation_window.popitem(last=False)

    def _evict_main(self) -> None:
        while self.main:
            page_id, reference_bit = self.main.popitem(last=False)
            if reference_bit:
                self.main[page_id] = 0
            else:
                self._remember_ghost(page_id)
                return

    def _evict_small(self) -> None:
        page_id, reference_bit = self.small.popitem(last=False)
        self._correlation_window.pop(page_id, None)

        if reference_bit and self.main_capacity:
            if len(self.main) >= self.main_capacity:
                self._evict_main()
            self.main[page_id] = 0
        else:
            self._remember_ghost(page_id)

    def _make_room_for_small(self) -> None:
        if len(self.small) >= self.small_capacity:
            self._evict_small()
        if len(self) < self.capacity:
            return
        if self.main:
            self._evict_main()
        elif self.small:
            self._evict_small()

    def _make_room_for_main(self) -> None:
        while len(self) >= self.capacity:
            if self.main:
                self._evict_main()
            elif self.small:
                self._evict_small()
            else:
                break

        while self.main_capacity and len(self.main) >= self.main_capacity:
            self._evict_main()

    def access(self, page_id: Any) -> bool:
        self.requests += 1

        if page_id in self.small:
            if page_id not in self._correlation_window:
                self.small[page_id] = 1
            self.hits += 1
            return True

        if page_id in self.main:
            self.main[page_id] = 1
            self.hits += 1
            return True

        self.misses += 1
        if page_id in self.ghost:
            del self.ghost[page_id]
            if self.main_capacity:
                self._make_room_for_main()
                self.main[page_id] = 0
                return False

        self._make_room_for_small()
        self._add_to_small(page_id)
        return False

    def __contains__(self, page_id: Any) -> bool:
        return page_id in self.small or page_id in self.main

    def __len__(self) -> int:
        return len(self.small) + len(self.main)
