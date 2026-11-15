# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
models/category_model.py

This file has the database queries for the product_categories table.
"""

from db import get_connection
from models.listing_model import PUBLIC_LISTING_VISIBILITY_SQL


# One category plus its parent's slug and name and how many active subcategories it has
CATEGORY_SELECT = """
    SELECT c.id, c.slug, c.name, c.parent_id, c.description, c.icon, c.is_active,
           p.slug, p.name,
           (SELECT COUNT(*) FROM product_categories ch
            WHERE ch.parent_id = c.id AND ch.is_active = TRUE)
    FROM product_categories c
    LEFT JOIN product_categories p ON p.id = c.parent_id
"""


def _row_to_category(row):
    return {
        "id": row[0],
        "slug": row[1],
        "name": row[2],
        "parent_id": row[3],
        "description": row[4],
        "icon": row[5],
        "is_active": bool(row[6]),
        "parent_slug": row[7],
        "parent_name": row[8],
        "child_count": int(row[9]),
    }


def get_category_tree():
    """Returns the active main categories in order, each with its active subcategories."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, slug, name, parent_id, description, icon
        FROM product_categories
        WHERE is_active = TRUE
        ORDER BY sort_order ASC, id ASC;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    nodes = {}
    for row in rows:
        nodes[row[0]] = {
            "id": row[0],
            "slug": row[1],
            "name": row[2],
            "parent_id": row[3],
            "description": row[4],
            "icon": row[5],
            "children": [],
        }

    # Subcategories of a turned off main category get left out
    tree = []
    for node in nodes.values():
        if node["parent_id"] is None:
            tree.append(node)
        elif node["parent_id"] in nodes:
            nodes[node["parent_id"]]["children"].append(node)
    return tree


def get_category_by_slug(slug):
    """Gets one category by its slug, active or not. Returns None if it isn't found."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(CATEGORY_SELECT + " WHERE c.slug = %s;", (slug,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return _row_to_category(row) if row else None


def get_category_by_id(category_id):
    """Gets one category by its id, active or not. Returns None if it isn't found."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(CATEGORY_SELECT + " WHERE c.id = %s;", (category_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return _row_to_category(row) if row else None


def get_child_categories(parent_id):
    """Returns the active subcategories of a main category in order."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        CATEGORY_SELECT + " WHERE c.parent_id = %s AND c.is_active = TRUE ORDER BY c.sort_order ASC, c.id ASC;",
        (parent_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [_row_to_category(row) for row in rows]


def get_visible_listing_counts(category_ids):
    """Counts the listings shoppers can see in each category. Categories with none are left out."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT l.category_id, COUNT(*)
        FROM listings l
        JOIN storefronts s ON s.id = l.storefront_id
        WHERE {PUBLIC_LISTING_VISIBILITY_SQL}
          AND l.category_id = ANY(%s)
        GROUP BY l.category_id;
    """, (list(category_ids),))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    counts = {}
    for category_id, count in rows:
        counts[category_id] = int(count)
    return counts
