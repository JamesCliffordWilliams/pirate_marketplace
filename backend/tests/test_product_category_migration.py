# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - migration tests
#
# These run the real migration in a test schema on a local database that looks like
# production did before categories, and get skipped otherwise (see tests/db_test_guard.py).

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema
from config.product_categories import PRODUCT_CATEGORIES
from migrations.add_product_categories import run_migration

ALL_SLUGS = [p["slug"] for p in PRODUCT_CATEGORIES] + [
    c["slug"] for p in PRODUCT_CATEGORIES for c in p.get("children", [])
]
CHILD_PARENT_PAIRS = sorted(
    (c["slug"], p["slug"]) for p in PRODUCT_CATEGORIES for c in p.get("children", [])
)

# The tables as they were before this migration
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
"""


class TestMigrationSql(unittest.TestCase):

    def test_never_drops_or_deletes_anything(self):
        with open(os.path.join(BACKEND_ROOT, "migrations", "add_product_categories.py"), encoding="utf-8") as f:
            source = f.read().upper()
        # "ON DELETE RESTRICT" in a foreign key is fine, but a DELETE statement is not
        source = source.replace("ON DELETE RESTRICT", "")
        for word in ("DROP", "TRUNCATE", "DELETE"):
            self.assertNotRegex(source, rf"\b{word}\b")


@require_local_db
class TestMigrationOnDatabase(unittest.TestCase):

    def setUp(self):
        self.db = ThrowawaySchema("test_categories").create(init_tables=False)
        self.db.execute(BASE_SCHEMA)
        user_id = self.db.scalar("INSERT INTO users (username) VALUES ('seller') RETURNING id;")
        storefront_id = self.db.scalar(
            "INSERT INTO storefronts (owner_id, brand_name) VALUES (%s, 'Shop') RETURNING id;", (user_id,)
        )
        self.listing_ids = []
        for i in range(3):
            listing_id = self.db.scalar("""
                INSERT INTO listings (storefront_id, title, price, fulfillment_type, quantity_on_hand,
                                      created_at, updated_at)
                VALUES (%s, %s, 10, 'IN_STOCK', 1, '2026-01-01 10:00:00', '2026-02-02 12:00:00')
                RETURNING id;
            """, (storefront_id, f"Item {i}"))
            self.listing_ids.append(listing_id)
            self.db.execute("INSERT INTO listing_images (listing_id, image_url, is_primary) VALUES (%s, 'u', TRUE);", (listing_id,))
            self.db.execute("INSERT INTO listing_sizes (listing_id, size, quantity) VALUES (%s, 'M', 1);", (listing_id,))

    def tearDown(self):
        self.db.drop()

    def migrate(self, **kwargs):
        conn = self.db.connect()
        try:
            return run_migration(conn, **kwargs)
        finally:
            conn.close()

    def category_column_count(self):
        return self.db.scalar("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'listings' AND column_name = 'category_id';
        """)

    def test_migration_end_to_end(self):
        before_timestamps = self.db.execute("SELECT id, created_at, updated_at FROM listings ORDER BY id;")

        summary = self.migrate()

        self.assertEqual(summary["outcome"], "committed")
        self.assertEqual(summary["listings_backfilled"], 3)
        self.assertEqual(summary["categories_inserted"], len(ALL_SLUGS))
        self.assertTrue(summary["fk_added"])

        other_id = self.db.scalar("SELECT id FROM product_categories WHERE slug = 'other';")
        self.assertEqual(summary["other_category_id"], other_id)
        self.assertEqual(self.db.execute("SELECT DISTINCT category_id FROM listings;"), [(other_id,)])

        # Nothing else changed
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM listing_images;"), 3)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM listing_sizes;"), 3)
        self.assertEqual(self.db.execute("SELECT id, created_at, updated_at FROM listings ORDER BY id;"), before_timestamps)

        # 12 main categories, and every subcategory sits under the right one
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM product_categories WHERE parent_id IS NULL AND is_active;"), 12)
        self.assertEqual(self.db.execute("""
            SELECT c.slug, p.slug FROM product_categories c
            JOIN product_categories p ON p.id = c.parent_id
            ORDER BY c.slug, p.slug;
        """), CHILD_PARENT_PAIRS)

        self.assertEqual(self.db.scalar("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'listings' AND column_name = 'category_id';
        """), "NO")
        self.assertEqual(self.db.scalar("""
            SELECT COUNT(*) FROM pg_constraint
            WHERE conname = 'fk_listing_category' AND conrelid = 'listings'::regclass;
        """), 1)

        # An old-style insert with no category_id gets Other by default
        conn = self.db.connect()
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
        self.migrate()
        phones_id = self.db.scalar("SELECT id FROM product_categories WHERE slug = 'phones';")
        self.db.execute("UPDATE listings SET category_id = %s WHERE id = %s;", (phones_id, self.listing_ids[0]))
        category_rows_before = self.db.execute("SELECT id, slug, updated_at FROM product_categories ORDER BY id;")

        summary = self.migrate()

        self.assertEqual(summary["listings_backfilled"], 0)
        self.assertEqual(summary["categories_inserted"], 0)
        self.assertEqual(summary["categories_updated"], 0)
        self.assertEqual(summary["categories_unchanged"], len(ALL_SLUGS))
        self.assertFalse(summary["fk_added"])
        self.assertEqual(self.db.scalar("SELECT category_id FROM listings WHERE id = %s;", (self.listing_ids[0],)), phones_id)
        self.assertEqual(self.db.execute("SELECT id, slug, updated_at FROM product_categories ORDER BY id;"),
                         category_rows_before)

    def test_renamed_category_is_updated_not_duplicated(self):
        self.migrate()
        self.db.execute("UPDATE product_categories SET name = 'Old Phones Name' WHERE slug = 'phones';")

        summary = self.migrate()

        self.assertEqual(summary["categories_inserted"], 0)
        self.assertEqual(summary["categories_updated"], 1)
        self.assertEqual(self.db.execute("SELECT name FROM product_categories WHERE slug = 'phones';"), [("Phones",)])

    def test_unknown_db_slug_is_reported_not_deleted(self):
        self.migrate()
        self.db.execute("INSERT INTO product_categories (slug, name) VALUES ('legacy-thing', 'Legacy');")

        summary = self.migrate()

        self.assertEqual(summary["categories_not_in_config"], ["legacy-thing"])
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM product_categories WHERE slug = 'legacy-thing';"), 1)

    def test_dry_run_leaves_schema_unchanged(self):
        summary = self.migrate(dry_run=True)

        self.assertTrue(summary["dry_run"])
        self.assertIn("rolled back", summary["outcome"])
        self.assertTrue(self.db.scalar("SELECT to_regclass('product_categories') IS NULL;"))
        self.assertEqual(self.category_column_count(), 0)

    def test_error_partway_undoes_everything(self):
        # The table gets created before the bad list is noticed, so this checks the rollback too
        bad = [{"slug": "other", "name": "Other", "icon": "box", "children": [{"slug": "x", "name": "X"}]}]
        with self.assertRaises(ValueError):
            self.migrate(taxonomy=bad)

        self.assertTrue(self.db.scalar("SELECT to_regclass('product_categories') IS NULL;"))
        self.assertEqual(self.category_column_count(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
