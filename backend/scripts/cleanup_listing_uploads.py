# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
scripts/cleanup_listing_uploads.py

This deletes S3 images that got uploaded for a new listing but never ended up on one.
That happens if a create failed and couldn't clean up after itself, or stopped partway through.
The image keys are saved in listing_create_requests.uploaded_keys.

How to run it (from the repo root):
    python backend/scripts/cleanup_listing_uploads.py           (dry run, just lists what it would delete)
    python backend/scripts/cleanup_listing_uploads.py --apply   (asks you to type the database name)
"""

import argparse
import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from migrations.add_listing_interest import print_target
from services.listing_create_service import STALE_AFTER


def cleanup(conn, delete_key, apply=False):
    """Returns how many leftover images it found and deleted. delete_key should return True if it worked."""
    cur = conn.cursor()
    # Skips requests that are still running, since their photos might still go on a listing
    cur.execute("""
        SELECT user_id, idempotency_key, status, uploaded_keys
        FROM listing_create_requests
        WHERE uploaded_keys <> '[]'::jsonb
          AND (status <> 'PENDING' OR updated_at < now() - %s::interval)
        ORDER BY updated_at;
    """, (STALE_AFTER,))
    found = deleted = 0
    for user_id, key, status, uploaded_keys in cur.fetchall():
        print(f"{status:8} user {user_id} request {key}: {len(uploaded_keys)} image(s)")
        found += len(uploaded_keys)
        if not apply:
            continue
        removed = [k for k in uploaded_keys if delete_key(k)]
        deleted += len(removed)
        cur.execute("""
            UPDATE listing_create_requests SET uploaded_keys = uploaded_keys - %s::text[]
            WHERE user_id = %s AND idempotency_key = %s;
        """, (removed, user_id, key))
        conn.commit()
    cur.close()
    return found, deleted


def main(argv=None):
    parser = argparse.ArgumentParser(description="Delete S3 images left by failed create listing requests.")
    parser.add_argument("--apply", action="store_true", help="Delete them (default is a dry run).")
    args = parser.parse_args(argv)

    from db import get_connection
    from utils.s3 import delete_image_from_s3

    _, name = print_target()
    if args.apply and input(f"Type the database name ({name}) to delete images: ").strip() != name:
        print("Database name did not match. Nothing was deleted.")
        return 2

    conn = get_connection()
    try:
        found, deleted = cleanup(conn, delete_image_from_s3, apply=args.apply)
    finally:
        conn.close()
    if args.apply:
        print(f"{found} leftover image(s); deleted {deleted}.")
    else:
        print(f"{found} leftover image(s); dry run, nothing deleted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
