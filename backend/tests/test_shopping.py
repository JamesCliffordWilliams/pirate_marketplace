# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - storefront covers and the product page
#
# This runs in a test schema on a local database.

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
class TestShopping(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = ThrowawaySchema(prefix="test_shop").create()
        from app import create_app
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()
        with cls.client.session_transaction() as sess:
            sess["user"] = "shopper"  # Added by James Williams 10/27/26 - pages need a login

    @classmethod
    def tearDownClass(cls):
        cls.db.drop()

    def setUp(self):
        self.db.execute("DELETE FROM listings;")
        self.db.execute("DELETE FROM storefronts;")

    def add_photo(self, listing_id, url, primary=True):
        self.db.execute(
            "INSERT INTO listing_images (listing_id, image_url, is_primary) VALUES (%s, %s, %s);",
            (listing_id, url, primary),
        )

    def storefronts(self):
        return {s["id"]: s for s in self.client.get("/api/storefronts").get_json()}

    # ---------- GET /api/storefronts cover_images ----------

    def test_cover_images_are_the_newest_three_product_photos(self):
        store = self.db.add_storefront(name="Onyx")
        for hours, name in ((5, "a"), (4, "b"), (3, "c"), (2, "d")):
            listing = self.db.add_listing(store, title=name, created_hours_ago=hours)
            self.add_photo(listing, f"https://img/{name}.jpg")
            self.add_photo(listing, f"https://img/{name}-side.jpg", primary=False)
        self.assertEqual(self.storefronts()[store]["cover_images"],
                         ["https://img/d.jpg", "https://img/c.jpg", "https://img/b.jpg"])

    def test_cover_images_skip_hidden_listings_and_keep_old_fields(self):
        store = self.db.add_storefront(name="Nike")
        hidden = self.db.add_listing(store, status="INACTIVE")
        self.add_photo(hidden, "https://img/hidden.jpg")
        sold_out = self.db.add_listing(store, status="SOLD_OUT")
        self.add_photo(sold_out, "https://img/sold.jpg")
        empty = self.db.add_storefront(name="Empty")
        data = self.storefronts()
        self.assertEqual(data[store]["cover_images"], ["https://img/sold.jpg"])
        self.assertEqual(data[empty]["cover_images"], [])
        for field in ("brand_name", "logo_url", "banner_url", "preview_image_1", "item_count", "categories"):
            self.assertIn(field, data[store])

    # ---------- GET /listings/<id> ----------

    def test_product_page_shows_the_listing(self):
        store = self.db.add_storefront(name="Von Dutch")
        listing = self.db.add_listing(store, title="Camo trucker hat")
        self.db.execute("UPDATE listings SET description = 'Barely worn <b>hat</b>' WHERE id = %s;", (listing,))
        self.add_photo(listing, "https://img/hat.jpg")
        response = self.client.get(f"/listings/{listing}")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Camo trucker hat | Pirate Market", html)
        self.assertIn("$10.00", html)
        self.assertIn("Von Dutch", html)
        self.assertIn(f'href="/storefronts/{store}"', html)
        self.assertIn('value="M"', html)                      # size chip from listing_sizes
        self.assertIn("Barely worn &lt;b&gt;hat&lt;/b&gt;", html)  # HTML in the description gets escaped
        self.assertIn("https://img/hat.jpg", html)
        self.assertIn(f'data-listing-id="{listing}"', html)

    def test_product_page_hides_listings_shoppers_cant_buy(self):
        store = self.db.add_storefront()
        inactive = self.db.add_listing(store, status="INACTIVE")
        closed_store = self.db.add_storefront(is_active=False)
        in_closed = self.db.add_listing(closed_store)
        for listing_id in (inactive, in_closed, 999999):
            with self.subTest(listing_id=listing_id):
                response = self.client.get(f"/listings/{listing_id}")
                self.assertEqual(response.status_code, 404)
                self.assertIn("isn't available", response.get_data(as_text=True))

    def test_sold_out_listing_page_says_so(self):
        store = self.db.add_storefront()
        listing = self.db.add_listing(store, status="SOLD_OUT", quantity=0)
        html = self.client.get(f"/listings/{listing}").get_data(as_text=True)
        self.assertIn("Sold out", html)
        self.assertNotIn(">Add to bag<", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
