"""
Least Recently Used (LRU) Cache Replacement Algorithm.
"""
from collections import OrderedDict
from typing import Any
from .base import CachePolicy


class LRUCache(CachePolicy):
    def __init__(self, capacity: int):
        super().__init__(capacity, name="LRU")
        self._cache = OrderedDict()

    def access(self, page_id: Any) -> bool:
        self.requests += 1
        if page_id in self._cache:
            # Hit: Move to MRU position (simulating serialized hit under lock)
            self._cache.move_to_end(page_id, last=True)
            self.hits += 1
            return True
        else:
            # Miss: Check capacity and evict LRU (first item)
            self.misses += 1
            if len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)
            self._cache[page_id] = True
            return False

    def __contains__(self, page_id: Any) -> bool:
        return page_id in self._cache

    def __len__(self) -> int:
        return len(self._cache)
