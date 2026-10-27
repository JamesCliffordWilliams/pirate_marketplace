# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - the bag page: quantity changes and item photos
#
# Runs in a throwaway schema on a local database.

import os
import sys
import unittest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, '..'))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema


@require_local_db
class TestBag(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = ThrowawaySchema(prefix="test_bag").create()
        from app import create_app
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.secret_key = "test"

    @classmethod
    def tearDownClass(cls):
        cls.db.drop()

    def setUp(self):
        self.db.execute("DELETE FROM cart_items;")
        self.db.execute("DELETE FROM listings;")
        self.user_id = self.db.add_user()
        store = self.db.add_storefront()
        self.listing = self.db.add_listing(store, title="Hoodie", quantity=4)
        self.db.execute(
            "INSERT INTO listing_images (listing_id, image_url, is_primary) VALUES (%s, 'https://img/hoodie.jpg', TRUE);",
            (self.listing,),
        )
        self.db.execute(
            "INSERT INTO cart_items (user_id, item_id, item_name, price, quantity, size) VALUES (%s, %s, 'Hoodie', 10, 1, 'M');",
            (self.user_id, self.listing),
        )
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["user"] = "shopper"
            sess["user_id"] = self.user_id
            sess["cart"] = [{"id": str(self.listing), "name": "Hoodie", "price": 10.0, "quantity": 1, "size": "M"}]

    def session_cart(self):
        with self.client.session_transaction() as sess:
            return sess["cart"]

    def saved_quantity(self):
        return self.db.scalar("SELECT quantity FROM cart_items WHERE user_id = %s;", (self.user_id,))

    def test_quantity_change_updates_session_and_saved_cart(self):
        response = self.client.post("/auth/update_cart/0", data={"quantity": "3"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.session_cart()[0]["quantity"], 3)
        self.assertEqual(self.saved_quantity(), 3)

    def test_quantity_is_capped_at_stock(self):
        self.client.post("/auth/update_cart/0", data={"quantity": "9"})
        self.assertEqual(self.session_cart()[0]["quantity"], 4)
        self.assertEqual(self.saved_quantity(), 4)

    def test_bad_quantity_or_index_changes_nothing(self):
        for index, quantity in ((0, "0"), (0, "abc"), (5, "2")):
            with self.subTest(index=index, quantity=quantity):
                self.client.post(f"/auth/update_cart/{index}", data={"quantity": quantity})
                self.assertEqual(self.session_cart()[0]["quantity"], 1)
                self.assertEqual(self.saved_quantity(), 1)

    def test_logged_out_update_goes_to_login(self):
        response = self.app.test_client().post("/auth/update_cart/0", data={"quantity": "2"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])

    def test_bag_page_shows_photo_and_total(self):
        self.client.post("/auth/update_cart/0", data={"quantity": "2"})
        html = self.client.get("/auth/cart").get_data(as_text=True)
        self.assertIn("https://img/hoodie.jpg", html)
        self.assertIn(f'href="/listings/{self.listing}"', html)
        self.assertIn("$20.00", html)
        self.assertIn('action="/auth/update_cart/0"', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
