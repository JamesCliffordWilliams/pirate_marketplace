# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - create listing: one listing per request key, all-or-nothing
#
# Runs in a throwaway schema on a local database with S3 stubbed.

import io
import os
import sys
import threading
import time
import unittest
import uuid
from unittest.mock import patch

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, '..'))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema


class FakeS3:
    """Stands in for utils.s3: records uploads and deletes, can fail on the Nth upload."""

    def __init__(self, fail_on=None, delay=0):
        self.fail_on = fail_on
        self.delay = delay
        self.uploaded = []
        self.deleted = []
        self.lock = threading.Lock()

    def upload(self, file, folder="uploads"):
        file.read()
        time.sleep(self.delay)
        with self.lock:
            if self.fail_on is not None and len(self.uploaded) + 1 == self.fail_on:
                return None
            key = f"{folder}/{uuid.uuid4().hex}.jpg"
            self.uploaded.append(key)
        return f"https://bucket.s3.us-east-2.amazonaws.com/{key}"

    def delete(self, key):
        with self.lock:
            self.deleted.append(key)
        return True


@require_local_db
class TestListingCreateIdempotency(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = ThrowawaySchema(prefix="test_create").create()
        from app import create_app
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.storefront_id = cls.db.add_storefront()
        cls.user_id = cls.db.owner_of(cls.storefront_id)
        cls.category_id = cls.db.scalar(
            "SELECT id FROM product_categories WHERE slug = 'laptops-and-computers';"
        )

    @classmethod
    def tearDownClass(cls):
        cls.db.drop()

    def setUp(self):
        self.db.execute("DELETE FROM listing_create_requests;")
        self.db.execute("DELETE FROM listings;")
        self.use_s3(FakeS3())

    def use_s3(self, fake):
        self.s3 = fake
        for name, fn in (("upload_image_to_s3", fake.upload), ("delete_image_from_s3", fake.delete)):
            patcher = patch(f"utils.s3.{name}", side_effect=fn)
            patcher.start()
            self.addCleanup(patcher.stop)

    def post(self, key=None, images=1, title="Hoodie", client=None):
        data = {
            "title": title,
            "price": "25",
            "quantity_on_hand": "3",
            "fulfillment_type": "IN_STOCK",
            "status": "ACTIVE",
            "sizes_available": '["S", "M"]',
            "size_quantities": '{"S": 1, "M": 2}',
            "category_id": str(self.category_id),
            "listing_images": [(io.BytesIO(b"photo-%d" % n), f"p{n}.jpg") for n in range(images)],
        }
        headers = {"X-User-Id": str(self.user_id)}
        if key:
            headers["Idempotency-Key"] = key
        return (client or self.app.test_client()).post(
            "/api/listings/create", data=data, headers=headers, content_type="multipart/form-data"
        )

    def count(self, table):
        return self.db.scalar(f"SELECT COUNT(*) FROM {table};")

    def claim(self, key):
        rows = self.db.execute(
            "SELECT status, uploaded_keys, listing_id FROM listing_create_requests WHERE idempotency_key = %s;",
            (key,),
        )
        return rows[0] if rows else None

    # ---------- tests ----------

    def test_same_key_twice_creates_one_listing(self):
        key = str(uuid.uuid4())
        first = self.post(key)
        second = self.post(key)
        self.assertEqual(first.status_code, 201, first.get_data(as_text=True))
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        self.assertEqual(first.get_json()["id"], second.get_json()["id"])
        self.assertEqual(self.count("listings"), 1)
        self.assertEqual(len(self.s3.uploaded), 1)
        self.assertEqual(self.claim(key)[0], "COMPLETE")

    def test_creates_listing_images_and_sizes_together(self):
        response = self.post(str(uuid.uuid4()), images=3)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        listing_id = response.get_json()["id"]
        self.assertEqual(self.db.execute(
            "SELECT is_primary FROM listing_images WHERE listing_id = %s ORDER BY id;", (listing_id,)
        ), [(True,), (False,), (False,)])
        self.assertEqual(self.db.execute(
            "SELECT size, quantity FROM listing_sizes WHERE listing_id = %s ORDER BY size;", (listing_id,)
        ), [("M", 2), ("S", 1)])

    def test_concurrent_same_key_creates_one_listing(self):
        self.use_s3(FakeS3(delay=0.4))
        key = str(uuid.uuid4())
        results = []

        def send():
            results.append(self.post(key).status_code)

        threads = [threading.Thread(target=send) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(results), [201, 409, 409])
        self.assertEqual(self.count("listings"), 1)

    def test_same_key_different_request_is_rejected(self):
        key = str(uuid.uuid4())
        self.assertEqual(self.post(key, title="Hoodie").status_code, 201)
        response = self.post(key, title="Jacket")
        self.assertEqual(response.status_code, 422, response.get_data(as_text=True))
        self.assertEqual(self.count("listings"), 1)

    def test_new_key_with_same_data_creates_second_listing(self):
        self.assertEqual(self.post(str(uuid.uuid4())).status_code, 201)
        self.assertEqual(self.post(str(uuid.uuid4())).status_code, 201)
        self.assertEqual(self.count("listings"), 2)

    def test_s3_failure_on_third_image_saves_nothing(self):
        self.use_s3(FakeS3(fail_on=3))
        key = str(uuid.uuid4())
        response = self.post(key, images=4)
        self.assertEqual(response.status_code, 500, response.get_data(as_text=True))
        self.assertEqual(self.count("listings"), 0)
        self.assertEqual(sorted(self.s3.deleted), sorted(self.s3.uploaded))
        self.assertEqual(len(self.s3.uploaded), 2)
        status, uploaded_keys, _ = self.claim(key)
        self.assertEqual((status, uploaded_keys), ("FAILED", []))

    def test_database_failure_after_uploads_rolls_back_and_cleans_up(self):
        key = str(uuid.uuid4())
        with patch("models.listing_model.insert_listing_size", side_effect=RuntimeError("db down")):
            response = self.post(key, images=2)
        self.assertEqual(response.status_code, 500, response.get_data(as_text=True))
        self.assertEqual(self.count("listings"), 0)
        self.assertEqual(self.count("listing_images"), 0)
        self.assertEqual(sorted(self.s3.deleted), sorted(self.s3.uploaded))
        self.assertEqual(self.claim(key)[0], "FAILED")

    def test_failed_key_can_be_retried(self):
        self.use_s3(FakeS3(fail_on=1))
        key = str(uuid.uuid4())
        self.assertEqual(self.post(key).status_code, 500)
        self.use_s3(FakeS3())
        self.assertEqual(self.post(key).status_code, 201)
        self.assertEqual(self.count("listings"), 1)

    def leave_pending(self, key, minutes_ago):
        """A claim for this exact request, left PENDING by a request that stopped."""
        self.use_s3(FakeS3(fail_on=1))
        self.assertEqual(self.post(key).status_code, 500)
        self.db.execute("""
            UPDATE listing_create_requests
            SET status = 'PENDING', updated_at = now() - make_interval(mins => %s)
            WHERE idempotency_key = %s;
        """, (minutes_ago, key))
        self.use_s3(FakeS3())

    def test_stale_pending_claim_is_taken_over(self):
        key = str(uuid.uuid4())
        self.leave_pending(key, minutes_ago=10)
        response = self.post(key)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertEqual(self.claim(key)[0], "COMPLETE")

    def test_fresh_pending_claim_asks_client_to_retry(self):
        key = str(uuid.uuid4())
        self.leave_pending(key, minutes_ago=0)
        response = self.post(key)
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertEqual(self.count("listings"), 0)

    def test_request_without_key_still_works(self):
        response = self.post(None, images=2)
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertEqual(self.count("listings"), 1)
        self.assertEqual(self.count("listing_create_requests"), 0)

    def test_bad_key_is_rejected_before_upload(self):
        response = self.post("not-a-uuid")
        self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
        self.assertEqual(self.s3.uploaded, [])

    def test_invalid_price_is_rejected_before_upload(self):
        response = self.app.test_client().post("/api/listings/create", data={
            "title": "Hoodie", "price": "-1", "sizes_available": '["S"]',
            "category_id": str(self.category_id),
            "listing_images": [(io.BytesIO(b"x"), "p.jpg")],
        }, headers={"X-User-Id": str(self.user_id)}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
        self.assertEqual(self.s3.uploaded, [])

    def test_oversized_request_gets_clear_413(self):
        self.app.config["MAX_CONTENT_LENGTH"], old = 1024, self.app.config.get("MAX_CONTENT_LENGTH")
        try:
            response = self.app.test_client().post("/api/listings/create", data={
                "listing_images": [(io.BytesIO(b"x" * 4096), "p.jpg")],
            }, headers={"X-User-Id": str(self.user_id)}, content_type="multipart/form-data")
        finally:
            self.app.config["MAX_CONTENT_LENGTH"] = old
        self.assertEqual(response.status_code, 413)
        self.assertIn("too large", response.get_json()["error"])


    def test_cleanup_script_removes_only_finished_leftovers(self):
        from scripts.cleanup_listing_uploads import cleanup
        failed, running = str(uuid.uuid4()), str(uuid.uuid4())
        self.db.execute("""
            INSERT INTO listing_create_requests (user_id, idempotency_key, request_hash, status, uploaded_keys)
            VALUES (%s, %s, 'h', 'FAILED', '["listings/a.jpg", "listings/b.jpg"]'),
                   (%s, %s, 'h', 'PENDING', '["listings/c.jpg"]');
        """, (self.user_id, failed, self.user_id, running))
        conn = self.db.connect()
        try:
            self.assertEqual(cleanup(conn, self.s3.delete), (2, 0))
            self.assertEqual(self.s3.deleted, [])
            self.assertEqual(cleanup(conn, self.s3.delete, apply=True), (2, 2))
        finally:
            conn.close()
        self.assertEqual(sorted(self.s3.deleted), ["listings/a.jpg", "listings/b.jpg"])
        self.assertEqual(self.claim(failed)[1], [])
        self.assertEqual(self.claim(running)[1], ["listings/c.jpg"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
