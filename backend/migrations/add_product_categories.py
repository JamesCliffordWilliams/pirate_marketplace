# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
migrations/add_product_categories.py

Purpose:
Adds product categories to an existing database. Everything runs in one
transaction, so it either all works or nothing changes.

Steps:
1. Lock so two runs can't overlap
2. Count rows in the listing tables
3. Create the product_categories table and fill it from config
4. Add listings.category_id and put every existing listing in "Other"
   (only listings with no category yet, so a re-run never undoes a seller's choice)
5. Check that nothing was lost; if anything looks wrong, undo everything

Usage (from the repo root):
    python backend/migrations/add_product_categories.py --dry-run   (test run, undoes itself)
    python backend/migrations/add_product_categories.py

It shows which database it will use and asks you to type the database name first.
"""

import argparse
import json
import os
import re
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from config.product_categories import PRODUCT_CATEGORIES, OTHER_SLUG


# Arbitrary constant shared by every run of this migration
ADVISORY_LOCK_KEY = 405202610

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Tables whose row counts must be identical before and after the migration
COUNTED_TABLES = (
    "listings",
    "listing_images",
    "listing_sizes",
    "wishlist",
    "cart_items",
    "order_items",
)

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

CREATE_PRODUCT_CATEGORIES_PARENT_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_product_categories_parent_id
        ON product_categories (parent_id);
"""

CREATE_LISTINGS_CATEGORY_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_listings_category_status_created
        ON listings (category_id, status, created_at DESC);
"""

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


class MigrationVerificationError(Exception):
    """Raised when post-migration verification fails (the transaction is rolled back)."""


# ________________________________________________________
# TAXONOMY VALIDATION
# ________________________________________________________

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


def _config_slugs(taxonomy):
    slugs = []
    for parent in taxonomy:
        slugs.append(parent["slug"])
        slugs.extend(child["slug"] for child in parent.get("children") or [])
    return slugs


# ________________________________________________________
# SCHEMA + SEED (shared with init_db.py)
# ________________________________________________________

def _upsert_category(cur, node, parent_id, sort_order, stats):
    cur.execute(UPSERT_CATEGORY, (
        node["slug"],
        node["name"],
        parent_id,
        node.get("description"),
        node.get("icon"),
        sort_order,
    ))
    row = cur.fetchone()

    if row is None:
        # Already up to date
        stats["unchanged"] += 1
        cur.execute("SELECT id FROM product_categories WHERE slug = %s;", (node["slug"],))
        return cur.fetchone()[0]

    if row[1]:
        stats["inserted"] += 1
    else:
        stats["updated"] += 1
    return row[0]


def seed_taxonomy(cur, taxonomy=PRODUCT_CATEGORIES):
    """Adds or updates each category by slug (main categories first). Never deletes."""
    validate_taxonomy(taxonomy)

    stats = {"inserted": 0, "updated": 0, "unchanged": 0}
    slug_ids = {}

    parent_ids = []
    for index, parent in enumerate(taxonomy, start=1):
        parent_ids.append(_upsert_category(cur, parent, None, index, stats))
        slug_ids[parent["slug"]] = parent_ids[-1]

    for parent, parent_id in zip(taxonomy, parent_ids):
        for index, child in enumerate(parent.get("children") or [], start=1):
            slug_ids[child["slug"]] = _upsert_category(cur, child, parent_id, index, stats)

    cur.execute(
        "SELECT slug FROM product_categories WHERE NOT (slug = ANY(%s)) ORDER BY slug;",
        (_config_slugs(taxonomy),)
    )
    unknown = [row[0] for row in cur.fetchall()]
    warnings = [
        f"Category slug {slug!r} exists in the database but not in config; left unchanged."
        for slug in unknown
    ]

    return {
        "inserted": stats["inserted"],
        "updated": stats["updated"],
        "unchanged": stats["unchanged"],
        "slug_ids": slug_ids,
        "warnings": warnings,
    }


# Looks up listings.category_id on the same listings table the changes above use
LISTINGS_CATEGORY_ATTRIBUTE = """
    SELECT a.attnotnull
    FROM pg_attribute a
    WHERE a.attrelid = 'listings'::regclass
      AND a.attname = 'category_id'
      AND NOT a.attisdropped;
"""


def _listings_column_exists(cur):
    cur.execute(LISTINGS_CATEGORY_ATTRIBUTE)
    return cur.fetchone() is not None


def _listing_category_fk_exists(cur):
    cur.execute("""
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_listing_category'
          AND conrelid = 'listings'::regclass;
    """)
    return cur.fetchone() is not None


def apply_product_categories(cur, taxonomy=PRODUCT_CATEGORIES):
    """
    Creates the category table, adds listings.category_id, and puts listings
    with no category into "Other". Safe to run more than once. Does not commit.
    """
    cur.execute(CREATE_PRODUCT_CATEGORIES_TABLE)
    cur.execute(CREATE_PRODUCT_CATEGORIES_PARENT_INDEX)

    seed = seed_taxonomy(cur, taxonomy)
    other_id = int(seed["slug_ids"][OTHER_SLUG])

    column_added = not _listings_column_exists(cur)
    cur.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS category_id INTEGER;")

    fk_added = False
    if not _listing_category_fk_exists(cur):
        cur.execute("""
            ALTER TABLE listings
            ADD CONSTRAINT fk_listing_category
                FOREIGN KEY (category_id)
                REFERENCES product_categories(id)
                ON DELETE RESTRICT;
        """)
        fk_added = True

    # Only listings with no category; updated_at is left alone
    cur.execute("UPDATE listings SET category_id = %s WHERE category_id IS NULL;", (other_id,))
    backfilled = cur.rowcount

    cur.execute("ALTER TABLE listings ALTER COLUMN category_id SET DEFAULT %s;" % other_id)
    cur.execute("ALTER TABLE listings ALTER COLUMN category_id SET NOT NULL;")
    cur.execute(CREATE_LISTINGS_CATEGORY_INDEX)

    return {
        "categories_inserted": seed["inserted"],
        "categories_updated": seed["updated"],
        "categories_unchanged": seed["unchanged"],
        "warnings": seed["warnings"],
        "other_category_id": other_id,
        "column_added": column_added,
        "fk_added": fk_added,
        "listings_backfilled": backfilled,
    }


# ________________________________________________________
# VERIFICATION HELPERS
# ________________________________________________________

def _existing_counted_tables(cur):
    existing = []
    for table in COUNTED_TABLES:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL;", (table,))
        if cur.fetchone()[0]:
            existing.append(table)
    return existing


def _lock_counted_tables(cur):
    """
    Pauses writes to the listing tables while the migration runs (reads still work),
    so the before/after counts can be compared.
    """
    tables = _existing_counted_tables(cur)
    if tables:
        # table names come from the COUNTED_TABLES constant, never from input
        cur.execute(f"LOCK TABLE {', '.join(tables)} IN SHARE MODE;")
    return tables


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


def _listing_timestamp_fingerprint(cur):
    """Fingerprint of every listing's dates, to prove they didn't change."""
    cur.execute("""
        SELECT md5(COALESCE(string_agg(
                   id::text || '|' || COALESCE(created_at::text, '') || '|' || COALESCE(updated_at::text, ''),
                   ',' ORDER BY id), ''))
        FROM listings;
    """)
    return cur.fetchone()[0]


def _verify(cur, taxonomy, before_counts, after_counts, before_fp, after_fp):
    results = {}
    failures = []

    results["row_counts_unchanged"] = before_counts == after_counts
    if not results["row_counts_unchanged"]:
        failures.append(f"Row counts changed: before={before_counts} after={after_counts}")

    results["listing_timestamps_unchanged"] = before_fp == after_fp
    if not results["listing_timestamps_unchanged"]:
        failures.append("listings.created_at/updated_at changed during the migration.")

    cur.execute("SELECT COUNT(*) FROM listings WHERE category_id IS NULL;")
    results["listings_with_null_category"] = cur.fetchone()[0]
    if results["listings_with_null_category"] != 0:
        failures.append(f"{results['listings_with_null_category']} listings still have a NULL category_id.")

    cur.execute("""
        SELECT COUNT(*)
        FROM listings l
        LEFT JOIN product_categories c ON c.id = l.category_id
        WHERE c.id IS NULL;
    """)
    results["listings_with_missing_category"] = cur.fetchone()[0]
    if results["listings_with_missing_category"] != 0:
        failures.append(f"{results['listings_with_missing_category']} listings point at a missing category.")

    parent_slugs = [parent["slug"] for parent in taxonomy]
    cur.execute("""
        SELECT COUNT(*)
        FROM product_categories
        WHERE slug = ANY(%s) AND parent_id IS NULL AND is_active = TRUE;
    """, (parent_slugs,))
    results["active_config_parents"] = cur.fetchone()[0]
    if results["active_config_parents"] != len(parent_slugs):
        failures.append(
            f"Expected {len(parent_slugs)} active parent categories, found {results['active_config_parents']}."
        )

    cur.execute("SELECT COUNT(*) FROM product_categories WHERE parent_id IS NULL AND is_active = TRUE;")
    results["active_parents_total"] = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM product_categories c
        JOIN product_categories p ON p.id = c.parent_id
        WHERE p.parent_id IS NOT NULL;
    """)
    results["categories_deeper_than_two_levels"] = cur.fetchone()[0]
    if results["categories_deeper_than_two_levels"] != 0:
        failures.append("Some categories are nested more than two levels deep.")

    cur.execute(LISTINGS_CATEGORY_ATTRIBUTE)
    row = cur.fetchone()
    results["category_id_not_null"] = bool(row and row[0])
    if not results["category_id_not_null"]:
        failures.append("listings.category_id is not NOT NULL.")

    results["fk_listing_category_present"] = _listing_category_fk_exists(cur)
    if not results["fk_listing_category_present"]:
        failures.append("fk_listing_category is missing.")

    results["passed"] = not failures
    if failures:
        raise MigrationVerificationError("Verification failed; rolled back. " + " | ".join(failures))
    return results


# ________________________________________________________
# ENTRY POINT
# ________________________________________________________

def run_migration(conn, dry_run=False, taxonomy=PRODUCT_CATEGORIES):
    """Runs the migration in one transaction. dry_run=True undoes it at the end. Returns a summary."""
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute("SET LOCAL lock_timeout = '5s';")
        cur.execute("SELECT pg_advisory_xact_lock(%s);", (ADVISORY_LOCK_KEY,))
        _lock_counted_tables(cur)

        counts_before = _table_counts(cur)
        fingerprint_before = _listing_timestamp_fingerprint(cur)

        applied = apply_product_categories(cur, taxonomy)

        counts_after = _table_counts(cur)
        fingerprint_after = _listing_timestamp_fingerprint(cur)

        verification = _verify(
            cur, taxonomy, counts_before, counts_after, fingerprint_before, fingerprint_after
        )

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
        "categories_in_config": len(_config_slugs(taxonomy)),
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
    parser = argparse.ArgumentParser(description="Add product categories and backfill listings to 'Other'.")
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
