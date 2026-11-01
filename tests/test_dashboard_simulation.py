"""Tests for trace parsing and interactive simulator helpers."""
import unittest

from dashboard_simulation import (
    POLICY_FACTORIES,
    compare_policies,
    parse_trace_text,
    policy_state,
    replay_prefix,
)


class TestDashboardSimulation(unittest.TestCase):
    def test_trace_parser_supports_comments_and_multi_column_rows(self):
        requests = parse_trace_text(
            "# trace header\ntimestamp,page_id,size\n1\n10, 22, 4096\n100 33 512\n",
            max_requests=3,
        )
        self.assertEqual(requests, [1, 22, 33])

    def test_trace_parser_reports_invalid_page_ids(self):
        with self.assertRaisesRegex(ValueError, "Line 2"):
            parse_trace_text("# header\n0, not-a-page, 4096\n")

    def test_replay_reports_the_last_access_and_eviction(self):
        policy, event = replay_prefix("LRU", [1, 2, 3, 4, 5], 4, 5)
        self.assertEqual(event["page_id"], 5)
        self.assertFalse(event["hit"])
        self.assertEqual(event["evicted_pages"], [1])
        self.assertEqual(len(policy), 4)
        self.assertEqual(policy.requests, 5)

    def test_policy_state_is_available_for_every_implementation(self):
        requests = [1, 2, 3, 4, 1, 5, 2, 6]
        for name in POLICY_FACTORIES:
            with self.subTest(policy=name):
                policy, _ = replay_prefix(name, requests, 4, len(requests))
                state = policy_state(policy)
                self.assertTrue(state)
                self.assertLessEqual(len(policy), 4)
                self.assertTrue(
                    all(
                        {
                            "Queue",
                            "Position",
                            "Page ID",
                            "Policy metadata",
                        }
                        <= row.keys()
                        for row in state
                    )
                )

    def test_comparison_runs_every_policy_on_the_same_request_count(self):
        results = compare_policies([1, 2, 1, 3, 2, 4], [2])
        self.assertEqual(len(results), len(POLICY_FACTORIES))
        self.assertEqual({row["Requests"] for row in results}, {6})
        self.assertTrue(all(0 <= row["Hit rate (%)"] <= 100 for row in results))


if __name__ == "__main__":
    unittest.main()
