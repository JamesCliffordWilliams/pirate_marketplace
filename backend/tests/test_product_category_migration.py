# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - migration tests
#
# Two layers:
# 1. TestMigrationOffline: runs run_migration() against a scripted fake
#    connection. No database needed. Proves statement order, dry-run rollback,
#    error rollback, and that nothing destructive is ever issued.
# 2. TestMigrationOnDatabase: runs the real migration inside a throwaway schema
#    on a LOCAL database (skipped otherwise, see tests/db_test_guard.py).

import os
import re
import sys
import unittest
import uuid

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from tests.db_test_guard import require_local_db
from config.product_categories import PRODUCT_CATEGORIES, OTHER_SLUG
from migrations.add_product_categories import (
    run_migration,
    MigrationVerificationError,
    ADVISORY_LOCK_KEY,
)

ALL_SLUGS = [p["slug"] for p in PRODUCT_CATEGORIES] + [
    c["slug"] for p in PRODUCT_CATEGORIES for c in p.get("children", [])
]


# ________________________________________________________
# OFFLINE: scripted fake connection
# ________________________________________________________

class FakeDatabase:
    """
    Just enough state to answer the migration's queries:
    categories by slug, whether the column / FK exist, and listing rows.
    """

    def __init__(self, listing_count=3, null_listings=3, existing_slugs=None, extra_slugs=None,
                 change_counts_after_backfill=False):
        self.categories = {}       # slug -> {"id", "name", "parent_id", ...}
        self.next_id = 1
        self.column_exists = False
        self.fk_exists = False
        self.not_null = False
        self.listing_count = listing_count
        self.null_listings = null_listings
        self.change_counts_after_backfill = change_counts_after_backfill
        self.backfilled = False
        for slug in (existing_slugs or []) + (extra_slugs or []):
            self._insert(slug, slug, None)

    def _insert(self, slug, name, parent_id):
        self.categories[slug] = {"id": self.next_id, "name": name, "parent_id": parent_id,
                                 "description": None, "icon": None, "sort_order": 0}
        self.next_id += 1
        return self.categories[slug]


class FakeCursor:
    def __init__(self, db, log):
        self.db = db
        self.log = log
        self._result = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.log.append((normalized, params))
        db = self.db
        self._result = []
        self.rowcount = 0

        if normalized.startswith("SET LOCAL") or "pg_advisory_xact_lock" in normalized:
            return
        if normalized.startswith("LOCK TABLE"):
            return
        if "FROM pg_attribute" in normalized:
            self._result = [(db.not_null,)] if db.column_exists else []
            return
        if normalized.startswith("SELECT to_regclass"):
            self._result = [(True,)]
        elif normalized.startswith("SELECT COUNT(*) FROM listings WHERE category_id IS NULL"):
            self._result = [(0 if db.backfilled else db.null_listings,)]
        elif re.match(r"SELECT COUNT\(\*\) FROM (listings|listing_images|listing_sizes|wishlist|cart_items|order_items);", normalized):
            bump = 1 if (db.change_counts_after_backfill and db.backfilled) else 0
            self._result = [(db.listing_count + bump,)]
        elif normalized.startswith("SELECT md5"):
            self._result = [("fingerprint",)]
        elif normalized.startswith("CREATE TABLE IF NOT EXISTS product_categories") or normalized.startswith("CREATE INDEX"):
            return
        elif normalized.startswith("INSERT INTO product_categories"):
            slug, name, parent_id, description, icon, sort_order = params
            existing = db.categories.get(slug)
            if existing is None:
                row = db._insert(slug, name, parent_id)
                row.update(description=description, icon=icon, sort_order=sort_order)
                self._result = [(row["id"], True)]
            else:
                new_values = dict(name=name, parent_id=parent_id, description=description,
                                  icon=icon, sort_order=sort_order)
                if any(existing[k] != v for k, v in new_values.items()):
                    existing.update(new_values)
                    self._result = [(existing["id"], False)]
                else:
                    self._result = []  # conditional upsert skipped the row
        elif normalized.startswith("SELECT id FROM product_categories WHERE slug"):
            self._result = [(db.categories[params[0]]["id"],)]
        elif normalized.startswith("SELECT slug FROM product_categories WHERE NOT"):
            config = set(params[0])
            self._result = [(s,) for s in sorted(db.categories) if s not in config]
        elif "FROM information_schema.columns" in normalized and "is_nullable" in normalized:
            self._result = [("NO" if db.not_null else "YES",)]
        elif "FROM information_schema.columns" in normalized:
            self._result = [(1,)] if db.column_exists else []
        elif normalized.startswith("ALTER TABLE listings ADD COLUMN IF NOT EXISTS category_id"):
            db.column_exists = True
        elif "FROM pg_constraint" in normalized:
            self._result = [(1,)] if db.fk_exists else []
        elif "ADD CONSTRAINT fk_listing_category" in normalized:
            db.fk_exists = True
        elif normalized.startswith("UPDATE listings SET category_id"):
            self.rowcount = 0 if db.backfilled else db.null_listings
            db.backfilled = True
        elif "SET NOT NULL" in normalized:
            db.not_null = True
        elif "SET DEFAULT" in normalized:
            return
        elif "LEFT JOIN product_categories c ON c.id = l.category_id" in normalized:
            self._result = [(0,)]
        elif "WHERE slug = ANY(%s) AND parent_id IS NULL AND is_active = TRUE" in normalized:
            parents = set(params[0])
            self._result = [(sum(1 for s, c in db.categories.items() if s in parents and c["parent_id"] is None),)]
        elif normalized.startswith("SELECT COUNT(*) FROM product_categories WHERE parent_id IS NULL"):
            self._result = [(sum(1 for c in db.categories.values() if c["parent_id"] is None),)]
        elif "JOIN product_categories p ON p.id = c.parent_id" in normalized:
            self._result = [(0,)]
        else:
            raise AssertionError(f"Unexpected SQL in migration: {normalized}")

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def close(self):
        pass


class FakeConnection:
    def __init__(self, db):
        self.db = db
        self.log = []
        self.autocommit = True
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return FakeCursor(self.db, self.log)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class TestMigrationOffline(unittest.TestCase):

    def test_first_run_seeds_everything_and_commits(self):
        conn = FakeConnection(FakeDatabase(listing_count=5, null_listings=5))
        summary = run_migration(conn, dry_run=False)

        self.assertFalse(conn.autocommit)
        self.assertEqual((conn.commits, conn.rollbacks), (1, 0))
        self.assertEqual(summary["outcome"], "committed")
        self.assertEqual(summary["categories_inserted"], len(ALL_SLUGS))
        self.assertEqual(summary["categories_updated"], 0)
        self.assertEqual(summary["listings_backfilled"], 5)
        self.assertTrue(summary["column_added"])
        self.assertTrue(summary["fk_added"])
        self.assertTrue(summary["verification"]["passed"])
        self.assertEqual(summary["other_category_id"], conn.db.categories[OTHER_SLUG]["id"])

    def test_statement_order(self):
        conn = FakeConnection(FakeDatabase())
        run_migration(conn)
        statements = [sql for sql, _ in conn.log]

        def first_index(prefix):
            return next(i for i, s in enumerate(statements) if s.startswith(prefix) or prefix in s)

        order = [
            first_index("SET LOCAL lock_timeout = '5s'"),
            first_index("pg_advisory_xact_lock"),
            first_index("SELECT to_regclass"),
            first_index("CREATE TABLE IF NOT EXISTS product_categories"),
            first_index("INSERT INTO product_categories"),
            first_index("ALTER TABLE listings ADD COLUMN IF NOT EXISTS category_id"),
            first_index("ADD CONSTRAINT fk_listing_category"),
            first_index("UPDATE listings SET category_id"),
            first_index("SET DEFAULT"),
            first_index("SET NOT NULL"),
            first_index("CREATE INDEX IF NOT EXISTS idx_listings_category_status_created"),
        ]
        self.assertEqual(order, sorted(order))

        lock_params = next(p for s, p in conn.log if "pg_advisory_xact_lock" in s)
        self.assertEqual(lock_params, (ADVISORY_LOCK_KEY,))

    def test_listing_tables_locked_before_before_counts(self):
        # Writes during the run (cart adds, edits) would otherwise trip the
        # count/timestamp verification and abort a production run.
        conn = FakeConnection(FakeDatabase())
        run_migration(conn)
        statements = [sql for sql, _ in conn.log]
        lock_index = next(i for i, s in enumerate(statements) if s.startswith("LOCK TABLE"))
        advisory_index = next(i for i, s in enumerate(statements) if "pg_advisory_xact_lock" in s)
        first_count = next(i for i, s in enumerate(statements) if s.startswith("SELECT COUNT(*) FROM listings;"))
        self.assertLess(advisory_index, lock_index)
        self.assertLess(lock_index, first_count)
        lock_sql = statements[lock_index]
        self.assertIn("IN SHARE MODE", lock_sql)
        for table in ("listings", "listing_images", "listing_sizes", "wishlist", "cart_items", "order_items"):
            self.assertIn(table, lock_sql)

    def test_column_checks_resolve_listings_like_the_ddl(self):
        # information_schema + current_schema() can point at a different schema than
        # the 'listings' that search_path/regclass resolves; use pg_attribute instead.
        conn = FakeConnection(FakeDatabase())
        run_migration(conn)
        for sql, _ in conn.log:
            self.assertNotIn("information_schema.columns", sql)
        attribute_checks = [sql for sql, _ in conn.log if "FROM pg_attribute" in sql]
        self.assertTrue(attribute_checks)
        for sql in attribute_checks:
            self.assertIn("'listings'::regclass", sql)

    def test_parents_inserted_before_children(self):
        conn = FakeConnection(FakeDatabase())
        run_migration(conn)
        inserts = [p for s, p in conn.log if s.startswith("INSERT INTO product_categories")]
        parent_flags = [params[2] is None for params in inserts]
        # all parents (parent_id None) first, then only children
        self.assertEqual(parent_flags, sorted(parent_flags, reverse=True))
        self.assertEqual(sum(parent_flags), 12)

    def test_backfill_only_touches_nulls_and_never_timestamps(self):
        conn = FakeConnection(FakeDatabase())
        run_migration(conn)
        updates = [s for s, _ in conn.log if s.startswith("UPDATE listings")]
        self.assertEqual(len(updates), 1)
        self.assertIn("WHERE category_id IS NULL", updates[0])
        self.assertNotIn("updated_at", updates[0])
        self.assertNotIn("created_at", updates[0])

    def test_never_issues_destructive_sql(self):
        conn = FakeConnection(FakeDatabase(extra_slugs=["legacy-thing"]))
        run_migration(conn)
        for sql, _ in conn.log:
            upper = sql.upper()
            self.assertNotRegex(upper, r"\bDROP\b")
            self.assertNotRegex(upper, r"\bTRUNCATE\b")
            # "ON DELETE RESTRICT" in a FK definition is fine; a DELETE statement is not
            self.assertNotRegex(upper, r"^\s*DELETE\b")
            self.assertNotRegex(upper.replace("ON DELETE RESTRICT", ""), r"\bDELETE\b")

    def test_rerun_is_a_no_op(self):
        db = FakeDatabase(listing_count=4, null_listings=4)
        run_migration(FakeConnection(db))
        conn = FakeConnection(db)
        summary = run_migration(conn)

        self.assertEqual(summary["categories_inserted"], 0)
        self.assertEqual(summary["categories_updated"], 0)
        self.assertEqual(summary["categories_unchanged"], len(ALL_SLUGS))
        self.assertEqual(summary["listings_backfilled"], 0)
        self.assertFalse(summary["column_added"])
        self.assertFalse(summary["fk_added"])
        self.assertFalse(any("ADD CONSTRAINT" in s for s, _ in conn.log))

    def test_renamed_category_is_updated_not_duplicated(self):
        db = FakeDatabase()
        run_migration(FakeConnection(db))
        db.categories["phones"]["name"] = "Old Phones Name"
        summary = run_migration(FakeConnection(db))
        self.assertEqual(summary["categories_inserted"], 0)
        self.assertEqual(summary["categories_updated"], 1)
        self.assertEqual(db.categories["phones"]["name"], "Phones")

    def test_unknown_db_slug_is_reported_not_deleted(self):
        db = FakeDatabase(extra_slugs=["legacy-thing"])
        summary = run_migration(FakeConnection(db))
        self.assertIn("legacy-thing", db.categories)
        self.assertEqual(len(summary["warnings"]), 1)
        self.assertIn("legacy-thing", summary["warnings"][0])

    def test_dry_run_rolls_back(self):
        conn = FakeConnection(FakeDatabase())
        summary = run_migration(conn, dry_run=True)
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))
        self.assertTrue(summary["dry_run"])
        self.assertIn("rolled back", summary["outcome"])

    def test_verification_failure_rolls_back(self):
        conn = FakeConnection(FakeDatabase(change_counts_after_backfill=True))
        with self.assertRaises(MigrationVerificationError):
            run_migration(conn)
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))

    def test_invalid_taxonomy_aborts_before_any_write(self):
        conn = FakeConnection(FakeDatabase())
        bad = [{"slug": "other", "name": "Other", "icon": "box", "children": [{"slug": "x", "name": "X"}]}]
        with self.assertRaises(ValueError):
            run_migration(conn, taxonomy=bad)
        self.assertEqual((conn.commits, conn.rollbacks), (0, 1))
        self.assertFalse(any(s.startswith("INSERT") for s, _ in conn.log))


# ________________________________________________________
# DATABASE: real migration inside a scratch schema (local DB only)
# ________________________________________________________

BASE_SCHEMA = """
    CREATE TABLE users (id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL);
    CREATE TABLE storefronts (
        id SERIAL PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
        brand_name VARCHAR(80) NOT NULL, logo_url TEXT, is_active BOOLEAN DEFAULT TRUE
    );
    CREATE TABLE listings (
        id SERIAL PRIMARY KEY,
        storefront_id INTEGER NOT NULL REFERENCES storefronts(id) ON DELETE CASCADE,
        title VARCHAR(120) NOT NULL, description TEXT,
        price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
        fulfillment_type VARCHAR(20) NOT NULL CHECK (fulfillment_type IN ('IN_STOCK', 'PREORDER')),
        quantity_on_hand INTEGER CHECK (quantity_on_hand >= 0),
        sizes_available TEXT,
        status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE', 'SOLD_OUT', 'DELETED')),
        storefront_restore_status VARCHAR(20), deleted_restore_status VARCHAR(20),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_made_to_order BOOLEAN DEFAULT FALSE
    );
    CREATE TABLE listing_images (
        id SERIAL PRIMARY KEY, listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
        image_url TEXT NOT NULL, is_primary BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE listing_sizes (
        id SERIAL PRIMARY KEY, listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
        size VARCHAR(20) NOT NULL, quantity INTEGER NOT NULL CHECK (quantity >= 0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE (listing_id, size)
    );
    CREATE TABLE wishlist (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, listing_id INTEGER NOT NULL);
    CREATE TABLE cart_items (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, item_id INTEGER, item_name VARCHAR(255) NOT NULL);
    CREATE TABLE order_items (id SERIAL PRIMARY KEY, order_id INTEGER NOT NULL, listing_id INTEGER, item_name VARCHAR(255) NOT NULL);
"""


@require_local_db
class TestMigrationOnDatabase(unittest.TestCase):

    def setUp(self):
        from db import get_connection
        self.get_connection = get_connection
        self.schema = f"test_categories_{uuid.uuid4().hex[:10]}"

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"CREATE SCHEMA {self.schema};")
        cur.execute(f"SET search_path TO {self.schema};")
        cur.execute(BASE_SCHEMA)
        cur.execute("INSERT INTO users (username) VALUES ('seller') RETURNING id;")
        user_id = cur.fetchone()[0]
        cur.execute("INSERT INTO storefronts (owner_id, brand_name) VALUES (%s, 'Shop') RETURNING id;", (user_id,))
        storefront_id = cur.fetchone()[0]
        self.listing_ids = []
        for i in range(3):
            cur.execute("""
                INSERT INTO listings (storefront_id, title, price, fulfillment_type, quantity_on_hand,
                                      created_at, updated_at)
                VALUES (%s, %s, 10, 'IN_STOCK', 1, '2026-01-01 10:00:00', '2026-02-02 12:00:00')
                RETURNING id;
            """, (storefront_id, f"Item {i}"))
            listing_id = cur.fetchone()[0]
            self.listing_ids.append(listing_id)
            cur.execute("INSERT INTO listing_images (listing_id, image_url, is_primary) VALUES (%s, 'u', TRUE);", (listing_id,))
            cur.execute("INSERT INTO listing_sizes (listing_id, size, quantity) VALUES (%s, 'M', 1);", (listing_id,))
        conn.commit()
        cur.close()
        conn.close()

    def tearDown(self):
        conn = self.get_connection()
        cur = conn.cursor()
        # Drops only the throwaway schema this test created
        cur.execute(f"DROP SCHEMA IF EXISTS {self.schema} CASCADE;")
        conn.commit()
        cur.close()
        conn.close()

    def _conn(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(f"SET search_path TO {self.schema};")
        conn.commit()
        cur.close()
        return conn

    def _query(self, sql, params=None):
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

    def test_migration_end_to_end(self):
        before_timestamps = self._query("SELECT id, created_at, updated_at FROM listings ORDER BY id;")

        conn = self._conn()
        summary = run_migration(conn)
        conn.close()

        self.assertEqual(summary["counts_before"], summary["counts_after"])
        self.assertEqual(summary["listings_backfilled"], 3)
        self.assertEqual(summary["categories_inserted"], len(ALL_SLUGS))

        other_id = self._query("SELECT id FROM product_categories WHERE slug = 'other';")[0][0]
        self.assertEqual(
            self._query("SELECT DISTINCT category_id FROM listings;"), [(other_id,)]
        )
        self.assertEqual(self._query("SELECT COUNT(*) FROM listing_images;"), [(3,)])
        self.assertEqual(self._query("SELECT COUNT(*) FROM listing_sizes;"), [(3,)])
        self.assertEqual(
            self._query("SELECT id, created_at, updated_at FROM listings ORDER BY id;"), before_timestamps
        )
        self.assertEqual(
            self._query("""
                SELECT is_nullable FROM information_schema.columns
                WHERE table_schema = %s AND table_name = 'listings' AND column_name = 'category_id';
            """, (self.schema,)),
            [("NO",)]
        )
        self.assertEqual(
            self._query("""
                SELECT COUNT(*) FROM pg_constraint
                WHERE conname = 'fk_listing_category' AND conrelid = 'listings'::regclass;
            """),
            [(1,)]
        )
        self.assertEqual(
            self._query("SELECT COUNT(*) FROM product_categories WHERE parent_id IS NULL AND is_active;"),
            [(12,)]
        )

        # Legacy raw insert without category_id gets the DB default (Other)
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO listings (storefront_id, title, price, fulfillment_type, quantity_on_hand)
            SELECT storefront_id, 'Legacy', 1, 'IN_STOCK', 1 FROM listings LIMIT 1
            RETURNING category_id;
        """)
        self.assertEqual(cur.fetchone()[0], other_id)
        conn.rollback()
        cur.close()
        conn.close()

    def test_rerun_changes_nothing_and_keeps_seller_choice(self):
        conn = self._conn()
        run_migration(conn)
        conn.close()

        phones_id = self._query("SELECT id FROM product_categories WHERE slug = 'phones';")[0][0]
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("UPDATE listings SET category_id = %s WHERE id = %s;", (phones_id, self.listing_ids[0]))
        conn.commit()
        cur.close()
        conn.close()

        category_rows_before = self._query("SELECT id, slug, updated_at FROM product_categories ORDER BY id;")

        conn = self._conn()
        summary = run_migration(conn)
        conn.close()

        self.assertEqual(summary["listings_backfilled"], 0)
        self.assertEqual(summary["categories_inserted"], 0)
        self.assertEqual(summary["categories_updated"], 0)
        self.assertEqual(
            self._query("SELECT category_id FROM listings WHERE id = %s;", (self.listing_ids[0],)),
            [(phones_id,)]
        )
        self.assertEqual(
            self._query("SELECT id, slug, updated_at FROM product_categories ORDER BY id;"),
            category_rows_before
        )

    def test_dry_run_leaves_schema_unchanged(self):
        conn = self._conn()
        summary = run_migration(conn, dry_run=True)
        conn.close()

        self.assertTrue(summary["dry_run"])
        self.assertEqual(self._query("SELECT to_regclass('product_categories') IS NULL;"), [(True,)])
        self.assertEqual(
            self._query("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = %s AND table_name = 'listings' AND column_name = 'category_id';
            """, (self.schema,)),
            [(0,)]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
