"""
Classic CLOCK (Second Chance) Cache Replacement Algorithm.
Frank Corbató (1968).
"""
from typing import Any, Dict, List, Optional
from .base import CachePolicy


class ClockCache(CachePolicy):
    def __init__(self, capacity: int):
        super().__init__(capacity, name="CLOCK")
        self._slots: List[Optional[Any]] = [None] * capacity
        self._bits: List[int] = [0] * capacity
        self._page_to_index: Dict[Any, int] = {}
        self._hand: int = 0
        self._size: int = 0

    def access(self, page_id: Any) -> bool:
        self.requests += 1

        # Cache Hit: Simply set reference bit to 1 (No list reordering!)
        if page_id in self._page_to_index:
            idx = self._page_to_index[page_id]
            self._bits[idx] = 1
            self.hits += 1
            return True

        # Cache Miss
        self.misses += 1

        if self._size < self.capacity:
            # Cache is not yet full, populate next available slot
            idx = self._size
            self._slots[idx] = page_id
            self._bits[idx] = 0
            self._page_to_index[page_id] = idx
            self._size += 1
            return False

        # Cache is full: Advance clock hand to find victim with bit == 0
        while True:
            if self._bits[self._hand] == 0:
                # Victim found
                victim_page = self._slots[self._hand]
                del self._page_to_index[victim_page]

                # Replace slot with new page
                self._slots[self._hand] = page_id
                self._bits[self._hand] = 0
                self._page_to_index[page_id] = self._hand

                # Advance hand for next replacement
                self._hand = (self._hand + 1) % self.capacity
                break
            else:
                # Give second chance: reset bit to 0 and advance hand
                self._bits[self._hand] = 0
                self._hand = (self._hand + 1) % self.capacity

        return False

    def __contains__(self, page_id: Any) -> bool:
        return page_id in self._page_to_index

    def __len__(self) -> int:
        return self._size
