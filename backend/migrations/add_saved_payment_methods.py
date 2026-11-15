
"""
migrations/add_saved_payment_methods.py

Purpose:
Creates a table for users' saved Stripe payment methods.

Security:
The application stores Stripe payment method references,
not actual card numbers or CVVs.
"""

import argparse
import json
import os
import sys

BACKEND_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from db import get_connection


LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}


CREATE_SAVED_PAYMENT_METHODS_TABLE = """
CREATE TABLE IF NOT EXISTS saved_payment_methods (
    id SERIAL PRIMARY KEY,

    user_id INTEGER NOT NULL,

    stripe_payment_method_id VARCHAR(255) NOT NULL UNIQUE,

    card_brand VARCHAR(50) NOT NULL,
    last_four VARCHAR(4) NOT NULL,

    expiration_month INTEGER NOT NULL,
    expiration_year INTEGER NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_saved_payment_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT valid_card_last_four
        CHECK (last_four ~ '^[0-9]{4}$'),

    CONSTRAINT valid_expiration_month
        CHECK (expiration_month BETWEEN 1 AND 12)
);
"""

CREATE_USER_INDEX = """
CREATE INDEX IF NOT EXISTS
idx_saved_payment_methods_user_id
ON saved_payment_methods(user_id);
"""


def run_migration(conn, dry_run=False):
    """Create the saved payment methods table."""

    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute(CREATE_SAVED_PAYMENT_METHODS_TABLE)
        cur.execute(CREATE_USER_INDEX)

        if dry_run:
            conn.rollback()
            outcome = "rolled back (dry run)"
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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create the saved payment methods table."
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test the migration and roll it back."
    )

    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation for local databases only."
    )

    args = parser.parse_args(argv)

    host = os.getenv("DB_HOST", "(unset)")
    database = os.getenv("DB_NAME", "(unset)")

    print("Target database")
    print(f"  DB_HOST = {host}")
    print(f"  DB_NAME = {database}")

    if args.yes:
        if host.strip().lower() not in LOCAL_DB_HOSTS:
            print("Refusing automatic confirmation for a non-local database.")
            return 2
    else:
        confirmation = input(
            f"Type the database name ({database}) to continue: "
        ).strip()

        if confirmation != database:
            print("Database name did not match. Aborted.")
            return 2

    conn = get_connection()

    try:
        result = run_migration(conn, dry_run=args.dry_run)

    except Exception as error:
        print(f"Migration failed: {error}")
        return 1

    finally:
        conn.close()

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
