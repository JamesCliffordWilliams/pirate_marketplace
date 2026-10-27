# Pirate Market Campus Marketplace
# Created by Aniya Hopson - 10/27/26 - order completion and 30-day pickup window
#
# Runs against a throwaway schema in a LOCAL database only (see db_test_guard).
# From the repo root:
#     python -m pytest backend/tests/test_order_lifecycle.py -v

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema

BUYER = {
    "first_name": "Jordan", "last_name": "Lee", "email": "jordan@my.hamptonu.edu",
    "contact": "757-555-0100", "meeting_location": "Student Center lobby",
}


@require_local_db
class TestOrderLifecycle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = ThrowawaySchema(prefix="test_orders").create()
        from app import create_app
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        cls.db.drop()

    def setUp(self):
        self.seller = self.db.add_user()
        self.store = self.db.add_storefront(owner_id=self.seller)
        self.buyer = self.db.add_user()

    # ---------- helpers ----------

    def login(self, user_id, cart=None):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["cart"] = cart or []
        return client

    def checkout(self, listing_id, quantity=1, size=None):
        cart = [{"id": listing_id, "name": "Hoodie", "price": 20, "quantity": quantity, "size": size}]
        return self.login(self.buyer, cart).post("/api/checkout/complete", json=BUYER)

    def stock(self, listing_id):
        return self.db.execute("SELECT quantity_on_hand, status FROM listings WHERE id = %s;", (listing_id,))[0]

    def status(self, order_id):
        return self.db.scalar("SELECT order_status FROM orders WHERE id = %s;", (order_id,))

    def make_overdue(self, order_id):
        self.db.execute("UPDATE orders SET expires_at = CURRENT_TIMESTAMP - INTERVAL '1 day' WHERE id = %s;", (order_id,))

    def expire(self):
        from models.order_model import expire_old_orders
        return expire_old_orders()

    # ---------- tests ----------

    def test_checkout_takes_stock_and_sets_30_day_deadline(self):
        listing = self.db.add_listing(self.store, quantity=3)  # one size "M"
        res = self.checkout(listing, quantity=2, size="M")
        self.assertEqual(res.status_code, 200, res.get_data(as_text=True))
        self.assertTrue(res.get_json()["confirmation_number"].startswith("PM-"))
        self.assertEqual(self.stock(listing), (1, "ACTIVE"))
        days = self.db.scalar("SELECT EXTRACT(DAY FROM expires_at - created_at) FROM orders WHERE id = %s;",
                              (res.get_json()["order_id"],))
        self.assertEqual(int(days), 30)

    def test_last_item_becomes_sold_out(self):
        listing = self.db.add_listing(self.store, quantity=1)
        self.checkout(listing, size="M")
        self.assertEqual(self.stock(listing), (0, "SOLD_OUT"))

    def test_not_enough_stock_saves_nothing(self):
        listing = self.db.add_listing(self.store, quantity=1)
        res = self.checkout(listing, quantity=5, size="M")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Only 1", res.get_json()["error"])
        self.assertEqual(self.stock(listing), (1, "ACTIVE"))
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM orders WHERE user_id = %s;", (self.buyer,)), 0)

    def test_overdue_order_expires_and_stock_comes_back_once(self):
        listing = self.db.add_listing(self.store, quantity=1)
        order_id = self.checkout(listing, size="M").get_json()["order_id"]
        self.make_overdue(order_id)
        self.expire()
        self.assertEqual(self.status(order_id), "EXPIRED")
        self.assertEqual(self.stock(listing), (1, "ACTIVE"))
        self.expire()  # running again must not add stock twice
        self.assertEqual(self.stock(listing), (1, "ACTIVE"))

    def test_seller_marks_picked_up_and_stock_stays_sold(self):
        listing = self.db.add_listing(self.store, quantity=2)
        order_id = self.checkout(listing, size="M").get_json()["order_id"]
        res = self.login(self.seller).post(f"/api/seller/orders/{order_id}/complete")
        self.assertEqual(res.get_json()["order_status"], "COMPLETED")
        self.make_overdue(order_id)
        self.expire()
        self.assertEqual(self.status(order_id), "COMPLETED")
        self.assertEqual(self.stock(listing)[0], 1)

    def test_other_seller_cannot_complete_the_order(self):
        listing = self.db.add_listing(self.store, quantity=2)
        order_id = self.checkout(listing, size="M").get_json()["order_id"]
        other_seller = self.db.add_user()
        self.db.add_storefront(owner_id=other_seller)
        res = self.login(other_seller).post(f"/api/seller/orders/{order_id}/complete")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.status(order_id), "SUBMITTED")

    def test_cannot_complete_after_deadline(self):
        listing = self.db.add_listing(self.store, quantity=1)
        order_id = self.checkout(listing, size="M").get_json()["order_id"]
        self.make_overdue(order_id)
        res = self.login(self.seller).post(f"/api/seller/orders/{order_id}/complete")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.status(order_id), "EXPIRED")
        self.assertEqual(self.stock(listing), (1, "ACTIVE"))

    def test_seller_sees_their_orders(self):
        listing = self.db.add_listing(self.store, quantity=2)
        self.checkout(listing, size="M")
        orders = self.login(self.seller).get("/api/seller/orders").get_json()["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["buyer_name"], "Jordan Lee")
        self.assertIsNotNone(orders[0]["pickup_by"])


if __name__ == "__main__":
    unittest.main()