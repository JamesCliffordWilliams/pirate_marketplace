# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - category checks on create/update listing
# Updated by James Williams - 10/26/26 - mocks the one-transaction create
#
# Runs without a database or S3: the storefront lookup, category lookup,
# model writes and utils.s3.upload_image_to_s3 are all mocked.

import io
import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from app import create_app
from controllers import listing_controller
from services import category_service, listing_service
import utils.s3

CATEGORIES = {
    1: {"id": 1, "slug": "electronics-and-technology", "name": "Electronics & Technology", "parent_id": None,
        "is_active": True, "child_count": 2},
    2: {"id": 2, "slug": "laptops-and-computers", "name": "Laptops & Computers", "parent_id": 1,
        "is_active": True, "child_count": 0},
    5: {"id": 5, "slug": "retired", "name": "Retired", "parent_id": 1, "is_active": False, "child_count": 0},
    9: {"id": 9, "slug": "other", "name": "Other", "parent_id": None, "is_active": True, "child_count": 0},
}

OWNER_ID = 7
STOREFRONT = {"id": 5, "owner_id": OWNER_ID, "brand_name": "Shop", "is_active": True}


class TestCreateListingRouteCategory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        self.created = []
        patches = [
            patch.object(listing_controller, "get_my_storefront_service", return_value=STOREFRONT),
            patch.object(category_service, "get_category_by_id", side_effect=CATEGORIES.get),
            patch.object(listing_service, "get_storefront_by_id", return_value=STOREFRONT),
            patch.object(listing_service, "create_listing", side_effect=self._fake_create),
            patch.object(listing_service, "get_listing_by_id",
                         side_effect=lambda listing_id: {"id": listing_id, "storefront_id": 5}),
            patch.object(listing_service, "get_images_for_listing", return_value=[]),
            patch.object(listing_service, "add_listing_image", return_value={}),
            patch.object(listing_service, "upsert_listing_size", return_value={}),
            # Updated by James Williams 10/26/26 - the form route saves through create_listing_once
            patch.object(listing_controller, "create_listing_once", side_effect=self._fake_create_once),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        upload = patch.object(utils.s3, "upload_image_to_s3", return_value="https://s3.test/img.png")
        self.upload = upload.start()
        self.addCleanup(upload.stop)

    def _fake_create(self, **kwargs):
        self.created.append(kwargs)
        return {"id": 101, **kwargs}

    def _fake_create_once(self, user_id, key, fields, sizes, files):
        for file in files:
            utils.s3.upload_image_to_s3(file, folder="listings")
        return self._fake_create(**fields), 201

    def _post(self, **fields):
        data = {
            "title": "MacBook Air",
            "price": "500",
            "quantity_on_hand": "1",
            "fulfillment_type": "IN_STOCK",
            "status": "ACTIVE",
            "sizes_available": '["One Size"]',
            "size_quantities": '{"One Size": 1}',
            "listing_images": (io.BytesIO(b"fake image bytes"), "laptop.png"),
        }
        data.update(fields)
        data = {k: v for k, v in data.items() if v is not None}
        return self.client.post(
            "/api/listings/create",
            data=data,
            headers={"X-User-Id": str(OWNER_ID)},
            content_type="multipart/form-data",
        )

    def test_invalid_categories_return_400_without_s3_upload(self):
        cases = {
            "missing": (None, "Please choose a category."),
            "empty": ("", "Please choose a category."),
            "parent": ("1", "Choose a specific subcategory, not a main category."),
            "nonexistent": ("999", "That category doesn't exist."),
            "inactive": ("5", "That category doesn't exist."),
            "string": ("laptops", "That category doesn't exist."),
            "negative": ("-2", "That category doesn't exist."),
            "bool-ish": ("true", "That category doesn't exist."),
            "float": ("2.0", "That category doesn't exist."),
        }
        for label, (value, message) in cases.items():
            with self.subTest(label):
                self.upload.reset_mock()
                response = self._post(category_id=value)
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
                self.assertEqual(response.get_json()["error"], message)
                self.upload.assert_not_called()
        self.assertEqual(self.created, [])

    def test_valid_category_creates_listing_with_it(self):
        response = self._post(category_id="2")
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.upload.assert_called_once()
        self.assertEqual(self.created[0]["category_id"], 2)
        self.assertEqual(response.get_json()["category_id"], 2)

    def test_other_is_valid(self):
        response = self._post(category_id="9")
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertEqual(self.created[0]["category_id"], 9)

    def test_json_create_route_requires_category(self):
        response = self.client.post(
            "/api/storefronts/5/listings",
            json={"title": "Thing", "price": 5, "fulfillment_type": "IN_STOCK", "quantity_on_hand": 1},
            headers={"X-User-Id": str(OWNER_ID)},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Please choose a category.")

        response = self.client.post(
            "/api/storefronts/5/listings",
            json={"title": "Thing", "price": 5, "fulfillment_type": "IN_STOCK", "quantity_on_hand": 1,
                  "category_id": 2},
            headers={"X-User-Id": str(OWNER_ID)},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertEqual(self.created[-1]["category_id"], 2)


class TestUpdateListingRouteCategory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        self.listing = {"id": 50, "storefront_id": 5, "title": "Mac", "fulfillment_type": "IN_STOCK",
                        "quantity_on_hand": 2, "status": "INACTIVE", "is_made_to_order": False, "category_id": 9}
        self.updates = []
        for target, kwargs in (
            ("get_storefront_by_id", {"return_value": STOREFRONT}),
            ("get_listing_by_id", {"side_effect": lambda _id: dict(self.listing)}),
            ("update_listing", {"side_effect": self._fake_update}),
        ):
            p = patch.object(listing_service, target, **kwargs)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(category_service, "get_category_by_id", side_effect=CATEGORIES.get)
        p.start()
        self.addCleanup(p.stop)

    def _fake_update(self, **kwargs):
        self.updates.append(kwargs)
        return {**self.listing, **{k: v for k, v in kwargs.items() if v is not None}, "id": 50}

    def _put(self, body, user_id=OWNER_ID):
        return self.client.put("/api/listings/50", json=body, headers={"X-User-Id": str(user_id)})

    def test_put_parent_category_is_400(self):
        response = self._put({"category_id": 1})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Choose a specific subcategory, not a main category.")
        self.assertEqual(self.updates, [])

    def test_put_null_category_is_400(self):
        response = self._put({"category_id": None})
        self.assertEqual(response.status_code, 400)

    def test_put_leaf_category(self):
        response = self._put({"category_id": 2, "quantity_on_hand": 2})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(self.updates[-1]["category_id"], 2)

    def test_put_without_category_is_unchanged(self):
        response = self._put({"title": "Renamed"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.updates[-1]["category_id"])

    def test_edit_page_payload_keeps_inactive_listing_inactive(self):
        # what the old edit page sent: always status ACTIVE
        response = self._put({"title": "Mac", "price": 10, "quantity_on_hand": 2, "fulfillment_type": "IN_STOCK",
                              "status": "ACTIVE", "sizes_available": ["M"], "is_made_to_order": False,
                              "category_id": 9})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.updates[-1]["status"])
        self.assertEqual(response.get_json()["status"], "INACTIVE")

    def test_non_owner_cannot_change_category(self):
        response = self._put({"category_id": 2}, user_id=999)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.updates, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
