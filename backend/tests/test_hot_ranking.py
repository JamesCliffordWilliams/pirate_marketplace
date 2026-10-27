# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - Hot / Rising ranking tests (no database)

import math
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from config import hot_ranking as cfg
from services.hot_service import (
    decay,
    engager_contribution,
    rank_hot,
    rank_rising,
    rising_score,
    select_hot,
    select_rising,
    select_sections,
    needs_just_listed,
    select_just_listed,
)

_user_seq = [1000]


def new_user():
    _user_seq[0] += 1
    return _user_seq[0]


def event(listing_id, storefront_id, kind, age_hours, user_id=None):
    return {
        "listing_id": listing_id,
        "storefront_id": storefront_id,
        "user_id": user_id if user_id is not None else new_user(),
        "kind": kind,
        "age_hours": age_hours,
    }


def age_for(kind, contribution, half_life=cfg.RISING_HALF_LIFE_HOURS):
    """Age at which one event of this kind is worth `contribution`."""
    return half_life * math.log2(cfg.WEIGHTS[kind] / contribution)


def events_worth(listing_id, storefront_id, parts):
    """One engager per (kind, contribution) pair."""
    return [event(listing_id, storefront_id, kind, age_for(kind, value)) for kind, value in parts]


def hot_listing(listing_id, storefront_id, engagers=3, age=1.0):
    """A listing that qualifies for Hot: one wishlist plus views."""
    events = [event(listing_id, storefront_id, "wishlist", age)]
    events += [event(listing_id, storefront_id, "detail_view", age) for _ in range(engagers - 1)]
    return events


class TestDecayAndWeights(unittest.TestCase):

    def test_weights(self):
        self.assertEqual(cfg.WEIGHTS, {"order": 6, "cart": 4, "wishlist": 3, "detail_view": 1})

    def test_decay_halves_each_half_life(self):
        self.assertEqual(decay(0, 96), 1.0)
        self.assertAlmostEqual(decay(96, 96), 0.5)
        self.assertAlmostEqual(decay(192, 96), 0.25)
        self.assertAlmostEqual(decay(48, 48), 0.5)

    def test_future_events_count_as_fresh(self):
        self.assertEqual(decay(-5, 48), 1.0)

    def test_strongest_action_wins_no_stacking(self):
        events = [
            {"kind": "detail_view", "age_hours": 0},
            {"kind": "wishlist", "age_hours": 0},
            {"kind": "cart", "age_hours": 0},
        ]
        self.assertAlmostEqual(engager_contribution(events, 48), 4.0)

    def test_fresh_view_can_beat_stale_wishlist(self):
        events = [
            {"kind": "detail_view", "age_hours": 0},
            {"kind": "wishlist", "age_hours": 48 * 3},   # 3 * 0.125 = 0.375
        ]
        self.assertAlmostEqual(engager_contribution(events, 48), 1.0)

    def test_one_engager_many_events_counts_once(self):
        user = new_user()
        events = [event(1, 10, kind, 0, user) for kind in ("detail_view", "wishlist", "cart", "order")]
        events += [event(1, 10, "detail_view", 0), event(1, 10, "detail_view", 0)]
        ranked = rank_hot(events)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["engagers"], 3)
        self.assertAlmostEqual(ranked[0]["score"], 6 + 1 + 1)


class TestHotThresholds(unittest.TestCase):

    def test_three_engagers_with_a_save_qualifies(self):
        self.assertEqual([c["listing_id"] for c in rank_hot(hot_listing(1, 10))], [1])

    def test_views_only_never_qualify(self):
        events = [event(1, 10, "detail_view", 0) for _ in range(10)]
        self.assertEqual(rank_hot(events), [])

    def test_two_engagers_not_enough(self):
        events = [event(1, 10, "order", 0), event(1, 10, "order", 0)]
        self.assertEqual(rank_hot(events), [])

    def test_events_outside_window_ignored(self):
        old = cfg.HOT_WINDOW_DAYS * 24 + 1
        events = [event(1, 10, "order", old) for _ in range(5)]
        self.assertEqual(rank_hot(events), [])

    def test_order_score_desc_then_latest_then_id(self):
        events = hot_listing(1, 10, engagers=3, age=5)       # like 2, but older
        events += hot_listing(2, 11, engagers=3, age=1)
        events += hot_listing(3, 12, engagers=5, age=1)      # highest score
        events += hot_listing(4, 13, engagers=3, age=1)      # ties 2 exactly
        ranked = [c["listing_id"] for c in rank_hot(events)]
        self.assertEqual(ranked, [3, 4, 2, 1])


class TestHotSelection(unittest.TestCase):

    def test_max_two_per_storefront(self):
        events = []
        for i in range(3):
            events += hot_listing(10 + i, 1, engagers=5 - i)
        for i in range(3):
            events += hot_listing(20 + i, 2, engagers=5 - i)
        self.assertEqual(select_hot(rank_hot(events)), [20, 10, 21, 11])   # ties: higher id first

    def test_top_up_to_four_from_one_storefront(self):
        events = []
        for i in range(5):
            events += hot_listing(10 + i, 1, engagers=8 - i)
        self.assertEqual(select_hot(rank_hot(events)), [10, 11, 12, 13])

    def test_top_up_keeps_score_order(self):
        events = []
        for i in range(4):
            events += hot_listing(10 + i, 1, engagers=9 - i)    # 10..13, scores high
        events += hot_listing(30, 2, engagers=3)                 # low score
        # 10, 11 (cap), 30, then top up with 12 (next best remaining)
        self.assertEqual(select_hot(rank_hot(events)), [10, 11, 12, 30])

    def test_limit_eight(self):
        events = []
        for store in range(12):
            events += hot_listing(100 + store, store, engagers=3)
        self.assertEqual(len(select_hot(rank_hot(events))), 8)

    def test_empty(self):
        self.assertEqual(select_hot(rank_hot([])), [])


class TestRising(unittest.TestCase):

    def rising_ids(self, events, reach):
        return [c["listing_id"] for c in rank_rising(events, reach)]

    def test_views_only_fail(self):
        events = [event(1, 10, "detail_view", 0) for _ in range(6)]
        self.assertEqual(self.rising_ids(events, {10: 1}), [])

    def test_below_floor_fails(self):
        events = events_worth(1, 10, [("wishlist", 1.4), ("detail_view", 1.0)])   # raw 2.4
        self.assertEqual(self.rising_ids(events, {10: 2}), [])

    def test_stale_fails_even_above_floor(self):
        # raw well above 2.5, but nothing in the last 72h
        events = [event(1, 10, "order", 80) for _ in range(4)]
        self.assertEqual(self.rising_ids(events, {10: 4}), [])

    def test_needs_two_engagers(self):
        events = [event(1, 10, "order", 0)]
        self.assertEqual(self.rising_ids(events, {10: 1}), [])

    def test_rising_score_formula(self):
        self.assertAlmostEqual(rising_score(9.37, 60), 4.685)
        self.assertAlmostEqual(rising_score(4.0, 0), 4.0)

    def test_boost_never_makes_below_threshold_qualify(self):
        weak_small = events_worth(1, 10, [("wishlist", 1.4), ("detail_view", 1.0)])   # raw 2.4, reach 0
        ok_big = events_worth(2, 20, [("wishlist", 2.0), ("detail_view", 1.0)])        # raw 3.0, reach 500
        ranked = rank_rising(weak_small + ok_big, {10: 0, 20: 500})
        self.assertEqual([c["listing_id"] for c in ranked], [2])
        self.assertLess(ranked[0]["score"], 2.4)

    def test_simulated_scenarios(self):
        scenarios = {
            # listing_id: (storefront_id, reach, events)
            1: (1, 2, [event(1, 1, "detail_view", age_for("detail_view", 0.835)) for _ in range(2)]),
            2: (2, 2, [event(2, 2, "wishlist", age_for("wishlist", 0.37)) for _ in range(2)]),
            3: (3, 2, events_worth(3, 3, [("wishlist", 2.25), ("detail_view", 1.0)])),
            4: (4, 2, events_worth(4, 4, [("cart", 2.70), ("detail_view", 1.0)])),
            5: (5, 3, events_worth(5, 5, [("wishlist", 2.0145), ("wishlist", 2.0145), ("detail_view", 1.0)])),
            6: (6, 60, events_worth(6, 6, [("wishlist", 3.0), ("wishlist", 3.0)] + [("detail_view", 0.8425)] * 4)),
            7: (7, 60, events_worth(7, 7, [("detail_view", 0.46)] * 3 + [("wishlist", 3.0)])),
            8: (8, 15, events_worth(8, 8, [("wishlist", 21.92 / 15)] * 15)),
        }
        events = [e for _, _, evs in scenarios.values() for e in evs]
        reach = {store: r for store, r, _ in scenarios.values()}
        ranked = rank_rising(events, reach)
        by_id = {c["listing_id"]: c for c in ranked}

        # does not qualify: fresh views only, stale wishlists
        self.assertNotIn(1, by_id)
        self.assertNotIn(2, by_id)

        expected = {3: (3.25, 3.09), 4: (3.70, 3.53), 5: (5.03, 4.69), 6: (9.37, 4.68), 7: (4.38, 2.19), 8: (21.92, 16.57)}
        for listing_id, (raw, score) in expected.items():
            self.assertAlmostEqual(by_id[listing_id]["raw_score"], raw, delta=0.01, msg=listing_id)
            self.assertAlmostEqual(by_id[listing_id]["score"], score, delta=0.01, msg=listing_id)

        self.assertEqual([c["listing_id"] for c in ranked], [8, 5, 6, 4, 3, 7])

    def test_raw_score_of_the_non_qualifiers(self):
        views = [event(1, 1, "detail_view", age_for("detail_view", 0.835)) for _ in range(2)]
        stale = [event(2, 2, "wishlist", age_for("wishlist", 0.37)) for _ in range(2)]
        from services.hot_service import score_listings
        scored = score_listings(views + stale, cfg.RISING_WINDOW_DAYS * 24, cfg.RISING_HALF_LIFE_HOURS)
        self.assertAlmostEqual(scored[1]["raw_score"], 1.67, delta=0.01)
        self.assertAlmostEqual(scored[2]["raw_score"], 0.74, delta=0.01)

    def test_one_per_storefront_no_top_up(self):
        events = events_worth(1, 10, [("cart", 4.0), ("wishlist", 3.0)])
        events += events_worth(2, 10, [("cart", 4.0), ("detail_view", 1.0)])
        self.assertEqual(select_rising(rank_rising(events, {10: 2}), exclude_ids=[]), [1])

    def test_limit_eight(self):
        events = []
        for store in range(12):
            events += events_worth(100 + store, store, [("cart", 4.0), ("wishlist", 3.0)])
        self.assertEqual(len(select_rising(rank_rising(events, {}), exclude_ids=[])), 8)


class TestSections(unittest.TestCase):

    def test_hot_and_rising_are_exclusive(self):
        events = []
        for i in range(4):
            events += hot_listing(10 + i, i, engagers=4, age=1)
        sections = select_sections(rank_hot(events), rank_rising(events, {}), available_ids=None)
        self.assertEqual(sorted(sections["hot"]), [10, 11, 12, 13])
        self.assertEqual(sections["rising"], [])

    def test_hot_overflow_can_rise(self):
        events = []
        for i in range(5):
            events += hot_listing(10 + i, 1, engagers=6 - i, age=1)
        sections = select_sections(rank_hot(events), rank_rising(events, {}), available_ids=None)
        self.assertEqual(sections["hot"], [10, 11, 12, 13])
        self.assertEqual(sections["rising"], [14])
        self.assertFalse(set(sections["hot"]) & set(sections["rising"]))

    def test_unavailable_candidates_dropped_before_caps(self):
        events = []
        for i in range(3):
            events += hot_listing(10 + i, 1, engagers=6 - i)
        events += hot_listing(20, 2, engagers=3)
        hot = rank_hot(events)
        # 10 sold out since ranking: 11 and 12 fill the store's two slots
        sections = select_sections(hot, [], available_ids={11, 12, 20})
        self.assertEqual(sections["hot"], [11, 12, 20])

    def test_ties_are_deterministic(self):
        events = []
        for listing_id in (5, 9, 7):
            events += hot_listing(listing_id, listing_id, engagers=3, age=2)
        self.assertEqual(select_hot(rank_hot(events)), [9, 7, 5])
        self.assertEqual(select_hot(rank_hot(list(reversed(events)))), [9, 7, 5])

    def test_everything_empty(self):
        self.assertEqual(select_sections([], [], available_ids=set()), {"hot": [], "rising": []})


class TestJustListed(unittest.TestCase):

    NEWEST = [
        {"id": 50, "storefront_id": 1},
        {"id": 49, "storefront_id": 1},
        {"id": 48, "storefront_id": 1},
        {"id": 47, "storefront_id": 2},
        {"id": 46, "storefront_id": 3},
    ]

    def test_shown_only_under_four_combined(self):
        self.assertTrue(needs_just_listed([], []))
        self.assertTrue(needs_just_listed([1, 2], [3]))
        self.assertFalse(needs_just_listed([1, 2], [3, 4]))
        self.assertFalse(needs_just_listed([1, 2, 3, 4, 5], []))

    def test_storefront_cap_and_order(self):
        self.assertEqual(select_just_listed(self.NEWEST, exclude_ids=[]), [50, 49, 47, 46])

    def test_excludes_shown(self):
        self.assertEqual(select_just_listed(self.NEWEST, exclude_ids=[50, 47]), [49, 48, 46])

    def test_limit_eight(self):
        newest = [{"id": i, "storefront_id": i} for i in range(20, 0, -1)]
        self.assertEqual(select_just_listed(newest, exclude_ids=[]), list(range(20, 12, -1)))

    def test_one_storefront(self):
        newest = [{"id": i, "storefront_id": 1} for i in range(10, 0, -1)]
        self.assertEqual(select_just_listed(newest, exclude_ids=[]), [10, 9])


if __name__ == "__main__":
    unittest.main()
