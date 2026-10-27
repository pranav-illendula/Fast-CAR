"""
CAR: Clock with Adaptive Replacement Algorithm.
Sorav Bansal and Dharmendra S. Modha (FAST '04).
"""
from collections import OrderedDict
from typing import Any, List, Optional, Tuple
from .base import CachePolicy


class CARCache(CachePolicy):
    def __init__(self, capacity: int, track_p_history: bool = False):
        super().__init__(capacity, name="CAR")
        self.p: float = 0.0  # Adaptive target size for list T1
        
        # T1 (recency) and T2 (frequency) clocks:
        # Maps page_id -> reference_bit (0 or 1)
        # Using OrderedDict: insertion order is preserved.
        # Cache hits update value in-place without moving position,
        # preserving the circular clock / second-chance semantics.
        self.T1: OrderedDict[Any, int] = OrderedDict()
        self.T2: OrderedDict[Any, int] = OrderedDict()
        
        # B1 and B2 ghost history directories (LRU order)
        # Store only keys (metadata) of recently evicted pages
        self.B1: OrderedDict[Any, bool] = OrderedDict()
        self.B2: OrderedDict[Any, bool] = OrderedDict()

        # Optional telemetry to reproduce Figure 6
        self.track_p_history = track_p_history
        self.p_history: List[Tuple[int, float]] = []

    def _replace(self) -> None:
        """
        Eviction routine corresponding to lines 22-39 of Figure 2.
        Finds a victim with reference bit == 0.
        """
        while True:
            # Line 24: if (|T1| >= max(1, p))
            if len(self.T1) >= max(1, self.p):
                # Inspect head page of T1
                head_page, ref_bit = next(iter(self.T1.items()))
                del self.T1[head_page]
                if ref_bit == 0:
                    # Demote head page in T1 and make it MRU in B1
                    self.B1[head_page] = True
                    break
                else:
                    # Second chance: set bit to 0 and move to tail of T2
                    self.T2[head_page] = 0
            else:
                # Inspect head page of T2
                head_page, ref_bit = next(iter(self.T2.items()))
                del self.T2[head_page]
                if ref_bit == 0:
                    # Demote head page in T2 and make it MRU in B2
                    self.B2[head_page] = True
                    break
                else:
                    # Second chance: set bit to 0 and re-insert at tail of T2
                    self.T2[head_page] = 0

    def access(self, page_id: Any) -> bool:
        """
        CAR access logic corresponding to lines 1-21 of Figure 2.
        """
        self.requests += 1

        # Line 1: Cache hit in T1 or T2
        if page_id in self.T1:
            # Line 2: Set page reference bit to 1.
            # No MRU operation, no list reorganization!
            self.T1[page_id] = 1
            self.hits += 1
            if self.track_p_history:
                self.p_history.append((self.requests, self.p))
            return True

        if page_id in self.T2:
            self.T2[page_id] = 1
            self.hits += 1
            if self.track_p_history:
                self.p_history.append((self.requests, self.p))
            return True

        # Line 3: Cache miss
        self.misses += 1

        # Line 4: If cache is full (|T1| + |T2| == c)
        if len(self.T1) + len(self.T2) == self.capacity:
            # Line 5: replace()
            self._replace()

            # Cache directory replacement (lines 6-10)
            is_new = (page_id not in self.B1) and (page_id not in self.B2)
            if is_new and (len(self.T1) + len(self.B1) == self.capacity):
                if self.B1:
                    self.B1.popitem(last=False)  # Discard LRU in B1
            elif is_new and (len(self.T1) + len(self.T2) + len(self.B1) + len(self.B2) == 2 * self.capacity):
                if self.B2:
                    self.B2.popitem(last=False)  # Discard LRU in B2

        # Cache directory miss or hit handling (lines 12-20)
        if (page_id not in self.B1) and (page_id not in self.B2):
            # Line 12-13: Totally new page -> Insert at tail of T1 with bit 0
            self.T1[page_id] = 0
        elif page_id in self.B1:
            # Line 14-16: Hit in ghost list B1 -> Adapt p upwards
            ratio = (len(self.B2) / len(self.B1)) if len(self.B1) > 0 else 1.0
            step = max(1.0, ratio)
            self.p = min(float(self.capacity), self.p + step)

            del self.B1[page_id]
            self.T2[page_id] = 0  # Move to tail of T2 with bit 0
        else:
            # Line 17-19: Hit in ghost list B2 -> Adapt p downwards
            ratio = (len(self.B1) / len(self.B2)) if len(self.B2) > 0 else 1.0
            step = max(1.0, ratio)
            self.p = max(0.0, self.p - step)

            del self.B2[page_id]
            self.T2[page_id] = 0  # Move to tail of T2 with bit 0

        if self.track_p_history:
            self.p_history.append((self.requests, self.p))

        return False

    def __contains__(self, page_id: Any) -> bool:
        return page_id in self.T1 or page_id in self.T2

    def __len__(self) -> int:
        return len(self.T1) + len(self.T2)
