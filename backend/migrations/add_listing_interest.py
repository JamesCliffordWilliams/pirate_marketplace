# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
migrations/add_listing_interest.py

Purpose:
Adds the listing_interest table used by the Hot page. New table only;
no existing table is changed and nothing is backfilled. Runs in one
transaction, so it either all works or nothing changes.

Usage (from the repo root):
    python backend/migrations/add_listing_interest.py --dry-run   (test run, undoes itself)
    python backend/migrations/add_listing_interest.py

It shows which database it will use and asks you to type the database name first.
"""

import argparse
import json
import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


# Arbitrary constant shared by every run of this migration
ADVISORY_LOCK_KEY = 405202611

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Tables whose row counts must be identical before and after the migration
COUNTED_TABLES = (
    "users",
    "storefronts",
    "listings",
    "wishlist",
    "cart_items",
    "orders",
    "order_items",
)

CREATE_LISTING_INTEREST_TABLE = """
    CREATE TABLE IF NOT EXISTS listing_interest (
        id BIGSERIAL PRIMARY KEY,
        listing_id INTEGER NOT NULL
            CONSTRAINT fk_listing_interest_listing
                REFERENCES listings(id)
                ON DELETE CASCADE,
        user_id INTEGER NOT NULL
            CONSTRAINT fk_listing_interest_user
                REFERENCES users(id)
                ON DELETE CASCADE,
        kind VARCHAR(16) NOT NULL
            CONSTRAINT listing_interest_kind_check
                CHECK (kind IN ('detail_view', 'wishlist', 'cart', 'order')),
        day DATE NOT NULL DEFAULT CURRENT_DATE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

        CONSTRAINT unique_listing_interest_daily
            UNIQUE (listing_id, user_id, kind, day)
    );
"""

CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_listing_interest_created_at ON listing_interest (created_at);",
    "CREATE INDEX IF NOT EXISTS idx_listing_interest_user_id ON listing_interest (user_id);",
)


class MigrationVerificationError(Exception):
    """Raised when post-migration verification fails (the transaction is rolled back)."""


def _table_exists(cur):
    cur.execute("SELECT to_regclass('listing_interest') IS NOT NULL;")
    return bool(cur.fetchone()[0])


def apply_listing_interest(cur):
    """Creates listing_interest and its indexes. Safe to run more than once. Does not commit."""
    table_created = not _table_exists(cur)
    cur.execute(CREATE_LISTING_INTEREST_TABLE)
    for statement in CREATE_INDEXES:
        cur.execute(statement)
    return {"table_created": table_created}


# ________________________________________________________
# VERIFICATION HELPERS
# ________________________________________________________

def _table_counts(cur):
    counts = {}
    for table in COUNTED_TABLES:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL;", (table,))
        if not cur.fetchone()[0]:
            counts[table] = None  # table not present in this environment
            continue
        # table names come from the COUNTED_TABLES constant, never from input
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        counts[table] = cur.fetchone()[0]
    return counts


def _schema_fingerprint(cur):
    """Columns and constraints of every other table, to prove they didn't change."""
    cur.execute("""
        SELECT md5(COALESCE(string_agg(
                   table_name || '.' || column_name || ':' || data_type || ':' || is_nullable
                   || ':' || COALESCE(column_default, ''),
                   ',' ORDER BY table_name, ordinal_position), ''))
        FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name <> 'listing_interest';
    """)
    columns = cur.fetchone()[0]
    cur.execute("""
        SELECT md5(COALESCE(string_agg(conrelid::regclass::text || '.' || conname, ',' ORDER BY 1), ''))
        FROM pg_constraint
        WHERE connamespace = current_schema()::regnamespace
          AND conrelid <> COALESCE(to_regclass('listing_interest'), 0);
    """)
    return columns, cur.fetchone()[0]


def _verify(cur, before_counts, after_counts, before_fp, after_fp):
    results = {}
    failures = []

    results["row_counts_unchanged"] = before_counts == after_counts
    if not results["row_counts_unchanged"]:
        failures.append(f"Row counts changed: before={before_counts} after={after_counts}")

    results["other_tables_unchanged"] = before_fp == after_fp
    if not results["other_tables_unchanged"]:
        failures.append("Columns or constraints of existing tables changed.")

    results["table_present"] = _table_exists(cur)
    if not results["table_present"]:
        failures.append("listing_interest was not created.")

    cur.execute("""
        SELECT conname FROM pg_constraint
        WHERE conrelid = to_regclass('listing_interest')
        ORDER BY conname;
    """)
    names = {row[0] for row in cur.fetchall()}
    for name in ("fk_listing_interest_listing", "fk_listing_interest_user",
                 "listing_interest_kind_check", "unique_listing_interest_daily"):
        if name not in names:
            failures.append(f"Constraint {name} is missing.")

    results["passed"] = not failures
    if failures:
        raise MigrationVerificationError("Verification failed; rolled back. " + " | ".join(failures))
    return results


# ________________________________________________________
# ENTRY POINT
# ________________________________________________________

def run_migration(conn, dry_run=False):
    """Runs the migration in one transaction. dry_run=True undoes it at the end. Returns a summary."""
    conn.autocommit = False
    cur = conn.cursor()
    try:
        # one snapshot for the whole run, so shoppers' writes during it don't change the counts
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;")
        cur.execute("SET LOCAL lock_timeout = '5s';")
        cur.execute("SELECT pg_advisory_xact_lock(%s);", (ADVISORY_LOCK_KEY,))

        counts_before = _table_counts(cur)
        fingerprint_before = _schema_fingerprint(cur)

        applied = apply_listing_interest(cur)

        counts_after = _table_counts(cur)
        fingerprint_after = _schema_fingerprint(cur)

        verification = _verify(cur, counts_before, counts_after, fingerprint_before, fingerprint_after)

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

    return {
        "outcome": outcome,
        "dry_run": dry_run,
        **applied,
        "counts_before": counts_before,
        "counts_after": counts_after,
        "verification": verification,
    }


def _print_target():
    host = os.getenv("DB_HOST") or "(unset)"
    name = os.getenv("DB_NAME") or "(unset)"
    port = os.getenv("DB_PORT") or "5432"
    sslmode = os.getenv("DB_SSLMODE") or "(driver default)"
    print("Target database")
    print(f"  DB_HOST    = {host}")
    print(f"  DB_PORT    = {port}")
    print(f"  DB_NAME    = {name}")
    print(f"  DB_SSLMODE = {sslmode}")
    return host, name


def main(argv=None):
    parser = argparse.ArgumentParser(description="Add the listing_interest table for the Hot page.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run everything, print the summary, then ROLLBACK.")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the confirmation prompt (local databases only).")
    args = parser.parse_args(argv)

    # Uses the app's normal database connection settings
    from db import get_connection

    host, name = _print_target()
    print(f"Mode: {'DRY RUN (will roll back)' if args.dry_run else 'APPLY (will commit)'}")

    if args.yes:
        if host.strip().lower() not in LOCAL_DB_HOSTS:
            print("Refusing --yes for a non-local database. Re-run without --yes and confirm interactively.")
            return 2
    else:
        typed = input(f"Type the database name ({name}) to continue: ").strip()
        if typed != name:
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
