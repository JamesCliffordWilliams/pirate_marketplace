# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - tracking on wishlist, cart, checkout and the interest API
#
# This runs in a test schema on a local database and gets skipped otherwise
# (see db_test_guard.py).

import os
import sys
import time
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema
from app import create_app
from models import interest_model
from services import interest_service

BUYER = {
    "first_name": "Ada",
    "last_name": "Shopper",
    "email": "ada@example.com",
    "contact": "555-0100",
    "meeting_location": "Library",
}


@require_local_db
class HookTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.db = ThrowawaySchema().create()
        self.client = self.app.test_client()
        self.store = self.db.add_storefront()
        self.owner = self.db.owner_of(self.store)
        self.listing = self.db.add_listing(self.store, "Hoodie", quantity=5)
        self.shopper = self.db.add_user("shopper")

    def tearDown(self):
        self.db.drop()

    def login(self, user_id, username="shopper", cart=None):
        with self.client.session_transaction() as sess:
            sess["user"] = username
            sess["user_id"] = user_id
            sess["cart"] = cart or []

    def kinds(self):
        return [row[2] for row in self.db.interest_rows()]

    def failing_tracker(self):
        from contextlib import ExitStack
        stack = ExitStack()
        for name in ("record_interest", "record_interests"):
            stack.enter_context(patch.object(interest_service, name, side_effect=RuntimeError("db down")))
        return stack


class TestWishlistHook(HookTestCase):

    def add(self, header_user):
        return self.client.post("/api/wishlist", json={"listing_id": self.listing},
                                headers={"X-User-Id": str(header_user)})

    def test_logged_in_shopper_recorded(self):
        self.login(self.shopper)
        response = self.add(self.shopper)
        self.assertEqual((response.status_code, response.get_json()), (201, {"message": "Item added to wishlist"}))
        self.assertEqual(self.db.interest_rows(), [(self.listing, self.shopper, "wishlist")])

    def test_header_only_works_but_records_nothing(self):
        response = self.add(self.shopper)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.kinds(), [])

    def test_spoofed_header_records_nothing(self):
        other = self.db.add_user("other")
        self.login(self.shopper)
        response = self.add(other)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.kinds(), [])

    def test_duplicate_add_records_nothing_new(self):
        self.login(self.shopper)
        self.add(self.shopper)
        response = self.add(self.shopper)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.kinds(), ["wishlist"])

    def test_owner_not_recorded(self):
        self.login(self.owner, "owner")
        self.assertEqual(self.add(self.owner).status_code, 201)
        self.assertEqual(self.kinds(), [])

    def test_tracking_failure_leaves_response_unchanged(self):
        self.login(self.shopper)
        with self.failing_tracker():
            response = self.add(self.shopper)
        self.assertEqual((response.status_code, response.get_json()), (201, {"message": "Item added to wishlist"}))
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM wishlist;"), 1)


class TestCartHook(HookTestCase):

    def add(self, price="10", listing_id=None):
        return self.client.post("/auth/add_to_cart", data={
            "item_id": str(listing_id or self.listing), "item_name": "Hoodie",
            "price": price, "quantity": "1", "size": "M",
        })

    def test_recorded_after_cart_row_committed(self):
        self.login(self.shopper)
        seen = []
        real = interest_service.record_interest

        def check_then_record(listing_id, user_id, kind):
            seen.append(self.db.scalar("SELECT COUNT(*) FROM cart_items WHERE user_id = %s;", (user_id,)))
            return real(listing_id, user_id, kind)

        with patch.object(interest_service, "record_interest", side_effect=check_then_record):
            response = self.add()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(seen, [1])
        self.assertEqual(self.db.interest_rows(), [(self.listing, self.shopper, "cart")])

    def test_failed_insert_records_nothing(self):
        self.login(self.shopper)
        response = self.add(price="-5")      # bad price, but the page still redirects like before
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM cart_items;"), 0)
        self.assertEqual(self.kinds(), [])

    def test_sold_out_records_nothing(self):
        sold_out = self.db.add_listing(self.store, status="SOLD_OUT")
        self.login(self.shopper)
        self.assertEqual(self.add(listing_id=sold_out).status_code, 409)
        self.assertEqual(self.kinds(), [])

    def test_logged_out_records_nothing(self):
        self.assertEqual(self.add().status_code, 302)
        self.assertEqual(self.kinds(), [])

    def test_tracking_failure_leaves_response_unchanged(self):
        self.login(self.shopper)
        with self.failing_tracker():
            response = self.add()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/auth/cart"))
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM cart_items;"), 1)
        with self.client.session_transaction() as sess:
            self.assertEqual(len(sess["cart"]), 1)


class TestCheckoutHook(HookTestCase):

    def cart(self, listing_id=None, quantity=1):
        return [{"id": listing_id or self.listing, "name": "Hoodie", "price": 10.0,
                 "quantity": quantity, "size": "M"}]

    def checkout(self, details=BUYER):
        return self.client.post("/api/checkout/complete", json=details)

    def test_order_recorded_only_after_order_saved(self):
        self.login(self.shopper, cart=self.cart())
        seen = []
        real = interest_service.record_interests

        def check_then_record(listing_ids, user_id, kind):
            # This reads on a separate connection, so it only sees saved rows
            seen.append((
                self.db.scalar("SELECT COUNT(*) FROM orders WHERE user_id = %s;", (user_id,)),
                self.db.scalar("SELECT COUNT(*) FROM order_items WHERE listing_id = ANY(%s);", (listing_ids,)),
            ))
            return real(listing_ids, user_id, kind)

        with patch.object(interest_service, "record_interests", side_effect=check_then_record):
            response = self.checkout()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(seen, [(1, 1)])
        self.assertEqual(self.db.interest_rows(), [(self.listing, self.shopper, "order")])

    def test_buying_the_last_one_still_records(self):
        last = self.db.add_listing(self.store, quantity=1)
        self.login(self.shopper, cart=self.cart(last))
        self.assertEqual(self.checkout().status_code, 200)
        self.assertEqual(self.db.interest_rows(), [(last, self.shopper, "order")])

    def test_rejected_checkout_records_nothing(self):
        self.login(self.shopper, cart=self.cart())
        response = self.checkout({**BUYER, "email": ""})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM orders;"), 0)
        self.assertEqual(self.kinds(), [])

    def test_sold_out_checkout_records_nothing(self):
        sold_out = self.db.add_listing(self.store, status="SOLD_OUT")
        self.login(self.shopper, cart=self.cart(sold_out))
        self.assertEqual(self.checkout().status_code, 400)
        self.assertEqual(self.kinds(), [])

    def test_tracking_failure_leaves_response_unchanged(self):
        self.login(self.shopper, cart=self.cart())
        with self.failing_tracker():
            response = self.checkout()
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(data), {"success", "confirmation_number", "order_id", "total_amount"})
        self.assertEqual(data["total_amount"], 10.0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM orders;"), 1)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["cart"], [])

    def test_tracker_crash_cannot_break_checkout(self):
        # Even if tracking crashes, the order still goes through
        self.login(self.shopper, cart=self.cart())
        with patch("controllers.checkout_controller.track_order", side_effect=RuntimeError("boom")):
            response = self.checkout()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])


class TestTrackingTimeouts(HookTestCase):

    def test_whole_order_uses_one_connection(self):
        others = [self.db.add_listing(self.store, f"Item {i}") for i in range(2)]
        real = interest_model.get_connection
        calls = []

        def counting(*args, **kwargs):
            calls.append(kwargs)
            return real(*args, **kwargs)

        with patch.object(interest_model, "get_connection", side_effect=counting):
            interest_service.track_order(self.shopper, [
                {"listing_id": self.listing}, {"listing_id": others[0]}, {"listing_id": others[1]},
                {"listing_id": self.listing},
            ])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].get("connect_timeout"), interest_model.TRACKING_TIMEOUT_SECONDS)
        self.assertEqual(sorted(r[0] for r in self.db.interest_rows()), sorted([self.listing] + others))

    def test_stuck_tracking_cannot_hold_up_checkout(self):
        # Another connection locks listing_interest so tracking can't write
        blocker = self.db.connect()
        blocker.cursor().execute("LOCK TABLE listing_interest IN ACCESS EXCLUSIVE MODE;")
        try:
            self.login(self.shopper, cart=[{"id": self.listing, "name": "Hoodie", "price": 10.0,
                                            "quantity": 1, "size": "M"}])
            started = time.monotonic()
            response = self.client.post("/api/checkout/complete", json=BUYER)
            elapsed = time.monotonic() - started
        finally:
            blocker.rollback()
            blocker.close()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertLess(elapsed, interest_model.TRACKING_TIMEOUT_SECONDS + 3)
        self.assertEqual(self.kinds(), [])


class TestInterestApi(HookTestCase):

    def post(self, listing_id=None, body=None, **kwargs):
        return self.client.post(f"/api/listings/{listing_id or self.listing}/interest",
                                json=body if body is not None else {"kind": "detail_view"}, **kwargs)

    def test_logged_out_401(self):
        self.assertEqual(self.post().status_code, 401)
        self.assertEqual(self.kinds(), [])

    def test_records_detail_view_once(self):
        self.login(self.shopper)
        first = self.post()
        self.assertEqual((first.status_code, first.data), (204, b""))
        self.assertEqual(self.post().status_code, 204)
        self.assertEqual(self.db.interest_rows(), [(self.listing, self.shopper, "detail_view")])

    def test_requires_json(self):
        self.login(self.shopper)
        response = self.client.post(f"/api/listings/{self.listing}/interest", data="kind=detail_view",
                                    content_type="application/x-www-form-urlencoded")
        self.assertEqual(response.status_code, 415)
        self.assertEqual(self.kinds(), [])

    def test_only_detail_view(self):
        self.login(self.shopper)
        for kind in ("order", "cart", "wishlist", "impression", None):
            self.assertEqual(self.post(body={"kind": kind}).status_code, 400, kind)
        self.assertEqual(self.kinds(), [])

    def test_missing_or_hidden_listing_404(self):
        self.login(self.shopper)
        hidden = self.db.add_listing(self.store, status="INACTIVE")
        self.assertEqual(self.post(hidden).status_code, 404)
        self.assertEqual(self.post(987654).status_code, 404)
        self.assertEqual(self.kinds(), [])

    def test_errors_do_not_expose_internals(self):
        from controllers import hot_controller
        self.login(self.shopper)
        with patch.object(hot_controller, "is_listing_public", side_effect=RuntimeError('host "db.internal.example"')):
            with self.assertLogs(self.app.logger, level="ERROR"):
                response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("db.internal.example", response.get_data(as_text=True))

    def test_owner_gets_204_but_nothing_recorded(self):
        self.login(self.owner, "owner")
        self.assertEqual(self.post().status_code, 204)
        self.assertEqual(self.kinds(), [])


if __name__ == "__main__":
    unittest.main()
