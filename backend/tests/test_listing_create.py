# Created by James Williams - 10/26/26 - one listing per request key, and nothing saved if a photo upload fails

import io
import os
import sys
import unittest
import uuid
from unittest.mock import patch

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path += [os.path.dirname(BACKEND_ROOT), BACKEND_ROOT]

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema


@require_local_db
class TestListingCreate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = ThrowawaySchema(prefix="test_create").create()
        from app import create_app
        cls.client = create_app().test_client()
        cls.owner = cls.db.owner_of(cls.db.add_storefront())
        cls.category = cls.db.scalar("SELECT id FROM product_categories WHERE slug = 'phones';")

    @classmethod
    def tearDownClass(cls):
        cls.db.drop()

    def setUp(self):
        self.db.execute("DELETE FROM listings;")
        self.uploaded, self.deleted = [], []

    def fake_upload(self, file, folder="uploads"):
        self.uploaded.append(f"{folder}/{uuid.uuid4().hex}.jpg")
        return f"https://bucket.s3.amazonaws.com/{self.uploaded[-1]}"

    def post(self, key, images=1, upload=None):
        data = {"title": "Hoodie", "price": "25", "sizes_available": '["M"]', "size_quantities": '{"M": 2}',
                "category_id": str(self.category),
                "listing_images": [(io.BytesIO(b"photo"), f"p{n}.jpg") for n in range(images)]}
        with patch("utils.s3.upload_image_to_s3", side_effect=upload or self.fake_upload), \
             patch("utils.s3.delete_image_from_s3", side_effect=self.deleted.append):
            return self.client.post("/api/listings/create", data=data, content_type="multipart/form-data",
                                    headers={"X-User-Id": str(self.owner), "Idempotency-Key": key})

    def count_listings(self):
        return self.db.scalar("SELECT COUNT(*) FROM listings;")

    def test_same_key_twice_makes_one_listing(self):
        key = str(uuid.uuid4())
        first, second = self.post(key), self.post(key)
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.get_json()["id"], second.get_json()["id"])
        self.assertEqual(self.count_listings(), 1)

    def test_failed_upload_saves_nothing(self):
        # This makes the second photo fail to upload
        def flaky_upload(file, folder="uploads"):
            return self.fake_upload(file, folder) if not self.uploaded else None

        response = self.post(str(uuid.uuid4()), images=2, upload=flaky_upload)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.count_listings(), 0)
        self.assertEqual(self.deleted, self.uploaded)  # the photo that did upload gets cleaned up


if __name__ == "__main__":
    unittest.main()
