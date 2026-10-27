# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
migrations/add_listing_create_requests.py

Purpose:
Adds the listing_create_requests table, which makes "create listing" safe to
retry: one listing per (user, request key). New table only; no existing table
is changed. Runs in one transaction, so it either all works or nothing changes.

Usage (from the repo root):
    python backend/migrations/add_listing_create_requests.py --dry-run   (test run, undoes itself)
    python backend/migrations/add_listing_create_requests.py

It shows which database it will use and asks you to type the database name first.
"""

import argparse
import json
import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# Same safety checks as the Hot migration
from migrations.add_listing_interest import LOCAL_DB_HOSTS, _print_target, _table_counts

ADVISORY_LOCK_KEY = 405202612
TABLE = "listing_create_requests"

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

# Lets the orphan cleanup find unfinished requests quickly
CREATE_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_listing_create_requests_unfinished
        ON listing_create_requests (updated_at) WHERE status <> 'COMPLETE';
"""


def apply_listing_create_requests(cur):
    """Creates the table and its index. Safe to run more than once. Does not commit."""
    cur.execute("SELECT to_regclass(%s) IS NOT NULL;", (TABLE,))
    table_created = not cur.fetchone()[0]
    cur.execute(CREATE_TABLE)
    cur.execute(CREATE_INDEX)
    return {"table_created": table_created}


def _other_tables_fingerprint(cur):
    cur.execute("""
        SELECT md5(COALESCE(string_agg(
                   table_name || '.' || column_name || ':' || data_type || ':' || is_nullable
                   || ':' || COALESCE(column_default, ''),
                   ',' ORDER BY table_name, ordinal_position), ''))
        FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name <> %s;
    """, (TABLE,))
    return cur.fetchone()[0]


def run_migration(conn, dry_run=False):
    """Runs the migration in one transaction. dry_run=True undoes it at the end. Returns a summary."""
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;")
        cur.execute("SET LOCAL lock_timeout = '5s';")
        cur.execute("SELECT pg_advisory_xact_lock(%s);", (ADVISORY_LOCK_KEY,))

        counts_before, fingerprint_before = _table_counts(cur), _other_tables_fingerprint(cur)
        applied = apply_listing_create_requests(cur)
        counts_after, fingerprint_after = _table_counts(cur), _other_tables_fingerprint(cur)

        failures = []
        if counts_before != counts_after:
            failures.append(f"Row counts changed: before={counts_before} after={counts_after}")
        if fingerprint_before != fingerprint_after:
            failures.append("Columns of existing tables changed.")
        cur.execute("SELECT to_regclass(%s) IS NOT NULL;", (TABLE,))
        if not cur.fetchone()[0]:
            failures.append(f"{TABLE} was not created.")
        if failures:
            raise RuntimeError("Verification failed; rolled back. " + " | ".join(failures))

        if dry_run:
            conn.rollback()
            outcome = "rolled back (dry run) - nothing was changed"
        else:
            conn.commit()
            outcome = "committed"
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

    return {"outcome": outcome, "dry_run": dry_run, **applied,
            "counts_before": counts_before, "counts_after": counts_after}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Add the listing_create_requests table.")
    parser.add_argument("--dry-run", action="store_true", help="Run everything, print the summary, then ROLLBACK.")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt (local databases only).")
    args = parser.parse_args(argv)

    from db import get_connection

    host, name = _print_target()
    print(f"Mode: {'DRY RUN (will roll back)' if args.dry_run else 'APPLY (will commit)'}")

    if args.yes:
        if host.strip().lower() not in LOCAL_DB_HOSTS:
            print("Refusing --yes for a non-local database. Re-run without --yes and confirm interactively.")
            return 2
    elif input(f"Type the database name ({name}) to continue: ").strip() != name:
        print("Database name did not match. Aborted; nothing was changed.")
        return 2

    conn = get_connection()
    try:
        summary = run_migration(conn, dry_run=args.dry_run)
    except Exception as e:
        print(f"MIGRATION FAILED - rolled back, nothing was changed: {e}")
        return 1
    finally:
        conn.close()

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
