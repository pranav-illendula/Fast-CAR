"""
Unit tests for LRU, CLOCK, ARC, CAR, and CART algorithms.
"""
import unittest
from cache_simulator import (
    LRUCache,
    ClockCache,
    ARCCache,
    CARCache,
    CARTCache,
    Clock2QCache,
    S3FIFOCache,
)
from cache_simulator.workloads import correlated_workload


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

    def test_clock2q_correlation_window_and_promotion(self):
        cache = Clock2QCache(capacity=40)
        self.assertEqual(cache.small_capacity, 4)
        self.assertEqual(cache.correlation_window, 2)

        for page in [1, 2, 3, 4]:
            cache.access(page)

        cache.access(1)
        cache.access(4)
        self.assertEqual(cache.small[1], 1)
        self.assertEqual(cache.small[4], 0)

        cache.access(5)
        self.assertIn(1, cache.main)
        self.assertIn(4, cache.small)

    def test_clock2q_ghost_references_enter_main(self):
        cache = Clock2QCache(capacity=40)
        for page in [1, 2, 3, 4, 5]:
            cache.access(page)
        self.assertIn(1, cache.ghost)

        self.assertFalse(cache.access(1))
        self.assertIn(1, cache.main)
        self.assertNotIn(1, cache.ghost)

    def test_s3fifo_promotes_reused_pages_and_tracks_cold_evictions(self):
        cache = S3FIFOCache(capacity=10)
        cache.access(1)
        cache.access(1)
        for page in range(2, 13):
            cache.access(page)

        self.assertIn(1, cache.main)
        self.assertIn(2, cache.ghost)

    def test_s3fifo_ghost_references_enter_main(self):
        cache = S3FIFOCache(capacity=10)
        for page in range(1, 12):
            cache.access(page)
        self.assertIn(1, cache.ghost)

        self.assertFalse(cache.access(1))
        self.assertIn(1, cache.main)
        self.assertNotIn(1, cache.ghost)

    def test_new_policies_preserve_queue_and_capacity_invariants(self):
        for capacity in [1, 2, 4, 10, 40]:
            for policy_type in [Clock2QCache, S3FIFOCache]:
                cache = policy_type(capacity)
                stream = correlated_workload(
                    num_requests=500,
                    num_pages=64,
                    burst_length=5,
                    burst_prob=0.7,
                    correlation_group_size=8,
                    seed=capacity,
                )
                for page in stream:
                    cache.access(page)
                    self.assertLessEqual(len(cache), capacity)
                    self.assertLessEqual(len(cache.ghost), cache.ghost_capacity)
                    self.assertTrue(set(cache.small).isdisjoint(cache.main))
                    self.assertTrue(set(cache.small).isdisjoint(cache.ghost))
                    self.assertTrue(set(cache.main).isdisjoint(cache.ghost))
                    if isinstance(cache, Clock2QCache):
                        self.assertLessEqual(len(cache.small), cache.small_capacity)
                        self.assertLessEqual(len(cache.main), cache.main_capacity)
                        self.assertTrue(set(cache._correlation_window).issubset(cache.small))

    def test_correlated_workload_bursts_cover_multiple_related_pages(self):
        stream = correlated_workload(
            num_requests=80,
            num_pages=16,
            burst_length=2,
            burst_prob=1.0,
            seed=7,
            correlation_group_size=2,
        )

        for offset in range(0, len(stream), 4):
            burst = stream[offset:offset + 4]
            self.assertEqual(len(set(burst)), 2)
            self.assertEqual(burst[0], burst[1])
            self.assertEqual(burst[2], burst[3])
            self.assertEqual((burst[0] - 1) // 2, (burst[2] - 1) // 2)


if __name__ == "__main__":
    unittest.main()
