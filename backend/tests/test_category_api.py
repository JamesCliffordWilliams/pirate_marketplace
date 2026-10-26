# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - category API tests
#
# TestCategoryApiOffline: Flask test client with the model layer mocked (no database).
# TestCategoryApiOnDatabase: real queries against a LOCAL database that already has
#   the product category migration applied (skipped otherwise, see db_test_guard.py).

import os
import sys
import unittest
import uuid
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from tests.db_test_guard import require_local_db
from app import create_app
from services import category_service


TREE = [
    {"id": 1, "slug": "electronics-and-technology", "name": "Electronics & Technology", "parent_id": None,
     "description": None, "icon": "laptop", "sort_order": 1, "is_active": True, "children": [
         {"id": 2, "slug": "laptops-and-computers", "name": "Laptops & Computers", "parent_id": 1,
          "description": None, "icon": None, "sort_order": 1, "is_active": True, "children": []},
         {"id": 3, "slug": "phones", "name": "Phones", "parent_id": 1,
          "description": None, "icon": None, "sort_order": 2, "is_active": True, "children": []},
     ]},
    {"id": 9, "slug": "other", "name": "Other", "parent_id": None, "description": None,
     "icon": "box", "sort_order": 12, "is_active": True, "children": []},
]

CATEGORIES = {
    "electronics-and-technology": {"id": 1, "slug": "electronics-and-technology", "name": "Electronics & Technology",
                                   "parent_id": None, "parent_slug": None, "parent_name": None,
                                   "is_active": True, "child_count": 2, "description": None, "icon": "laptop"},
    "phones": {"id": 3, "slug": "phones", "name": "Phones", "parent_id": 1,
               "parent_slug": "electronics-and-technology", "parent_name": "Electronics & Technology",
               "is_active": True, "child_count": 0, "description": None, "icon": None},
}


class TestCategoryApiOffline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        for name, kwargs in (
            ("get_category_tree", {"return_value": TREE}),
            ("get_category_by_slug", {"side_effect": CATEGORIES.get}),
            ("get_child_categories", {"side_effect": lambda pid: [{"id": 2}, {"id": 3}] if pid == 1 else []}),
        ):
            p = patch.object(category_service, name, **kwargs)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(category_service, "browse_public_listings", return_value=([], 0))
        self.browse = p.start()
        self.addCleanup(p.stop)

    def test_tree_shape_and_cache_header(self):
        response = self.client.get("/api/categories")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "public, max-age=300")
        data = response.get_json()
        self.assertEqual([n["slug"] for n in data], ["electronics-and-technology", "other"])
        self.assertFalse(data[0]["is_selectable"])
        self.assertEqual([c["slug"] for c in data[0]["children"]], ["laptops-and-computers", "phones"])
        self.assertTrue(all(c["is_selectable"] for c in data[0]["children"]))
        self.assertTrue(data[1]["is_selectable"])

    def test_browse_parent_expands_to_children(self):
        response = self.client.get("/api/categories/electronics-and-technology/listings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(self.browse.call_args.kwargs["category_ids"]), [1, 2, 3])

    def test_browse_leaf(self):
        response = self.client.get("/api/categories/phones/listings?sort=price_desc&page=2&per_page=12")
        self.assertEqual(response.status_code, 200)
        kwargs = self.browse.call_args.kwargs
        self.assertEqual((kwargs["category_ids"], kwargs["sort"], kwargs["limit"], kwargs["offset"]),
                         ([3], "price_desc", 12, 12))
        body = response.get_json()
        self.assertEqual(set(body), {"category", "listings", "pagination"})

    def test_bad_params_never_500(self):
        for query in ("page=abc", "per_page=1000", "sort=drop%20table", "page=-4&per_page=0",
                      "page=99999999999999999999", "sort=", "per_page=1e9"):
            with self.subTest(query=query):
                response = self.client.get(f"/api/categories/phones/listings?{query}")
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                kwargs = self.browse.call_args.kwargs
                self.assertIn(kwargs["sort"], ("newest", "price_asc", "price_desc"))
                self.assertTrue(1 <= kwargs["limit"] <= 48)
                self.assertGreaterEqual(kwargs["offset"], 0)

    def test_unknown_slug_404(self):
        response = self.client.get("/api/categories/not-a-category/listings")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.get_json())

    def test_invalid_slug_rejected_before_db(self):
        with patch.object(category_service, "get_category_by_slug") as lookup:
            for slug in ("UPPER", "has_underscore", "x" * 81, "semi;colon"):
                with self.subTest(slug=slug):
                    response = self.client.get(f"/api/categories/{slug}/listings")
                    self.assertEqual(response.status_code, 404)
            lookup.assert_not_called()


@require_local_db
class TestCategoryApiOnDatabase(unittest.TestCase):
    """
    Seeds its own user/storefronts/listings (cleaned up afterwards) and checks the
    real browse SQL. Needs product_categories + listings.category_id (run the migration first).
    """

    @classmethod
    def setUpClass(cls):
        from db import get_connection
        cls.get_connection = staticmethod(get_connection)
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('product_categories') IS NOT NULL;")
        if not cur.fetchone()[0]:
            cur.close()
            conn.close()
            raise unittest.SkipTest("product_categories missing; run the migration on the local DB first.")

        cur.execute("SELECT id, slug FROM product_categories WHERE slug IN ('electronics-and-technology', 'laptops-and-computers', 'phones');")
        cls.cat = {slug: cid for cid, slug in cur.fetchall()}

        tag = uuid.uuid4().hex[:8]
        cls.tag = tag
        cur.execute("INSERT INTO users (username, password, email) VALUES (%s, 'x', %s) RETURNING id;",
                    (f"cat_api_{tag}", f"cat_api_{tag}@example.test"))
        cls.user_id = cur.fetchone()[0]
        cur.execute("INSERT INTO users (username, password, email) VALUES (%s, 'x', %s) RETURNING id;",
                    (f"cat_api2_{tag}", f"cat_api2_{tag}@example.test"))
        cls.user2_id = cur.fetchone()[0]
        cur.execute("INSERT INTO storefronts (owner_id, brand_name, is_active) VALUES (%s, %s, TRUE) RETURNING id;",
                    (cls.user_id, f"Active Shop {tag}"))
        cls.active_store = cur.fetchone()[0]
        cur.execute("INSERT INTO storefronts (owner_id, brand_name, is_active) VALUES (%s, %s, FALSE) RETURNING id;",
                    (cls.user2_id, f"Closed Shop {tag}"))
        cls.closed_store = cur.fetchone()[0]

        def listing(store, title, category, price, status="ACTIVE", qty=5, created="2026-01-01 10:00:00"):
            cur.execute("""
                INSERT INTO listings (storefront_id, title, price, fulfillment_type, quantity_on_hand,
                                      status, category_id, created_at, updated_at)
                VALUES (%s, %s, %s, 'IN_STOCK', %s, %s, %s, %s, %s) RETURNING id;
            """, (store, f"{title} {tag}", price, qty, status, category, created, created))
            return cur.fetchone()[0]

        laptops, phones = cls.cat["laptops-and-computers"], cls.cat["phones"]
        cls.ids = {
            "cheap_laptop": listing(cls.active_store, "Cheap Laptop", laptops, 100, created="2026-01-03 10:00:00"),
            "pricey_laptop": listing(cls.active_store, "Pricey Laptop", laptops, 900, created="2026-01-02 10:00:00"),
            "phone": listing(cls.active_store, "Phone", phones, 300, created="2026-01-04 10:00:00"),
            "sold_out": listing(cls.active_store, "Sold Phone", phones, 50, status="SOLD_OUT", qty=0,
                                created="2026-01-05 10:00:00"),
            "inactive": listing(cls.active_store, "Hidden", laptops, 10, status="INACTIVE"),
            "deleted": listing(cls.active_store, "Deleted", laptops, 10, status="DELETED"),
            "closed_store": listing(cls.closed_store, "Closed", laptops, 10),
        }
        for i in range(5):
            cur.execute("INSERT INTO listing_images (listing_id, image_url, is_primary) VALUES (%s, %s, %s);",
                        (cls.ids["cheap_laptop"], f"https://img.test/{i}.png", i == 2))
        cur.execute("INSERT INTO listing_sizes (listing_id, size, quantity) VALUES (%s, 'One Size', 5);",
                    (cls.ids["cheap_laptop"],))
        conn.commit()
        cur.close()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        conn = cls.get_connection()
        cur = conn.cursor()
        # Removes only the rows this test created (cascades to its listings/images/sizes)
        cur.execute("DELETE FROM users WHERE id = ANY(%s);", ([cls.user_id, cls.user2_id],))
        conn.commit()
        cur.close()
        conn.close()

    def _browse(self, slug, query=""):
        response = self.client.get(f"/api/categories/{slug}/listings?per_page=48&{query}")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        mine = [item for item in data["listings"] if item["title"].endswith(self.tag)]
        return data, mine

    def test_parent_includes_child_listings_and_excludes_hidden(self):
        _, mine = self._browse("electronics-and-technology")
        ids = {item["id"] for item in mine}
        self.assertEqual(ids, {self.ids[k] for k in ("cheap_laptop", "pricey_laptop", "phone", "sold_out")})

    def test_leaf_filters(self):
        _, mine = self._browse("phones")
        self.assertEqual({item["id"] for item in mine}, {self.ids["phone"], self.ids["sold_out"]})

    def test_sold_out_after_available(self):
        _, mine = self._browse("phones")
        self.assertEqual([item["id"] for item in mine], [self.ids["phone"], self.ids["sold_out"]])

    def test_sorts(self):
        _, newest = self._browse("laptops-and-computers")
        self.assertEqual([i["id"] for i in newest], [self.ids["cheap_laptop"], self.ids["pricey_laptop"]])
        _, asc = self._browse("laptops-and-computers", "sort=price_asc")
        self.assertEqual([i["price"] for i in asc], [100.0, 900.0])
        _, desc = self._browse("laptops-and-computers", "sort=price_desc")
        self.assertEqual([i["price"] for i in desc], [900.0, 100.0])

    def test_inline_images_sizes_storefront(self):
        _, mine = self._browse("laptops-and-computers")
        cheap = next(i for i in mine if i["id"] == self.ids["cheap_laptop"])
        self.assertEqual(len(cheap["images"]), 4)
        self.assertEqual(cheap["images"][0], "https://img.test/2.png")  # primary first
        self.assertEqual(cheap["sizes"], [{"size": "One Size", "quantity": 5}])
        self.assertEqual(cheap["storefront"]["id"], self.active_store)
        self.assertEqual(cheap["category"]["slug"], "laptops-and-computers")
        self.assertEqual(cheap["category"]["parent_slug"], "electronics-and-technology")

    def test_pagination_totals_and_past_end(self):
        response = self.client.get("/api/categories/laptops-and-computers/listings?per_page=1&page=999")
        data = response.get_json()
        self.assertEqual(data["listings"], [])
        self.assertGreaterEqual(data["pagination"]["total"], 2)
        self.assertEqual(data["pagination"]["page"], 999)


if __name__ == "__main__":
    unittest.main(verbosity=2)
