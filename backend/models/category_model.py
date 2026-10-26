# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
models/category_model.py

Purpose:
Database queries for the product_categories table.

It will:
- Return the category tree
- Look up one category by slug or id
- Return the subcategories of a main category
- Count the listings shoppers can see in each category
"""

from db import get_connection
from models.listing_model import PUBLIC_LISTING_VISIBILITY_SQL


CATEGORY_COLUMNS = """
    c.id, c.slug, c.name, c.parent_id, c.description, c.icon, c.sort_order, c.is_active,
    p.slug, p.name,
    (SELECT COUNT(*) FROM product_categories ch
     WHERE ch.parent_id = c.id AND ch.is_active = TRUE) AS child_count
"""


def _row_to_category(row):
    return {
        "id": row[0],
        "slug": row[1],
        "name": row[2],
        "parent_id": row[3],
        "description": row[4],
        "icon": row[5],
        "sort_order": row[6],
        "is_active": bool(row[7]),
        "parent_slug": row[8],
        "parent_name": row[9],
        "child_count": int(row[10]),
    }


def get_category_tree(active_only=True):
    """
    Returns parents (ordered) each with an ordered "children" list.
    With active_only, inactive categories (and children of inactive parents) are left out.
    """
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT id, slug, name, parent_id, description, icon, sort_order, is_active
        FROM product_categories
        WHERE (%s = FALSE OR is_active = TRUE)
        ORDER BY sort_order ASC, id ASC;
    """
    cur.execute(query, (active_only,))
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
            "sort_order": row[6],
            "is_active": bool(row[7]),
            "children": [],
        }

    tree = []
    for node in nodes.values():
        if node["parent_id"] is None:
            tree.append(node)
        elif node["parent_id"] in nodes:
            nodes[node["parent_id"]]["children"].append(node)

    return tree


def get_category_by_slug(slug):
    """
    Retrieves one category by slug (active or not). Returns None if not found.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT {CATEGORY_COLUMNS}
        FROM product_categories c
        LEFT JOIN product_categories p ON p.id = c.parent_id
        WHERE c.slug = %s;
    """, (slug,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    return _row_to_category(row) if row else None


def get_category_by_id(category_id):
    """
    Retrieves one category by id (active or not). Returns None if not found.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT {CATEGORY_COLUMNS}
        FROM product_categories c
        LEFT JOIN product_categories p ON p.id = c.parent_id
        WHERE c.id = %s;
    """, (category_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    return _row_to_category(row) if row else None


def get_child_categories(parent_id, active_only=True):
    """
    Returns the children of a parent category in sort order.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT {CATEGORY_COLUMNS}
        FROM product_categories c
        LEFT JOIN product_categories p ON p.id = c.parent_id
        WHERE c.parent_id = %s
          AND (%s = FALSE OR c.is_active = TRUE)
        ORDER BY c.sort_order ASC, c.id ASC;
    """, (parent_id, active_only))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [_row_to_category(row) for row in rows]


def get_visible_listing_counts(category_ids):
    """
    Returns {category_id: count} of publicly visible listings for each id.
    Ids with no visible listings are returned with 0.
    """
    category_ids = [int(category_id) for category_id in category_ids]
    if not category_ids:
        return {}

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT l.category_id, COUNT(*)
        FROM listings l
        JOIN storefronts s ON s.id = l.storefront_id
        WHERE {PUBLIC_LISTING_VISIBILITY_SQL}
          AND l.category_id = ANY(%s)
        GROUP BY l.category_id;
    """, (category_ids,))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    counts = {category_id: 0 for category_id in category_ids}
    for category_id, count in rows:
        counts[category_id] = int(count)
    return counts
