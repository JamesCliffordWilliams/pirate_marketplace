# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
migrations/add_product_categories.py

This adds product categories to a database that already has data.
If anything fails, nothing gets changed.

What it does:
1. Creates the product_categories table and fills it from the config file
2. Adds listings.category_id and puts existing listings with no category in "Other".
   Running it again won't undo a category a seller already picked.

How to run it (from the repo root):
    python backend/migrations/add_product_categories.py --dry-run   (test run, undoes itself)
    python backend/migrations/add_product_categories.py

It shows which database it will use and asks you to type the database name first.
"""

import os
import re
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from config.product_categories import PRODUCT_CATEGORIES, OTHER_SLUG
from migrations.add_listing_interest import run_in_one_transaction, run_from_command_line

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

CREATE_PRODUCT_CATEGORIES_TABLE = """
    CREATE TABLE IF NOT EXISTS product_categories (
        id SERIAL PRIMARY KEY,
        slug VARCHAR(80) NOT NULL UNIQUE
            CONSTRAINT product_categories_slug_format
                CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
        name VARCHAR(80) NOT NULL,
        parent_id INTEGER NULL
            CONSTRAINT fk_product_category_parent
                REFERENCES product_categories(id)
                ON DELETE RESTRICT,
        description TEXT,
        icon VARCHAR(40),
        sort_order INTEGER NOT NULL DEFAULT 0,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        CONSTRAINT product_categories_not_own_parent
            CHECK (parent_id IS NULL OR parent_id <> id)
    );
"""

# Adds a category, or updates it if anything about it changed.
# If nothing changed it returns no row, so updated_at stays the same.
UPSERT_CATEGORY = """
    INSERT INTO product_categories (slug, name, parent_id, description, icon, sort_order)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (slug) DO UPDATE
    SET name = EXCLUDED.name,
        parent_id = EXCLUDED.parent_id,
        description = EXCLUDED.description,
        icon = EXCLUDED.icon,
        sort_order = EXCLUDED.sort_order,
        updated_at = CURRENT_TIMESTAMP
    WHERE (product_categories.name, product_categories.parent_id, product_categories.description,
           product_categories.icon, product_categories.sort_order)
          IS DISTINCT FROM
          (EXCLUDED.name, EXCLUDED.parent_id, EXCLUDED.description,
           EXCLUDED.icon, EXCLUDED.sort_order)
    RETURNING id, (xmax::text = '0') AS was_inserted;
"""


def validate_taxonomy(taxonomy):
    """Checks the category list before anything is saved. Raises ValueError if something is wrong."""
    if not isinstance(taxonomy, list) or not taxonomy:
        raise ValueError("Taxonomy must be a non-empty list of parent categories.")

    seen_slugs = set()

    def check_node(node, label):
        slug = node.get("slug")
        name = node.get("name")
        if not isinstance(slug, str) or not SLUG_PATTERN.match(slug) or len(slug) > 80:
            raise ValueError(f"{label}: invalid slug {slug!r}.")
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ValueError(f"{label} {slug!r}: name must be 1-80 characters.")
        if slug in seen_slugs:
            raise ValueError(f"Duplicate slug {slug!r}. Slugs must be globally unique.")
        icon = node.get("icon")
        if icon is not None and (not isinstance(icon, str) or len(icon) > 40):
            raise ValueError(f"{label} {slug!r}: icon must be a string of at most 40 characters.")
        seen_slugs.add(slug)

    other_found = False
    for parent in taxonomy:
        check_node(parent, "Parent category")
        children = parent.get("children") or []

        if parent["slug"] == OTHER_SLUG:
            other_found = True
            if children:
                raise ValueError("'Other' must not have children; it is a selectable top-level leaf.")

        for child in children:
            check_node(child, f"Child of {parent['slug']!r}")
            if child.get("children"):
                raise ValueError(
                    f"{child['slug']!r} has children. Categories are limited to two levels (no grandchildren)."
                )

    if not other_found:
        raise ValueError(f"The taxonomy must include a top-level {OTHER_SLUG!r} category.")


def _save_category(cur, node, parent_id, sort_order, counts):
    """Adds or updates one category and returns its id."""
    cur.execute(UPSERT_CATEGORY, (node["slug"], node["name"], parent_id,
                                  node.get("description"), node.get("icon"), sort_order))
    row = cur.fetchone()
    if row is None:
        counts["categories_unchanged"] += 1
        cur.execute("SELECT id FROM product_categories WHERE slug = %s;", (node["slug"],))
        return cur.fetchone()[0]
    if row[1]:
        counts["categories_inserted"] += 1
    else:
        counts["categories_updated"] += 1
    return row[0]


def apply_product_categories(cur, taxonomy=PRODUCT_CATEGORIES):
    """
    Creates the category table, adds listings.category_id and puts listings with no category in "Other".
    It's safe to run more than once and it doesn't commit. init_db.py uses this too.
    """
    cur.execute(CREATE_PRODUCT_CATEGORIES_TABLE)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_product_categories_parent_id ON product_categories (parent_id);")

    # Adds or updates each category by its slug, main categories first. It never deletes any
    validate_taxonomy(taxonomy)
    summary = {"categories_inserted": 0, "categories_updated": 0, "categories_unchanged": 0}
    slug_ids = {}
    for index, parent in enumerate(taxonomy, start=1):
        slug_ids[parent["slug"]] = _save_category(cur, parent, None, index, summary)
    for parent in taxonomy:
        for index, child in enumerate(parent.get("children") or [], start=1):
            slug_ids[child["slug"]] = _save_category(cur, child, slug_ids[parent["slug"]], index, summary)

    # Categories in the database that aren't in the config are left alone, just listed in the summary
    cur.execute("SELECT slug FROM product_categories WHERE NOT (slug = ANY(%s)) ORDER BY slug;", (list(slug_ids),))
    summary["categories_not_in_config"] = [row[0] for row in cur.fetchall()]

    other_id = int(slug_ids[OTHER_SLUG])
    cur.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS category_id INTEGER;")

    # Postgres has no ADD CONSTRAINT IF NOT EXISTS, so this checks first
    cur.execute("""
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_listing_category' AND conrelid = 'listings'::regclass;
    """)
    summary["fk_added"] = cur.fetchone() is None
    if summary["fk_added"]:
        cur.execute("""
            ALTER TABLE listings
            ADD CONSTRAINT fk_listing_category
                FOREIGN KEY (category_id)
                REFERENCES product_categories(id)
                ON DELETE RESTRICT;
        """)

    # This only changes listings with no category and doesn't touch updated_at
    cur.execute("UPDATE listings SET category_id = %s WHERE category_id IS NULL;", (other_id,))
    summary["listings_backfilled"] = cur.rowcount

    cur.execute("ALTER TABLE listings ALTER COLUMN category_id SET DEFAULT %s;", (other_id,))
    cur.execute("ALTER TABLE listings ALTER COLUMN category_id SET NOT NULL;")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_listings_category_status_created
            ON listings (category_id, status, created_at DESC);
    """)

    summary["other_category_id"] = other_id
    return summary


def run_migration(conn, dry_run=False, taxonomy=PRODUCT_CATEGORIES):
    """Runs the migration and returns a summary. With dry_run=True it undoes everything at the end."""
    return run_in_one_transaction(conn, lambda cur: apply_product_categories(cur, taxonomy), dry_run)


if __name__ == "__main__":
    sys.exit(run_from_command_line("Add product categories and backfill listings to 'Other'.", run_migration))
