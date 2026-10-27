# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - listing_interest migration tests
#
# Runs against a throwaway schema on a LOCAL database (skipped otherwise, see db_test_guard.py).

import os
import sys
import unittest

import psycopg2

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema
from migrations.add_listing_interest import run_migration

COLUMNS_SQL = """
    SELECT table_name, column_name, data_type, is_nullable, COALESCE(column_default, '')
    FROM information_schema.columns
    WHERE table_schema = current_schema() AND table_name <> 'listing_interest'
    ORDER BY table_name, ordinal_position;
"""

CONSTRAINTS_SQL = """
    SELECT conrelid::regclass::text, conname
    FROM pg_constraint
    WHERE connamespace = current_schema()::regnamespace
      AND conrelid <> COALESCE(to_regclass('listing_interest'), 0)
    ORDER BY 1, 2;
"""


@require_local_db
class TestListingInterestMigration(unittest.TestCase):

    def setUp(self):
        self.db = ThrowawaySchema("test_interest_mig").create()
        # Start from a database without the new table (as production is today)
        self.db.execute("DROP TABLE IF EXISTS listing_interest;")
        self.seller_store = self.db.add_storefront()
        self.listing_id = self.db.add_listing(self.seller_store)
        self.shopper = self.db.add_user()
        self.db.execute("INSERT INTO wishlist (user_id, listing_id) VALUES (%s, %s);", (self.shopper, self.listing_id))

    def tearDown(self):
        self.db.drop()

    def _migrate(self, dry_run=False):
        conn = self.db.connect()
        try:
            return run_migration(conn, dry_run=dry_run)
        finally:
            conn.close()

    def _table_exists(self):
        return self.db.scalar("SELECT to_regclass('listing_interest') IS NOT NULL;")

    def test_creates_table_and_is_idempotent(self):
        columns_before = self.db.execute(COLUMNS_SQL)
        constraints_before = self.db.execute(CONSTRAINTS_SQL)
        wishlist_before = self.db.execute("SELECT * FROM wishlist ORDER BY id;")

        first = self._migrate()
        self.assertEqual(first["outcome"], "committed")
        self.assertTrue(first["table_created"])
        self.assertTrue(self._table_exists())

        second = self._migrate()
        self.assertEqual(second["outcome"], "committed")
        self.assertFalse(second["table_created"])

        # existing tables untouched
        self.assertEqual(self.db.execute(COLUMNS_SQL), columns_before)
        self.assertEqual(self.db.execute(CONSTRAINTS_SQL), constraints_before)
        self.assertEqual(self.db.execute("SELECT * FROM wishlist ORDER BY id;"), wishlist_before)
        self.assertEqual(first["counts_before"], first["counts_after"])

        # no backfill
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM listing_interest;"), 0)

        indexes = {row[0] for row in self.db.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() AND tablename = 'listing_interest';"
        )}
        self.assertIn("idx_listing_interest_created_at", indexes)
        self.assertIn("idx_listing_interest_user_id", indexes)

    def test_dry_run_changes_nothing(self):
        summary = self._migrate(dry_run=True)
        self.assertTrue(summary["dry_run"])
        self.assertFalse(self._table_exists())

    def test_constraints(self):
        self._migrate()
        self.db.execute(
            "INSERT INTO listing_interest (listing_id, user_id, kind) VALUES (%s, %s, 'wishlist');",
            (self.listing_id, self.shopper),
        )
        # one row per listing, user, kind and day
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            self.db.execute(
                "INSERT INTO listing_interest (listing_id, user_id, kind) VALUES (%s, %s, 'wishlist');",
                (self.listing_id, self.shopper),
            )
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.db.execute(
                "INSERT INTO listing_interest (listing_id, user_id, kind) VALUES (%s, %s, 'impression');",
                (self.listing_id, self.shopper),
            )
        # cascades with the listing
        self.db.execute("DELETE FROM listings WHERE id = %s;", (self.listing_id,))
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM listing_interest;"), 0)

    def test_live_writes_during_migration_do_not_fail_it(self):
        # a shopper adds to cart while the migration runs (another connection, committed)
        from migrations import add_listing_interest as migration
        real_apply = migration.apply_listing_interest

        def apply_with_concurrent_write(cur):
            self.db.execute(
                "INSERT INTO cart_items (user_id, item_id, item_name, price) VALUES (%s, %s, 'Item', 10);",
                (self.shopper, self.listing_id),
            )
            return real_apply(cur)

        from unittest.mock import patch
        with patch.object(migration, "apply_listing_interest", side_effect=apply_with_concurrent_write):
            summary = self._migrate()
        self.assertEqual(summary["outcome"], "committed")
        self.assertTrue(self._table_exists())

    def test_init_db_creates_the_table(self):
        from init_db import create_vault_tables
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            create_vault_tables()
        self.assertTrue(self._table_exists())


if __name__ == "__main__":
    unittest.main()
