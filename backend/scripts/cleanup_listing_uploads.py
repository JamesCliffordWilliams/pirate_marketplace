# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
scripts/cleanup_listing_uploads.py

Purpose:
Deletes S3 images that a create listing request uploaded but never attached to a
listing (the request failed and its own cleanup couldn't delete them, or it stopped
mid-way). They are tracked in listing_create_requests.uploaded_keys.

Usage (from the repo root):
    python backend/scripts/cleanup_listing_uploads.py           (dry run: lists what it would delete)
    python backend/scripts/cleanup_listing_uploads.py --apply   (asks you to type the database name)
"""

import argparse
import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from migrations.add_listing_interest import _print_target
from services.listing_create_service import STALE_AFTER

FIND_LEFTOVERS = f"""
    SELECT user_id, idempotency_key, status, uploaded_keys
    FROM listing_create_requests
    WHERE uploaded_keys <> '[]'::jsonb
      AND (status <> 'PENDING' OR updated_at < now() - interval '{STALE_AFTER}')
    ORDER BY updated_at;
"""


def cleanup(conn, delete_key, apply=False):
    """Returns (found, deleted) key counts. delete_key(key) -> bool."""
    cur = conn.cursor()
    cur.execute(FIND_LEFTOVERS)
    rows = cur.fetchall()
    found = deleted = 0
    for user_id, key, status, uploaded_keys in rows:
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

    _, name = _print_target()
    if args.apply and input(f"Type the database name ({name}) to delete images: ").strip() != name:
        print("Database name did not match. Nothing was deleted.")
        return 2

    conn = get_connection()
    try:
        found, deleted = cleanup(conn, delete_image_from_s3, apply=args.apply)
    finally:
        conn.close()
    print(f"{found} leftover image(s); {'deleted ' + str(deleted) if args.apply else 'dry run, nothing deleted'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
