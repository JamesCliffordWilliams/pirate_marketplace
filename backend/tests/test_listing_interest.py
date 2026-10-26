# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - engagement tracking and Hot queries
#
# Runs against a throwaway schema on a LOCAL database (skipped otherwise, see db_test_guard.py).

import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema
from models import interest_model
from models.interest_model import (
    record_interest,
    is_listing_public,
    get_engagement_events,
    get_storefront_reach,
)
from models.listing_model import browse_public_listings, get_newest_available_listings
from services import interest_service
from services.interest_service import track_interest


@require_local_db
class TestRecordInterest(unittest.TestCase):

    def setUp(self):
        self.db = ThrowawaySchema().create()
        self.store = self.db.add_storefront()
        self.owner = self.db.owner_of(self.store)
        self.listing = self.db.add_listing(self.store)
        self.shopper = self.db.add_user()

    def tearDown(self):
        self.db.drop()

    def test_dedupes_per_day(self):
        self.assertTrue(record_interest(self.listing, self.shopper, "detail_view"))
        self.assertFalse(record_interest(self.listing, self.shopper, "detail_view"))
        self.assertTrue(record_interest(self.listing, self.shopper, "wishlist"))
        self.assertEqual(self.db.interest_rows(), [
            (self.listing, self.shopper, "detail_view"),
            (self.listing, self.shopper, "wishlist"),
        ])

    def test_new_day_is_a_new_row(self):
        self.db.add_interest(self.listing, self.shopper, "detail_view", hours_ago=30)
        self.assertTrue(record_interest(self.listing, self.shopper, "detail_view"))
        self.assertEqual(len(self.db.interest_rows()), 2)

    def test_owner_never_recorded(self):
        self.assertFalse(record_interest(self.listing, self.owner, "wishlist"))
        self.assertEqual(self.db.interest_rows(), [])

    def test_non_visible_listings_ignored(self):
        deleted = self.db.add_listing(self.store, status="DELETED")
        inactive = self.db.add_listing(self.store, status="INACTIVE")
        closed_store = self.db.add_storefront(is_active=False)
        closed = self.db.add_listing(closed_store)
        for listing_id in (deleted, inactive, closed, 999999):
            self.assertFalse(record_interest(listing_id, self.shopper, "detail_view"))
            self.assertFalse(is_listing_public(listing_id))
        self.assertEqual(self.db.interest_rows(), [])
        self.assertTrue(is_listing_public(self.listing))

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            record_interest(self.listing, self.shopper, "impression")

    def test_track_interest_never_raises(self):
        with patch.object(interest_service, "record_interest", side_effect=RuntimeError("db down")):
            self.assertFalse(track_interest(self.listing, self.shopper, "cart"))
        self.assertFalse(track_interest(self.listing, self.shopper, "impression"))
        self.assertFalse(track_interest(None, self.shopper, "cart"))
        self.assertFalse(track_interest(self.listing, None, "cart"))
        self.assertTrue(track_interest(self.listing, self.shopper, "cart"))

    def test_missing_table_does_nothing(self):
        self.db.execute("DROP TABLE listing_interest;")
        self.assertFalse(track_interest(self.listing, self.shopper, "cart"))
        self.assertEqual(get_engagement_events(14 * 24), [])
        self.assertEqual(get_storefront_reach([self.store], 30), {})


@require_local_db
class TestEngagementQueries(unittest.TestCase):

    def setUp(self):
        self.db = ThrowawaySchema().create()
        self.store = self.db.add_storefront()
        self.owner = self.db.owner_of(self.store)
        self.a = self.db.add_listing(self.store, "A")
        self.b = self.db.add_listing(self.store, "B")

    def tearDown(self):
        self.db.drop()

    def events(self):
        return sorted(
            (e["listing_id"], e["storefront_id"], e["user_id"], e["kind"], round(e["age_hours"]))
            for e in get_engagement_events(14 * 24)
        )

    def test_latest_event_of_each_kind(self):
        shopper = self.db.add_user(age_hours=500)
        self.db.add_interest(self.a, shopper, "detail_view", hours_ago=50)
        self.db.add_interest(self.a, shopper, "detail_view", hours_ago=2)
        self.db.add_interest(self.a, shopper, "cart", hours_ago=10)
        self.assertEqual(self.events(), [
            (self.a, self.store, shopper, "cart", 10),
            (self.a, self.store, shopper, "detail_view", 2),
        ])

    def test_window(self):
        shopper = self.db.add_user(age_hours=1000)
        self.db.add_interest(self.a, shopper, "order", hours_ago=14 * 24 + 2)
        self.assertEqual(self.events(), [])

    def test_owner_and_new_accounts_excluded(self):
        fresh = self.db.add_user(age_hours=5)          # account 5h old
        recent = self.db.add_user(age_hours=30)        # 30h old
        self.db.add_interest(self.a, self.owner, "order", hours_ago=1)
        self.db.add_interest(self.a, fresh, "wishlist", hours_ago=1)
        self.db.add_interest(self.a, recent, "wishlist", hours_ago=20)   # account was 10h old then
        self.db.add_interest(self.a, recent, "cart", hours_ago=1)        # account was 29h old then
        self.assertEqual(self.events(), [(self.a, self.store, recent, "cart", 1)])

    def test_account_age_rule_can_be_turned_off(self):
        fresh = self.db.add_user(age_hours=5)
        self.db.add_interest(self.a, fresh, "wishlist", hours_ago=1)
        events = get_engagement_events(14 * 24, min_account_age_hours=0)
        self.assertEqual([(e["user_id"], e["kind"]) for e in events], [(fresh, "wishlist")])

    def test_unavailable_listings_excluded(self):
        shopper = self.db.add_user(age_hours=500)
        sold_out = self.db.add_listing(self.store, status="SOLD_OUT")
        no_stock = self.db.add_listing(self.store, quantity=0)
        made_to_order = self.db.add_listing(self.store, quantity=0, made_to_order=True)
        for listing_id in (sold_out, no_stock, made_to_order):
            self.db.add_interest(listing_id, shopper, "order", hours_ago=1)
        self.assertEqual([e[0] for e in self.events()], [made_to_order])

    def test_reach_counts_people_not_events(self):
        loyal = self.db.add_user(age_hours=500)
        for hours in (1, 30, 60):
            for kind in ("detail_view", "wishlist", "cart"):
                self.db.add_interest(self.a, loyal, kind, hours_ago=hours)
                self.db.add_interest(self.b, loyal, kind, hours_ago=hours)
        self.db.add_interest(self.a, self.owner, "order", hours_ago=1)            # owner never counts
        self.db.add_interest(self.a, self.db.add_user(age_hours=2), "cart", 1)    # too new
        old = self.db.add_user(age_hours=2000)
        self.db.add_interest(self.a, old, "cart", hours_ago=31 * 24)              # outside 30 days
        other_store = self.db.add_storefront()
        self.assertEqual(get_storefront_reach([self.store, other_store], 30), {self.store: 1})


@require_local_db
class TestBrowseFilters(unittest.TestCase):

    def setUp(self):
        self.db = ThrowawaySchema().create()
        self.store = self.db.add_storefront()
        self.ok = self.db.add_listing(self.store, "ok")
        self.sold_out = self.db.add_listing(self.store, status="SOLD_OUT")
        self.no_stock = self.db.add_listing(self.store, quantity=0)
        self.null_qty = self.db.add_listing(self.store, quantity=None)
        self.made_to_order = self.db.add_listing(self.store, quantity=0, made_to_order=True)
        self.deleted = self.db.add_listing(self.store, status="DELETED")
        self.inactive = self.db.add_listing(self.store, status="INACTIVE")
        closed_store = self.db.add_storefront(is_active=False)
        self.closed = self.db.add_listing(closed_store)
        self.all_ids = [self.ok, self.sold_out, self.no_stock, self.null_qty, self.made_to_order,
                        self.deleted, self.inactive, self.closed]

    def tearDown(self):
        self.db.drop()

    def test_listing_ids_and_available_only(self):
        listings, total = browse_public_listings(listing_ids=self.all_ids, available_only=True, limit=50)
        self.assertEqual(sorted(l["id"] for l in listings), sorted([self.ok, self.null_qty, self.made_to_order]))
        self.assertEqual(total, 3)

    def test_listing_ids_without_available_only_keeps_visibility_rule(self):
        listings, _ = browse_public_listings(listing_ids=self.all_ids, limit=50)
        self.assertEqual(
            sorted(l["id"] for l in listings),
            sorted([self.ok, self.sold_out, self.no_stock, self.null_qty, self.made_to_order]),
        )

    def test_empty_ids(self):
        self.assertEqual(browse_public_listings(listing_ids=[], available_only=True), ([], 0))

    def test_default_call_unchanged(self):
        listings, total = browse_public_listings()
        self.assertEqual(total, 5)

    def test_newest_available(self):
        other = self.db.add_storefront()
        newer = [self.db.add_listing(other, f"n{i}", created_hours_ago=0) for i in range(3)]
        refs = get_newest_available_listings(exclude_ids=[newer[0]], per_storefront=2, limit=8)
        ids = [r["id"] for r in refs]
        self.assertEqual(ids[:2], [newer[2], newer[1]])
        self.assertNotIn(newer[0], ids)
        self.assertTrue(set(ids) <= {self.ok, self.null_qty, self.made_to_order, *newer})
        self.assertEqual(sum(1 for r in refs if r["storefront_id"] == self.store), 2)


if __name__ == "__main__":
    unittest.main()
