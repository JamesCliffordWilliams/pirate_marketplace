# The Vault Campus Marketplace
# CSC 405 Sp 26'
# Created by Day Ekoi - Iteration 3
# Updated by Day Ekoi - Iteration 5 - 4/20/26 - added primary image JOIN to get_listings_by_storefront_id
# Updated by James Williams - 10/26/26 - added category_id to listings and browse_public_listings
# Updated by James Williams - 10/26/26 - Hot page: listing_ids / available_only filters, newest available listings
# Updated by James Williams - 10/26/26 - cursor inserts for the one-transaction create

"""
models/listing_model.py

Purpose:
This file handles all direct database operations related to listings.

This file includes DB operations for:
- listings (core listing data)
- listing_images (image URLs + primary image)
- listing_sizes (size-based inventory)

It will:
- Insert new listing records
- Retrieve listing data
- Update listing data
- Soft delete listings (status = 'DELETED')
- Insert/retrieve/update/delete listing image records
- Insert/retrieve/update/delete listing size inventory records
- Return results as dictionaries
- Browse public listings across storefronts (category pages and the Hot page)
"""

from db import get_connection


# Added by James Williams 10/26/26
# Shoppers can see ACTIVE and SOLD_OUT listings from active storefronts
PUBLIC_LISTING_VISIBILITY_SQL = "l.status IN ('ACTIVE', 'SOLD_OUT') AND s.is_active IS TRUE"

# Sold out listings are shown after available ones (made-to-order is never sold out)
SOLD_OUT_SQL = (
    "(l.status = 'SOLD_OUT' OR (NOT COALESCE(l.is_made_to_order, FALSE)"
    " AND l.fulfillment_type = 'IN_STOCK' AND COALESCE(l.quantity_on_hand, 0) = 0))"
)

# Added by James Williams 10/26/26
# Can be added to the cart right now (same rule as add_to_cart and the card)
AVAILABLE_SQL = (
    "(l.status <> 'SOLD_OUT' AND (COALESCE(l.is_made_to_order, FALSE)"
    " OR l.quantity_on_hand IS NULL OR l.quantity_on_hand > 0))"
)

# Allowed sort orders
BROWSE_SORTS = {
    "newest": "l.created_at DESC",
    "price_asc": "l.price ASC",
    "price_desc": "l.price DESC",
}


def _category_info(category_id, slug, name, parent_slug, parent_name):
    """Returns the listing's category info, or None."""
    if category_id is None or slug is None:
        return None
    return {
        "id": category_id,
        "slug": slug,
        "name": name,
        "parent_slug": parent_slug,
        "parent_name": parent_name,
    }


# ________________________________________________________
# LISTINGS TABLE OPERATIONS
# ________________________________________________________

def create_listing(
    storefront_id,
    title,
    description,
    price,
    fulfillment_type,
    quantity_on_hand=None,
    sizes_available=None,
    status="ACTIVE",
    is_made_to_order=False,
    category_id=None
):
    """
    Inserts a new listing and returns the created listing as a dictionary.
    """
    conn = get_connection()
    cur = conn.cursor()
    listing = insert_listing(cur, storefront_id, title, description, price, fulfillment_type,
                             quantity_on_hand, sizes_available, status, is_made_to_order, category_id)
    conn.commit()

    cur.close()
    conn.close()
    return listing


# Added by James Williams 10/26/26
# Cursor versions of the inserts, so create listing can run them in one transaction.
# The caller commits.
def insert_listing(cur, storefront_id, title, description, price, fulfillment_type,
                   quantity_on_hand=None, sizes_available=None, status="ACTIVE",
                   is_made_to_order=False, category_id=None):
    cur.execute("""
        INSERT INTO listings
        (storefront_id, title, description, price, fulfillment_type, quantity_on_hand, sizes_available, status, is_made_to_order, category_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, storefront_id, title, description, price,
                  fulfillment_type, quantity_on_hand, sizes_available,
                  status, created_at, updated_at, is_made_to_order, category_id;
    """, (storefront_id, title, description, price, fulfillment_type, quantity_on_hand,
          sizes_available, status, bool(is_made_to_order), category_id))
    row = cur.fetchone()
    return {
        "id": row[0],
        "storefront_id": row[1],
        "title": row[2],
        "description": row[3],
        "price": float(row[4]),
        "fulfillment_type": row[5],
        "quantity_on_hand": row[6],
        "sizes_available": row[7],
        "status": row[8],
        "created_at": row[9],
        "updated_at": row[10],
        "is_made_to_order": row[11],
        "category_id": row[12],
    }


def insert_listing_image(cur, listing_id, image_url, is_primary=False):
    if is_primary:
        cur.execute("UPDATE listing_images SET is_primary = FALSE WHERE listing_id = %s;", (listing_id,))
    cur.execute("""
        INSERT INTO listing_images (listing_id, image_url, is_primary)
        VALUES (%s, %s, %s)
        RETURNING id, listing_id, image_url, is_primary, created_at;
    """, (listing_id, image_url, is_primary))
    row = cur.fetchone()
    return {"id": row[0], "listing_id": row[1], "image_url": row[2], "is_primary": row[3], "created_at": row[4]}


def insert_listing_size(cur, listing_id, size, quantity):
    cur.execute("""
        INSERT INTO listing_sizes (listing_id, size, quantity)
        VALUES (%s, %s, %s)
        ON CONFLICT (listing_id, size)
        DO UPDATE SET quantity = EXCLUDED.quantity
        RETURNING id, listing_id, size, quantity, created_at;
    """, (listing_id, size, quantity))
    row = cur.fetchone()
    return {"id": row[0], "listing_id": row[1], "size": row[2], "quantity": row[3], "created_at": row[4]}


def get_listing_by_id(listing_id):
    """
    Retrieves a listing by its PK (id).
    Returns None if not found.
    """
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT l.id, l.storefront_id, l.title, l.description, l.price,
               l.fulfillment_type, l.quantity_on_hand, l.sizes_available,
               l.status, l.storefront_restore_status, l.deleted_restore_status,
               l.created_at, l.updated_at,
               li.image_url, l.is_made_to_order,
               l.category_id, c.slug, c.name, p.slug, p.name
        FROM listings l
        LEFT JOIN listing_images li
            ON li.listing_id = l.id AND li.is_primary = TRUE
        LEFT JOIN product_categories c ON c.id = l.category_id
        LEFT JOIN product_categories p ON p.id = c.parent_id
        WHERE l.id = %s;
    """

    cur.execute(query, (listing_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "storefront_id": row[1],
        "title": row[2],
        "description": row[3],
        "price": float(row[4]),
        "fulfillment_type": row[5],
        "quantity_on_hand": row[6],
        "sizes_available": row[7],
        "status": row[8],
        "storefront_restore_status": row[9],
        "deleted_restore_status": row[10],
        "created_at": row[11],
        "updated_at": row[12],
        "image_url": row[13],
        "is_made_to_order": bool(row[14]) if row[14] is not None else False,
        "category_id": row[15],
        "category": _category_info(row[15], row[16], row[17], row[18], row[19]),
    }


def get_listings_by_storefront_id(storefront_id, include_deleted=False):
    """
    Retrieves all non-deleted listings for a storefront.
    Returns a list of listing dictionaries.
    """
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT l.id, l.storefront_id, l.title, l.description, l.price,
               l.fulfillment_type, l.quantity_on_hand, l.sizes_available,
               l.status, l.storefront_restore_status, l.deleted_restore_status,
               l.created_at, l.updated_at,
               li.image_url, l.is_made_to_order,
               l.category_id, c.slug, c.name, p.slug, p.name
        FROM listings l
        LEFT JOIN listing_images li
            ON li.listing_id = l.id AND li.is_primary = TRUE
        LEFT JOIN product_categories c ON c.id = l.category_id
        LEFT JOIN product_categories p ON p.id = c.parent_id
        WHERE l.storefront_id = %s
          AND (%s = TRUE OR l.status != 'DELETED')
        ORDER BY l.created_at DESC;
    """

    cur.execute(query, (storefront_id, include_deleted))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    listings = []
    for row in rows:
        listings.append({
            "id": row[0],
            "storefront_id": row[1],
            "title": row[2],
            "description": row[3],
            "price": float(row[4]),
            "fulfillment_type": row[5],
            "quantity_on_hand": row[6],
            "sizes_available": row[7],
            "status": row[8],
            "storefront_restore_status": row[9],
            "deleted_restore_status": row[10],
            "created_at": row[11],
            "updated_at": row[12],
            "image_url": row[13],
            "is_made_to_order": bool(row[14]) if row[14] is not None else False,
            "category_id": row[15],
            "category": _category_info(row[15], row[16], row[17], row[18], row[19]),
        })

    return listings


def update_listing(
    listing_id,
    title=None,
    description=None,
    price=None,
    fulfillment_type=None,
    quantity_on_hand=None,
    sizes_available=None,
    status=None,
    is_made_to_order=None,
    category_id=None
):
    """
    Updates editable listing fields using COALESCE and returns updated listing.
    Returns None if listing does not exist.
    """
    conn = get_connection()
    cur = conn.cursor()

    query = """
        UPDATE listings
        SET title = COALESCE(%s, title),
            description = COALESCE(%s, description),
            price = COALESCE(%s, price),
            fulfillment_type = COALESCE(%s, fulfillment_type),
            quantity_on_hand = COALESCE(%s, quantity_on_hand),
            sizes_available = COALESCE(%s, sizes_available),
            status = COALESCE(%s, status),
            is_made_to_order = COALESCE(%s, is_made_to_order),
            category_id = COALESCE(%s, category_id),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING id, storefront_id, title, description, price,
                  fulfillment_type, quantity_on_hand, sizes_available,
                  status, created_at, updated_at, is_made_to_order, category_id;
    """

    cur.execute(query, (
        title,
        description,
        price,
        fulfillment_type,
        quantity_on_hand,
        sizes_available,
        status,
        is_made_to_order,
        category_id,
        listing_id
    ))

    row = cur.fetchone()
    conn.commit()

    cur.close()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "storefront_id": row[1],
        "title": row[2],
        "description": row[3],
        "price": float(row[4]),
        "fulfillment_type": row[5],
        "quantity_on_hand": row[6],
        "sizes_available": row[7],
        "status": row[8],
        "created_at": row[9],
        "updated_at": row[10],
        "is_made_to_order": bool(row[11]) if row[11] is not None else False,
        "category_id": row[12],
    }


def soft_delete_listing(listing_id):
    """
    Soft deletes a listing by setting status = 'DELETED'.
    """
    conn = get_connection()
    cur = conn.cursor()

    query = """
        UPDATE listings
        SET deleted_restore_status = COALESCE(storefront_restore_status, status),
            storefront_restore_status = NULL,
            status = 'DELETED',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING id, storefront_id, title, description, price,
                  fulfillment_type, quantity_on_hand, sizes_available,
                  status, created_at, updated_at, is_made_to_order, category_id;
    """

    cur.execute(query, (listing_id,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "storefront_id": row[1],
        "title": row[2],
        "description": row[3],
        "price": float(row[4]),
        "fulfillment_type": row[5],
        "quantity_on_hand": row[6],
        "sizes_available": row[7],
        "status": row[8],
        "created_at": row[9],
        "updated_at": row[10],
        "is_made_to_order": bool(row[11]) if row[11] is not None else False,
        "category_id": row[12],
    }


def deactivate_listing(listing_id):
    return update_listing_status(listing_id, "INACTIVE", storefront_restore_status=None, deleted_restore_status=None)


def reactivate_listing(listing_id, restored_status):
    return update_listing_status(listing_id, restored_status, storefront_restore_status=None, deleted_restore_status=None)


def restore_deleted_listing(listing_id, restored_status, storefront_restore_status=None):
    return update_listing_status(
        listing_id,
        restored_status,
        storefront_restore_status=storefront_restore_status,
        deleted_restore_status=None
    )


def update_listing_status(listing_id, status, storefront_restore_status=None, deleted_restore_status=None):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        UPDATE listings
        SET status = %s,
            storefront_restore_status = %s,
            deleted_restore_status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING id, storefront_id, title, description, price,
                  fulfillment_type, quantity_on_hand, sizes_available,
                  status, storefront_restore_status, deleted_restore_status,
                  created_at, updated_at, is_made_to_order, category_id;
    """

    cur.execute(query, (status, storefront_restore_status, deleted_restore_status, listing_id))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "storefront_id": row[1],
        "title": row[2],
        "description": row[3],
        "price": float(row[4]),
        "fulfillment_type": row[5],
        "quantity_on_hand": row[6],
        "sizes_available": row[7],
        "status": row[8],
        "storefront_restore_status": row[9],
        "deleted_restore_status": row[10],
        "created_at": row[11],
        "updated_at": row[12],
        "is_made_to_order": bool(row[13]) if row[13] is not None else False,
        "category_id": row[14],
    }


def deactivate_active_listings_for_storefront(storefront_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE listings
        SET storefront_restore_status = status,
            status = 'INACTIVE',
            updated_at = CURRENT_TIMESTAMP
        WHERE storefront_id = %s
          AND status IN ('ACTIVE', 'SOLD_OUT');
    """, (storefront_id,))
    updated_count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return updated_count


def restore_listings_after_storefront_reactivation(storefront_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE listings
        SET status = storefront_restore_status,
            storefront_restore_status = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE storefront_id = %s
          AND status = 'INACTIVE'
          AND storefront_restore_status IS NOT NULL;
    """, (storefront_id,))
    updated_count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return updated_count


# ________________________________________________________
# BROWSE LISTINGS ACROSS ALL STOREFRONTS
# Added by James Williams 10/26/26
# ________________________________________________________

def browse_public_listings(category_ids=None, sort="newest", limit=24, offset=0,
                           listing_ids=None, available_only=False):  # Added by James Williams 10/26/26
    """
    Returns (listings, total) for listings shoppers can see, from every storefront.
    Each listing includes its images, sizes, storefront and category,
    so the page doesn't need extra requests per card.
    listing_ids: only these listings. available_only: skip sold out / out of stock.
    """
    # Added by James Williams 10/26/26
    if listing_ids is not None and len(listing_ids) == 0:
        return [], 0

    order_by = BROWSE_SORTS.get(sort, BROWSE_SORTS["newest"])

    where_clauses = [PUBLIC_LISTING_VISIBILITY_SQL]
    params = []
    if category_ids is not None:
        where_clauses.append("l.category_id = ANY(%s)")
        params.append(list(category_ids))
    # Added by James Williams 10/26/26
    if listing_ids is not None:
        where_clauses.append("l.id = ANY(%s)")
        params.append([int(listing_id) for listing_id in listing_ids])
    if available_only:
        where_clauses.append(AVAILABLE_SQL)
    where_sql = " AND ".join(where_clauses)

    conn = get_connection()
    cur = conn.cursor()

    query = f"""
        SELECT l.id, l.storefront_id, l.title, l.description, l.price,
               l.fulfillment_type, l.quantity_on_hand, l.sizes_available,
               l.status, l.is_made_to_order, l.created_at, l.updated_at,
               s.brand_name, s.logo_url,
               l.category_id, c.slug, c.name, p.slug, p.name,
               COALESCE(imgs.urls, ARRAY[]::TEXT[]) AS image_urls,
               COALESCE(sz.sizes, '[]'::JSON) AS sizes,
               {SOLD_OUT_SQL} AS is_sold_out,
               COUNT(*) OVER () AS total_count
        FROM listings l
        JOIN storefronts s ON s.id = l.storefront_id
        LEFT JOIN product_categories c ON c.id = l.category_id
        LEFT JOIN product_categories p ON p.id = c.parent_id
        LEFT JOIN LATERAL (
            SELECT array_agg(top_images.image_url ORDER BY top_images.rank) AS urls
            FROM (
                SELECT li.image_url,
                       ROW_NUMBER() OVER (
                           ORDER BY COALESCE(li.is_primary, FALSE) DESC, li.created_at ASC, li.id ASC
                       ) AS rank
                FROM listing_images li
                WHERE li.listing_id = l.id
            ) top_images
            WHERE top_images.rank <= 4
        ) imgs ON TRUE
        LEFT JOIN LATERAL (
            SELECT json_agg(json_build_object('size', ls.size, 'quantity', ls.quantity) ORDER BY ls.id) AS sizes
            FROM listing_sizes ls
            WHERE ls.listing_id = l.id
        ) sz ON TRUE
        WHERE {where_sql}
        ORDER BY is_sold_out ASC, {order_by}, l.id DESC
        LIMIT %s OFFSET %s;
    """

    cur.execute(query, (*params, limit, offset))
    rows = cur.fetchall()

    if rows:
        total = rows[0][22]
    elif offset > 0:
        # Past the last page: still return the real total
        cur.execute(f"""
            SELECT COUNT(*)
            FROM listings l
            JOIN storefronts s ON s.id = l.storefront_id
            WHERE {where_sql};
        """, tuple(params))
        total = cur.fetchone()[0]
    else:
        total = 0

    cur.close()
    conn.close()

    listings = []
    for row in rows:
        images = list(row[19] or [])
        listings.append({
            "id": row[0],
            "storefront_id": row[1],
            "title": row[2],
            "description": row[3],
            "price": float(row[4]),
            "fulfillment_type": row[5],
            "quantity_on_hand": row[6],
            "sizes_available": row[7],
            "status": row[8],
            "is_made_to_order": bool(row[9]) if row[9] is not None else False,
            "created_at": row[10],
            "updated_at": row[11],
            "storefront": {
                "id": row[1],
                "brand_name": row[12],
                "logo_url": row[13],
            },
            "category_id": row[14],
            "category": _category_info(row[14], row[15], row[16], row[17], row[18]),
            "image_url": images[0] if images else None,
            "images": images,
            "sizes": row[20] or [],
            "is_sold_out": bool(row[21]),
        })

    return listings, total


# Added by James Williams 10/26/26
def get_newest_available_listings(exclude_ids=(), per_storefront=2, limit=8):
    """Newest visible, in-stock listings as [{id, storefront_id}], at most per_storefront from each store."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT id, storefront_id
        FROM (
            SELECT l.id, l.storefront_id, l.created_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY l.storefront_id ORDER BY l.created_at DESC, l.id DESC
                   ) AS store_rank
            FROM listings l
            JOIN storefronts s ON s.id = l.storefront_id
            WHERE {PUBLIC_LISTING_VISIBILITY_SQL}
              AND {AVAILABLE_SQL}
              AND NOT (l.id = ANY(%s))
        ) ranked
        WHERE store_rank <= %s
        ORDER BY created_at DESC, id DESC
        LIMIT %s;
    """, ([int(listing_id) for listing_id in exclude_ids], per_storefront, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": row[0], "storefront_id": row[1]} for row in rows]


# ________________________________________________________
# LISTING IMAGES TABLE OPERATIONS
# ________________________________________________________

def add_listing_image(listing_id, image_url, is_primary=False):
    """
    Adds an image URL to a listing.
    Returns the created image record as a dictionary.
    """
    conn = get_connection()
    cur = conn.cursor()
    image = insert_listing_image(cur, listing_id, image_url, is_primary)
    conn.commit()

    cur.close()
    conn.close()
    return image


def get_images_for_listing(listing_id):
    """
    Returns all images for a listing (primary first).
    """
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT id, listing_id, image_url, is_primary, created_at
        FROM listing_images
        WHERE listing_id = %s
        ORDER BY is_primary DESC, created_at ASC;
    """
    cur.execute(query, (listing_id,))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    images = []
    for row in rows:
        images.append({
            "id": row[0],
            "listing_id": row[1],
            "image_url": row[2],
            "is_primary": row[3],
            "created_at": row[4],
        })

    return images


def set_primary_image(listing_id, image_id):
    """
    Marks a specific image as the primary image for that listing.
    Returns the updated image record, or None if not found.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE listing_images SET is_primary = FALSE WHERE listing_id = %s;",
        (listing_id,)
    )

    query = """
        UPDATE listing_images
        SET is_primary = TRUE
        WHERE id = %s AND listing_id = %s
        RETURNING id, listing_id, image_url, is_primary, created_at;
    """
    cur.execute(query, (image_id, listing_id))
    row = cur.fetchone()
    conn.commit()

    cur.close()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "listing_id": row[1],
        "image_url": row[2],
        "is_primary": row[3],
        "created_at": row[4],
    }


def delete_listing_image(image_id):
    """
    Deletes an image record by image_id.
    Returns True if something was deleted, False otherwise.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM listing_images WHERE id = %s;", (image_id,))
    deleted = cur.rowcount > 0
    conn.commit()

    cur.close()
    conn.close()

    return deleted


# ________________________________________________________
# LISTING SIZES TABLE OPERATIONS
# ________________________________________________________

def upsert_listing_size(listing_id, size, quantity):
    """
    Creates or updates a size row for a listing.
    Updates quantity if (listing_id, size) already exists.
    Returns the upserted row as a dictionary.
    """
    conn = get_connection()
    cur = conn.cursor()
    row = insert_listing_size(cur, listing_id, size, quantity)
    conn.commit()

    cur.close()
    conn.close()
    return row


def get_sizes_for_listing(listing_id):
    """
    Returns all size inventory rows for a listing.
    """
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT id, listing_id, size, quantity, created_at
        FROM listing_sizes
        WHERE listing_id = %s
        ORDER BY size ASC;
    """
    cur.execute(query, (listing_id,))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    sizes = []
    for row in rows:
        sizes.append({
            "id": row[0],
            "listing_id": row[1],
            "size": row[2],
            "quantity": row[3],
            "created_at": row[4],
        })

    return sizes


def delete_listing_size(listing_id, size):
    """
    Deletes a size row for a listing.
    Returns True if something was deleted, False otherwise.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM listing_sizes WHERE listing_id = %s AND size = %s;",
        (listing_id, size)
    )
    deleted = cur.rowcount > 0
    conn.commit()

    cur.close()
    conn.close()

    return deleted
