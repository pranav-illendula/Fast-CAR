"""
Adaptive Replacement Cache (ARC) Algorithm.
Nimrod Megiddo and Dharmendra S. Modha (FAST '03).
"""
from collections import OrderedDict
from typing import Any
from .base import CachePolicy


class ARCCache(CachePolicy):
    def __init__(self, capacity: int):
        super().__init__(capacity, name="ARC")
        self.p: float = 0.0  # Target size for T1
        self.T1: OrderedDict[Any, bool] = OrderedDict()  # Recency cache
        self.T2: OrderedDict[Any, bool] = OrderedDict()  # Frequency cache
        self.B1: OrderedDict[Any, bool] = OrderedDict()  # Ghost recency
        self.B2: OrderedDict[Any, bool] = OrderedDict()  # Ghost frequency

    def _replace(self, page_id: Any) -> None:
        if len(self.T1) > 0 and ((page_id in self.B2 and len(self.T1) == self.p) or (len(self.T1) > self.p)):
            # Evict LRU of T1 to B1
            victim, _ = self.T1.popitem(last=False)
            self.B1[victim] = True
        else:
            # Evict LRU of T2 to B2
            victim, _ = self.T2.popitem(last=False)
            self.B2[victim] = True

    def access(self, page_id: Any) -> bool:
        self.requests += 1

        # Case 1: Hit in T1 or T2
        if page_id in self.T1:
            del self.T1[page_id]
            self.T2[page_id] = True
            self.hits += 1
            return True
        elif page_id in self.T2:
            self.T2.move_to_end(page_id, last=True)
            self.hits += 1
            return True

        self.misses += 1

        # Case 2: Hit in B1 (Ghost Recency)
        if page_id in self.B1:
            delta = max(1, len(self.B2) // len(self.B1)) if len(self.B1) > 0 else 1
            self.p = min(self.capacity, self.p + delta)
            self._replace(page_id)
            del self.B1[page_id]
            self.T2[page_id] = True
            return False

        # Case 3: Hit in B2 (Ghost Frequency)
        elif page_id in self.B2:
            delta = max(1, len(self.B1) // len(self.B2)) if len(self.B2) > 0 else 1
            self.p = max(0, self.p - delta)
            self._replace(page_id)
            del self.B2[page_id]
            self.T2[page_id] = True
            return False

        # Case 4: Complete Miss (page not in T1, T2, B1, B2)
        else:
            if len(self.T1) + len(self.B1) == self.capacity:
                if len(self.T1) < self.capacity:
                    self.B1.popitem(last=False)
                    self._replace(page_id)
                else:
                    self.T1.popitem(last=False)
            else:
                total = len(self.T1) + len(self.T2) + len(self.B1) + len(self.B2)
                if total >= self.capacity:
                    if total == 2 * self.capacity:
                        self.B2.popitem(last=False)
                    self._replace(page_id)
            self.T1[page_id] = True
            return False

    def __contains__(self, page_id: Any) -> bool:
        return page_id in self.T1 or page_id in self.T2

    def __len__(self) -> int:
        return len(self.T1) + len(self.T2)
