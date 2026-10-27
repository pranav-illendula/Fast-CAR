"""
Unit tests for LRU, CLOCK, ARC, CAR, and CART algorithms.
"""
import unittest
from cache_simulator import LRUCache, ClockCache, ARCCache, CARCache, CARTCache


class TestCacheAlgorithms(unittest.TestCase):
    def setUp(self):
        self.capacity = 4

    def test_lru_basic(self):
        cache = LRUCache(self.capacity)
        # Misses
        for p in [1, 2, 3, 4]:
            self.assertFalse(cache.access(p))
        self.assertEqual(len(cache), 4)
        self.assertEqual(cache.hits, 0)
        self.assertEqual(cache.misses, 4)

        # Hit on 1 (now 2 is LRU)
        self.assertTrue(cache.access(1))
        self.assertEqual(cache.hits, 1)

        # Access 5: should evict 2
        self.assertFalse(cache.access(5))
        self.assertNotIn(2, cache)
        self.assertIn(1, cache)
        self.assertIn(5, cache)

    def test_clock_basic(self):
        cache = ClockCache(self.capacity)
        for p in [1, 2, 3, 4]:
            self.assertFalse(cache.access(p))
        self.assertEqual(len(cache), 4)

        # Hit on 1 (sets bit=1)
        self.assertTrue(cache.access(1))
        self.assertEqual(cache.hits, 1)

        # Access 5: should sweep, see 1 has bit=1 (sets to 0), and evict 2 (bit=0)
        self.assertFalse(cache.access(5))
        self.assertNotIn(2, cache)
        self.assertIn(1, cache)
        self.assertIn(5, cache)

    def test_arc_basic(self):
        cache = ARCCache(self.capacity)
        # Fill cache
        for p in [1, 2, 3, 4]:
            self.assertFalse(cache.access(p))
        self.assertEqual(len(cache), 4)

        # Hit on 1 -> moves to T2
        self.assertTrue(cache.access(1))
        self.assertIn(1, cache.T2)

        # Miss on 5 -> should evict LRU of T1 to B1
        self.assertFalse(cache.access(5))
        self.assertEqual(len(cache), 4)

    def test_car_basic_and_invariants(self):
        c = self.capacity
        cache = CARCache(c)

        # Warm up with sequence
        seq = [1, 2, 3, 4, 1, 5, 2, 6, 7, 3, 1, 8, 9, 2]
        for p in seq:
            cache.access(p)
            # Verify CAR invariants
            self.assertLessEqual(len(cache.T1) + len(cache.T2), c, "Invariant I1 failed")
            self.assertLessEqual(len(cache.T1) + len(cache.B1), c, "Invariant I2 failed")
            self.assertLessEqual(len(cache.T2) + len(cache.B2), 2 * c, "Invariant I3 failed")
            self.assertLessEqual(
                len(cache.T1) + len(cache.T2) + len(cache.B1) + len(cache.B2),
                2 * c,
                "Invariant I4 failed"
            )

    def test_cart_basic_and_invariants(self):
        c = self.capacity
        cache = CARTCache(c)

        seq = [1, 2, 3, 4, 1, 5, 2, 6, 7, 3, 1, 8, 9, 2, 1, 2, 1, 3, 4, 5]
        for p in seq:
            cache.access(p)
            self.assertLessEqual(len(cache.T1) + len(cache.T2), c)
            self.assertLessEqual(len(cache.T2) + len(cache.B2), c)
            self.assertLessEqual(len(cache.T1) + len(cache.B1), 2 * c)

    def test_scan_resistance(self):
        """
        Scan resistance test:
        Frequently accessed working set [1, 2, 3, 4] with high repetition,
        followed by a long scan of one-time items [100..200].
        CAR and ARC should protect frequent items in T2, whereas basic LRU/CLOCK
        may suffer complete flush.
        """
        c = 10
        lru = LRUCache(c)
        clock = ClockCache(c)
        arc = ARCCache(c)
        car = CARCache(c)

        # Frequent items
        freq_items = [1, 2, 3, 4, 5]
        for _ in range(5):
            for item in freq_items:
                lru.access(item)
                clock.access(item)
                arc.access(item)
                car.access(item)

        # Scan of one-time pages
        scan_pages = list(range(100, 150))
        for item in scan_pages:
            lru.access(item)
            clock.access(item)
            arc.access(item)
            car.access(item)

        # Now test re-accessing freq_items:
        # ARC and CAR should retain items in T2
        car_retained = sum(1 for item in freq_items if item in car)
        arc_retained = sum(1 for item in freq_items if item in arc)
        lru_retained = sum(1 for item in freq_items if item in lru)

        self.assertGreaterEqual(car_retained, 1, "CAR should retain frequent items during scan")
        self.assertEqual(lru_retained, 0, "Basic LRU should be completely polluted by scan")


if __name__ == "__main__":
    unittest.main()
