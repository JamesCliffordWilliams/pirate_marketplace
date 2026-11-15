# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
migrations/add_listing_create_requests.py

This adds the listing_create_requests table so retrying "create listing" can't make two listings.
It only adds a new table and doesn't change any existing ones.
If anything fails, nothing gets changed.

How to run it (from the repo root):
    python backend/migrations/add_listing_create_requests.py --dry-run   (test run, undoes itself)
    python backend/migrations/add_listing_create_requests.py

It shows which database it will use and asks you to type the database name first.
"""

import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from migrations.add_listing_interest import run_in_one_transaction, run_from_command_line

CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS listing_create_requests (
        user_id INTEGER NOT NULL,
        idempotency_key UUID NOT NULL,
        request_hash TEXT NOT NULL,
        status TEXT NOT NULL
            CONSTRAINT listing_create_requests_status_check
                CHECK (status IN ('PENDING', 'COMPLETE', 'FAILED')),
        listing_id INTEGER NULL
            CONSTRAINT fk_listing_create_requests_listing
                REFERENCES listings(id) ON DELETE SET NULL,
        uploaded_keys JSONB NOT NULL DEFAULT '[]',
        error TEXT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (user_id, idempotency_key)
    );
"""

# This helps the cleanup script find unfinished requests quickly
CREATE_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_listing_create_requests_unfinished
        ON listing_create_requests (updated_at) WHERE status <> 'COMPLETE';
"""


def apply_listing_create_requests(cur):
    """Creates the table and its index. It's safe to run more than once and it doesn't commit."""
    cur.execute("SELECT to_regclass('listing_create_requests') IS NULL;")
    table_created = cur.fetchone()[0]
    cur.execute(CREATE_TABLE)
    cur.execute(CREATE_INDEX)
    return {"table_created": table_created}


def run_migration(conn, dry_run=False):
    """Runs the migration and returns a summary. With dry_run=True it undoes everything at the end."""
    return run_in_one_transaction(conn, apply_listing_create_requests, dry_run)


if __name__ == "__main__":
    sys.exit(run_from_command_line("Add the listing_create_requests table.", run_migration))
