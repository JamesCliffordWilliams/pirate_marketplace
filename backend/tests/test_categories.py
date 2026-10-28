# Created by James Williams - 10/26/26 - product categories, category pages and the category rule on new listings

import io
import os
import sys
import unittest
from unittest.mock import patch

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path += [os.path.dirname(BACKEND_ROOT), BACKEND_ROOT]

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema
from app import create_app
from config.product_categories import PRODUCT_CATEGORIES


class TestCategoryList(unittest.TestCase):

    def test_twelve_main_categories(self):
        self.assertEqual(len(PRODUCT_CATEGORIES), 12)


@require_local_db
class TestCategoriesOnDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = ThrowawaySchema(prefix="test_cats").create()
        cls.client = create_app().test_client()
        with cls.client.session_transaction() as sess:
            sess["user"] = "shopper"

    @classmethod
    def tearDownClass(cls):
        cls.db.drop()

    def test_category_page_and_not_found(self):
        self.assertEqual(self.client.get("/categories/electronics-and-technology").status_code, 200)
        response = self.client.get("/categories/nope")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Category not found", response.get_data(as_text=True))

    def test_new_listing_needs_a_category(self):
        owner = self.db.owner_of(self.db.add_storefront())
        # This leaves out category_id on purpose
        data = {"title": "Hoodie", "price": "25", "sizes_available": '["M"]',
                "listing_images": (io.BytesIO(b"photo"), "p.jpg")}
        with patch("utils.s3.upload_image_to_s3") as upload:
            response = self.client.post("/api/listings/create", data=data, headers={"X-User-Id": str(owner)},
                                        content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Please choose a category.")
        upload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
