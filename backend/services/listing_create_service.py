# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
services/listing_create_service.py

Purpose:
Creates a listing with its images and sizes all-or-nothing, and at most once per
(user, request key), so a double-clicked or retried request can't make duplicates.

Flow: claim the key -> upload images (each S3 key is recorded) -> insert listing,
images and sizes in one transaction -> mark the claim COMPLETE. On any failure the
transaction rolls back, this request's uploads are deleted, and the claim is FAILED.
uploaded_keys always lists S3 objects that aren't attached to a listing yet, which is
what scripts/cleanup_listing_uploads.py removes.
"""

import hashlib
import json
import uuid

from db import get_connection
from models import listing_model
from utils import s3

STALE_AFTER = "2 minutes"  # a PENDING claim older than this is from a request that died


class CreateError(Exception):
    """A failure with a message for the user and an HTTP status."""

    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def parse_idempotency_key(raw):
    """Returns the key as a string, None when the client didn't send one (older pages)."""
    if not raw:
        return None
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        raise CreateError("Invalid Idempotency-Key.", 400)


def _request_hash(fields, sizes, files):
    digest = hashlib.sha256(json.dumps([fields, sizes], sort_keys=True, default=str).encode())
    for file in files:
        digest.update(hashlib.sha256(file.read()).digest())
        file.seek(0)
    return digest.hexdigest()


def _claim(cur, user_id, key, request_hash):
    """Returns None when this request owns the key, or (listing, status) to send back instead."""
    cur.execute("""
        INSERT INTO listing_create_requests (user_id, idempotency_key, request_hash, status)
        VALUES (%s, %s, %s, 'PENDING')
        ON CONFLICT DO NOTHING
        RETURNING 1;
    """, (user_id, key, request_hash))
    if cur.fetchone():
        return None

    cur.execute(f"""
        SELECT request_hash, status, listing_id, updated_at < now() - interval '{STALE_AFTER}'
        FROM listing_create_requests WHERE user_id = %s AND idempotency_key = %s;
    """, (user_id, key))
    row = cur.fetchone()
    if row is None:
        raise CreateError("This listing is still being created. Please wait a moment.", 409)
    saved_hash, status, listing_id, stale = row

    if saved_hash != request_hash:
        raise CreateError("This request key was already used for a different listing.", 422)
    if status == "COMPLETE":
        listing = listing_model.get_listing_by_id(listing_id) if listing_id else None
        if listing is None:
            raise CreateError("This listing was already created and has since been removed.", 409)
        return listing, 200

    # FAILED, or PENDING from a request that died: take it over (only one request can win)
    cur.execute(f"""
        UPDATE listing_create_requests
        SET status = 'PENDING', error = NULL, updated_at = now()
        WHERE user_id = %s AND idempotency_key = %s
          AND (status = 'FAILED' OR (status = 'PENDING' AND updated_at < now() - interval '{STALE_AFTER}'))
        RETURNING 1;
    """, (user_id, key))
    if cur.fetchone() is None:
        raise CreateError("This listing is still being created. Please wait a moment.", 409)
    return None


def _insert_all(conn, fields, image_urls, sizes, claim):
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            listing = listing_model.insert_listing(cur, **fields)
            for index, url in enumerate(image_urls):
                listing_model.insert_listing_image(cur, listing["id"], url, is_primary=(index == 0))
            for size, quantity in sizes:
                listing_model.insert_listing_size(cur, listing["id"], size, quantity)
            if claim:
                used = [s3.key_from_url(url) for url in image_urls]
                cur.execute("""
                    UPDATE listing_create_requests
                    SET status = 'COMPLETE', listing_id = %s, uploaded_keys = uploaded_keys - %s::text[],
                        updated_at = now()
                    WHERE user_id = %s AND idempotency_key = %s;
                """, (listing["id"], used, *claim))
        conn.commit()
        return listing
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = True


def create_listing_once(user_id, key, fields, sizes, files):
    """
    fields: build_listing_fields() output; sizes: [(size, quantity)]; files: uploaded images,
    first is primary. Returns (listing, http_status). Raises CreateError or the original error.
    """
    claim = (user_id, key) if key else None
    conn = get_connection()
    conn.autocommit = True  # claim and upload records are saved right away
    try:
        with conn.cursor() as cur:
            if claim:
                replay = _claim(cur, user_id, key, _request_hash(fields, sizes, files))
                if replay:
                    return replay

            image_urls = []
            try:
                for number, file in enumerate(files, start=1):
                    url = s3.upload_image_to_s3(file, folder="listings")
                    if not url:
                        raise CreateError(f"Image {number} couldn't be uploaded. Nothing was saved; please try again.", 500)
                    image_urls.append(url)
                    if claim:
                        cur.execute("""
                            UPDATE listing_create_requests
                            SET uploaded_keys = uploaded_keys || jsonb_build_array(%s::text), updated_at = now()
                            WHERE user_id = %s AND idempotency_key = %s;
                        """, (s3.key_from_url(url), *claim))
                return _insert_all(conn, fields, image_urls, sizes, claim), 201
            except Exception as error:
                deleted = [k for k in (s3.key_from_url(url) for url in image_urls) if s3.delete_image_from_s3(k)]
                if claim:
                    cur.execute("""
                        UPDATE listing_create_requests
                        SET status = 'FAILED', error = %s, uploaded_keys = uploaded_keys - %s::text[],
                            updated_at = now()
                        WHERE user_id = %s AND idempotency_key = %s;
                    """, (str(error)[:500], deleted, *claim))
                raise
    finally:
        conn.close()
