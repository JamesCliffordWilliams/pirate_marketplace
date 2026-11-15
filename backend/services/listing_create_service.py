# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
services/listing_create_service.py

Saves the listing, its photos and sizes all at once, so it either all saves or nothing does.
Each request has a key so a double click or a retry can't make two listings.

First it claims the key, then uploads the photos, then saves everything and marks the request COMPLETE.
If something fails, nothing is saved, the uploaded photos get deleted and the request is marked FAILED.
Any photos that are uploaded but not on a listing yet are kept in uploaded_keys,
and scripts/cleanup_listing_uploads.py deletes those later.
"""

import hashlib
import json
import uuid

from db import get_connection
from models import listing_model
from utils import s3

STALE_AFTER = "2 minutes"  # if a PENDING request is older than this, it probably crashed

STILL_RUNNING = "This listing is still being created. Please wait a moment."


class CreateError(Exception):
    """An error with a message for the user and an HTTP status code."""

    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def parse_idempotency_key(raw):
    """Returns the key as a string, or None if the page didn't send one."""
    if not raw:
        return None
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        raise CreateError("Invalid Idempotency-Key.", 400)


def _request_hash(fields, sizes, files):
    """Makes a fingerprint of the form and photos so we can tell if a key gets reused for something else."""
    digest = hashlib.sha256(json.dumps([fields, sizes], sort_keys=True, default=str).encode())
    for file in files:
        digest.update(hashlib.sha256(file.read()).digest())
        file.seek(0)
    return digest.hexdigest()


def _claim(cur, user_id, key, request_hash):
    """Returns None if this request gets the key. Otherwise returns the listing and status to send back."""
    cur.execute("""
        INSERT INTO listing_create_requests (user_id, idempotency_key, request_hash, status)
        VALUES (%s, %s, %s, 'PENDING')
        ON CONFLICT DO NOTHING
        RETURNING 1;
    """, (user_id, key, request_hash))
    if cur.fetchone():
        return None

    cur.execute("""
        SELECT request_hash, status, listing_id
        FROM listing_create_requests WHERE user_id = %s AND idempotency_key = %s;
    """, (user_id, key))
    row = cur.fetchone()
    if row is None:
        raise CreateError(STILL_RUNNING, 409)
    saved_hash, status, listing_id = row

    if saved_hash != request_hash:
        raise CreateError("This request key was already used for a different listing.", 422)
    if status == "COMPLETE":
        listing = listing_model.get_listing_by_id(listing_id) if listing_id else None
        if listing is None:
            raise CreateError("This listing was already created and has since been removed.", 409)
        return listing, 200

    # If the old request FAILED or crashed, this one takes over. Only one request can do this
    cur.execute("""
        UPDATE listing_create_requests
        SET status = 'PENDING', error = NULL, updated_at = now()
        WHERE user_id = %s AND idempotency_key = %s
          AND (status = 'FAILED' OR (status = 'PENDING' AND updated_at < now() - %s::interval))
        RETURNING 1;
    """, (user_id, key, STALE_AFTER))
    if cur.fetchone() is None:
        raise CreateError(STILL_RUNNING, 409)
    return None


def _save_listing(conn, user_id, key, fields, image_urls, sizes):
    """Saves the listing, photos and sizes in one transaction and marks the request COMPLETE."""
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            listing = listing_model.insert_listing(cur, **fields)
            for index, url in enumerate(image_urls):
                listing_model.insert_listing_image(cur, listing["id"], url, is_primary=(index == 0))
            for size, quantity in sizes:
                listing_model.insert_listing_size(cur, listing["id"], size, quantity)
            if key:
                # These photos are on the listing now, so the cleanup script should leave them alone
                used = [s3.key_from_url(url) for url in image_urls]
                cur.execute("""
                    UPDATE listing_create_requests
                    SET status = 'COMPLETE', listing_id = %s, uploaded_keys = uploaded_keys - %s::text[],
                        updated_at = now()
                    WHERE user_id = %s AND idempotency_key = %s;
                """, (listing["id"], used, user_id, key))
        conn.commit()
        return listing
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = True


def create_listing_once(user_id, key, fields, sizes, files):
    """
    Creates the listing once and returns (listing, http_status).
    fields comes from build_listing_fields(), sizes is a list of (size, quantity), and the first file is the main photo.
    """
    conn = get_connection()
    conn.autocommit = True  # saves the claim and each upload right away
    try:
        with conn.cursor() as cur:
            if key:
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
                    if key:
                        # Remembers the photo so the cleanup script can find it if we crash
                        cur.execute("""
                            UPDATE listing_create_requests
                            SET uploaded_keys = uploaded_keys || jsonb_build_array(%s::text), updated_at = now()
                            WHERE user_id = %s AND idempotency_key = %s;
                        """, (s3.key_from_url(url), user_id, key))
                return _save_listing(conn, user_id, key, fields, image_urls, sizes), 201
            except Exception as error:
                # Deletes the photos we uploaded. Any that don't delete stay in uploaded_keys for the cleanup script
                uploaded_keys = [s3.key_from_url(url) for url in image_urls]
                deleted = [k for k in uploaded_keys if s3.delete_image_from_s3(k)]
                if key:
                    cur.execute("""
                        UPDATE listing_create_requests
                        SET status = 'FAILED', error = %s, uploaded_keys = uploaded_keys - %s::text[],
                            updated_at = now()
                        WHERE user_id = %s AND idempotency_key = %s;
                    """, (str(error)[:500], deleted, user_id, key))
                raise
    finally:
        conn.close()
