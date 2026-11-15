# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
migrations/add_listing_interest.py

This adds the listing_interest table that the Hot page uses.
It only adds a new table, so existing tables and data stay the same.
If anything fails, nothing gets changed.

How to run it (from the repo root):
    python backend/migrations/add_listing_interest.py --dry-run   (test run, undoes itself)
    python backend/migrations/add_listing_interest.py

It shows which database it will use and asks you to type the database name first.
The other migrations and the cleanup script use the helpers at the bottom of this file too.
"""

import argparse
import json
import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


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


def apply_listing_interest(cur):
    """Creates listing_interest and its indexes. It's safe to run more than once and it doesn't commit."""
    cur.execute("SELECT to_regclass('listing_interest') IS NULL;")
    table_created = cur.fetchone()[0]
    cur.execute(CREATE_LISTING_INTEREST_TABLE)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_listing_interest_created_at ON listing_interest (created_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_listing_interest_user_id ON listing_interest (user_id);")
    return {"table_created": table_created}


def run_migration(conn, dry_run=False):
    """Runs the migration and returns a summary. With dry_run=True it undoes everything at the end."""
    return run_in_one_transaction(conn, apply_listing_interest, dry_run)


# ________________________________________________________
# SHARED BY ALL THE MIGRATIONS AND THE CLEANUP SCRIPT
# ________________________________________________________

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}


def run_in_one_transaction(conn, apply, dry_run=False):
    """Runs apply(cur) as one transaction. A dry run or any error undoes all of it."""
    conn.autocommit = False
    cur = conn.cursor()
    try:
        # Gives up after 5 seconds instead of making shoppers wait on a busy table
        cur.execute("SET LOCAL lock_timeout = '5s';")
        summary = apply(cur)
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

    summary["outcome"] = "rolled back (dry run) - nothing was changed" if dry_run else "committed"
    summary["dry_run"] = dry_run
    return summary


def print_target():
    """Prints which database we're about to use and returns its host and name."""
    host = os.getenv("DB_HOST") or "(unset)"
    name = os.getenv("DB_NAME") or "(unset)"
    print("Target database")
    print(f"  DB_HOST    = {host}")
    print(f"  DB_PORT    = {os.getenv('DB_PORT') or '5432'}")
    print(f"  DB_NAME    = {name}")
    print(f"  DB_SSLMODE = {os.getenv('DB_SSLMODE') or '(driver default)'}")
    return host, name


def run_from_command_line(description, run_migration):
    """Handles --dry-run and --yes, asks for the database name, then runs the migration."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dry-run", action="store_true",
                        help="Run everything, print the summary, then ROLLBACK.")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the confirmation prompt (local databases only).")
    args = parser.parse_args()

    # Uses the app's normal database connection settings
    from db import get_connection

    host, name = print_target()
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
    sys.exit(run_from_command_line("Add the listing_interest table for the Hot page.", run_migration))
