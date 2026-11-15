# Created by James Williams - 10/26/26 - login redirects, the main shopping pages and the bag

import os
import sys
import unittest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path += [os.path.dirname(BACKEND_ROOT), BACKEND_ROOT]

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema
from app import create_app


class TestLoginRedirect(unittest.TestCase):

    def test_logged_out_goes_to_login(self):
        client = create_app().test_client()
        for path in ("/storefronts", "/listings/1", "/categories", "/hot", "/cart"):
            response = client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertTrue(response.headers["Location"].endswith("/auth/login"), path)


@require_local_db
class TestPagesOnDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = ThrowawaySchema(prefix="test_pages").create()
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.db.drop()

    def setUp(self):
        self.user_id = self.db.add_user()
        self.listing = self.db.add_listing(self.db.add_storefront(), "Hoodie", quantity=4)
        self.db.execute("INSERT INTO cart_items (user_id, item_id, item_name, price, quantity, size) "
                        "VALUES (%s, %s, 'Hoodie', 10, 1, 'M');", (self.user_id, self.listing))
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["user"] = "shopper"
            sess["user_id"] = self.user_id
            sess["cart"] = [{"id": str(self.listing), "name": "Hoodie", "price": 10.0, "quantity": 1, "size": "M"}]

    def test_main_pages_load(self):
        for path in ("/storefronts", f"/listings/{self.listing}", "/categories", "/hot", "/auth/cart"):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_bag_quantity_stops_at_stock(self):
        # Only 4 are in stock, so asking for 9 should give 4
        self.client.post("/auth/update_cart/0", data={"quantity": "9"})
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["cart"][0]["quantity"], 4)
        self.assertEqual(self.db.scalar("SELECT quantity FROM cart_items WHERE user_id = %s;", (self.user_id,)), 4)


if __name__ == "__main__":
    unittest.main()
