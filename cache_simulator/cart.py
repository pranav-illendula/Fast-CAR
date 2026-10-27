"""
CART: Clock with Adaptive Replacement and Temporal Filtering Algorithm.
Sorav Bansal and Dharmendra S. Modha (FAST '04, Figure 3).
"""
from collections import OrderedDict
from typing import Any, Dict, Tuple
from .base import CachePolicy


class CARTCache(CachePolicy):
    def __init__(self, capacity: int):
        super().__init__(capacity, name="CART")
        self.p: float = 0.0  # Target size for T1 (temporal locality window)
        self.q: float = 0.0  # Target size for list B1
        self.nS: int = 0     # Number of pages in cache with filter bit 'S'
        self.nL: int = 0     # Number of pages in cache with filter bit 'L'

        # T1: page_id -> [reference_bit (0 or 1), filter_bit ('S' or 'L')]
        self.T1: OrderedDict[Any, list] = OrderedDict()
        
        # T2: page_id -> [reference_bit (0 or 1)] (all pages in T2 are implicitly 'L')
        self.T2: OrderedDict[Any, list] = OrderedDict()

        # Ghost history directories
        self.B1: OrderedDict[Any, bool] = OrderedDict()
        self.B2: OrderedDict[Any, bool] = OrderedDict()

    def _replace(self) -> None:
        """
        Victim selection with temporal filtering (lines 23-40 of Figure 3).
        """
        # Lines 23-26: Flush referenced pages from T2 to T1
        while self.T2:
            head_page = next(iter(self.T2))
            if self.T2[head_page][0] == 1:
                del self.T2[head_page]
                self.T1[head_page] = [0, "L"]  # Move to tail of T1 with bit 0
                if len(self.T2) + len(self.B2) + len(self.T1) - self.nS >= self.capacity:
                    self.q = min(self.q + 1.0, 2.0 * self.capacity - len(self.T1))
            else:
                break

        # Lines 27-35: Sweep T1 until head is 'S' and bit is 0 (or T1 empty)
        while self.T1:
            head_page = next(iter(self.T1))
            ref_bit, filter_bit = self.T1[head_page]

            if filter_bit == "L" or ref_bit == 1:
                del self.T1[head_page]
                if ref_bit == 1:
                    # Move to tail of T1 with bit 0
                    new_filter = filter_bit
                    if len(self.T1) + 1 >= min(self.p + 1.0, len(self.B1)) and filter_bit == "S":
                        new_filter = "L"
                        self.nS -= 1
                        self.nL += 1
                    self.T1[head_page] = [0, new_filter]
                else:
                    # ref_bit == 0 and filter_bit == 'L' -> move to tail of T2
                    self.T2[head_page] = [0]
                    self.q = max(self.q - 1.0, float(self.capacity - len(self.T1)))
            else:
                break

        # Lines 36-40: Cache replacement decision
        if len(self.T1) >= max(1.0, self.p) and len(self.T1) > 0:
            # Demote head page in T1 to MRU in B1
            head_page = next(iter(self.T1))
            del self.T1[head_page]
            self.B1[head_page] = True
            self.nS -= 1
        elif len(self.T2) > 0:
            # Demote head page in T2 to MRU in B2
            head_page = next(iter(self.T2))
            del self.T2[head_page]
            self.B2[head_page] = True
            self.nL -= 1
        elif len(self.T1) > 0:
            head_page = next(iter(self.T1))
            _, filter_bit = self.T1[head_page]
            del self.T1[head_page]
            self.B1[head_page] = True
            if filter_bit == "S":
                self.nS -= 1
            else:
                self.nL -= 1

    def access(self, page_id: Any) -> bool:
        """
        CART access logic corresponding to lines 1-22 of Figure 3.
        """
        self.requests += 1

        # Line 1-2: Cache hit
        if page_id in self.T1:
            self.T1[page_id][0] = 1
            self.hits += 1
            return True

        if page_id in self.T2:
            self.T2[page_id][0] = 1
            self.hits += 1
            return True

        # Line 3: Cache miss
        self.misses += 1

        # Line 4: Cache full
        if len(self.T1) + len(self.T2) == self.capacity:
            self._replace()

            # History replacement (lines 6-10)
            is_new = (page_id not in self.B1) and (page_id not in self.B2)
            if is_new and (len(self.B1) + len(self.B2) == self.capacity + 1):
                if (len(self.B1) > max(0.0, self.q)) or (len(self.B2) == 0):
                    if self.B1:
                        self.B1.popitem(last=False)
                else:
                    if self.B2:
                        self.B2.popitem(last=False)

        # Line 12-21: History miss or hit
        if (page_id not in self.B1) and (page_id not in self.B2):
            # Totally new page: type 'S', bit 0
            self.T1[page_id] = [0, "S"]
            self.nS += 1
        elif page_id in self.B1:
            # History hit in B1
            step = max(1.0, float(self.nS) / float(len(self.B1))) if len(self.B1) > 0 else 1.0
            self.p = min(self.p + step, float(self.capacity))
            del self.B1[page_id]
            self.T1[page_id] = [0, "L"]
            self.nL += 1
        else:
            # History hit in B2
            step = max(1.0, float(self.nL) / float(len(self.B2))) if len(self.B2) > 0 else 1.0
            self.p = max(self.p - step, 0.0)
            del self.B2[page_id]
            self.T1[page_id] = [0, "L"]
            self.nL += 1
            if len(self.T2) + len(self.B2) + len(self.T1) - self.nS >= self.capacity:
                self.q = min(self.q + 1.0, 2.0 * self.capacity - len(self.T1))

        return False

    def __contains__(self, page_id: Any) -> bool:
        return page_id in self.T1 or page_id in self.T2

    def __len__(self) -> int:
        return len(self.T1) + len(self.T2)
