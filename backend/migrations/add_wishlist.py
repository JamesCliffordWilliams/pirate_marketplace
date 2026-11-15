#Created by Madison Rickman - 10/27/26

"""
migrations/add_listing_interest.py

Purpose:
Migrates the wishlist. Referencing the existing table. Runs in one
transaction, so it either all works or nothing changes.

"""


import argparse
import json
import os
import sys
from db import get_db_connection

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

CREATE_WISHLIST_TABLE = """
            CREATE TABLE IF NOT EXISTS wishlist (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                listing_id INTEGER NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_wishlist_user
                    FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,

                CONSTRAINT fk_wishlist_listing
                    FOREIGN KEY(listing_id)
                    REFERENCES listings(id)
                    ON DELETE CASCADE,

                CONSTRAINT unique_user_listing_wishlist
                    UNIQUE (user_id, listing_id)
            );
        """

CREATE_INDEX_SQL = """CREATE INDEX IF NOT EXISTS idx_wishlist_user_id ON wishlist(user_id)"""


# ________________________________________________________
# ENTRY POINT
# ________________________________________________________

def run_migration(conn, dry_run=False):
    """Runs the migration in one transaction. dry_run=True undoes it at the end. Returns a summary."""
    conn.autocommit = False
    cur = conn.cursor()
    try:

        cur.execute(CREATE_WISHLIST_TABLE)
        cur.execute(CREATE_INDEX_SQL)

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
        "dry_run": dry_run
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
