# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
models/interest_model.py

Purpose:
Database work for listing_interest (shopper engagement used by the Hot page).

Notes:
- At most one row per listing, shopper, kind and day.
- Owners' own actions and hidden listings are never recorded.
- If the table doesn't exist yet (code deployed before the migration),
  the Hot queries return no engagement instead of erroring.
"""

from psycopg2 import errors

from db import get_connection
from config.hot_ranking import INTEREST_KINDS, MIN_ACCOUNT_AGE_HOURS
from models.listing_model import PUBLIC_LISTING_VISIBILITY_SQL, AVAILABLE_SQL


# Shoppers who count: not the storefront owner, and the account was old enough at the time
COUNTED_ENGAGER_SQL = """
    li.user_id <> s.owner_id
    AND (%(min_age)s = 0 OR u.created_at IS NULL
         OR li.created_at - u.created_at >= make_interval(hours => %(min_age)s))
"""


def record_interest(listing_id, user_id, kind):
    """Saves one engagement. Returns True if a new row was added."""
    if kind not in INTEREST_KINDS:
        raise ValueError(f"Unknown interest kind: {kind!r}")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO listing_interest (listing_id, user_id, kind)
            SELECT l.id, %s, %s
            FROM listings l
            JOIN storefronts s ON s.id = l.storefront_id
            WHERE l.id = %s
              AND {PUBLIC_LISTING_VISIBILITY_SQL}
              AND s.owner_id <> %s
            ON CONFLICT (listing_id, user_id, kind, day) DO NOTHING
            RETURNING id;
        """, (user_id, kind, listing_id, user_id))
        inserted = cur.fetchone() is not None
        conn.commit()
        cur.close()
        return inserted
    finally:
        conn.close()


def is_listing_public(listing_id):
    """True if shoppers can see this listing."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT 1
            FROM listings l
            JOIN storefronts s ON s.id = l.storefront_id
            WHERE l.id = %s AND {PUBLIC_LISTING_VISIBILITY_SQL};
        """, (listing_id,))
        found = cur.fetchone() is not None
        cur.close()
        return found
    finally:
        conn.close()


def get_engagement_events(window_hours, min_account_age_hours=MIN_ACCOUNT_AGE_HOURS):
    """
    Latest event of each kind per (listing, shopper) in the window, for listings
    that are visible and in stock. Returns dicts with listing_id, storefront_id,
    user_id, kind and age_hours (worked out by the database clock).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT li.listing_id, l.storefront_id, li.user_id, li.kind,
                   EXTRACT(EPOCH FROM (LOCALTIMESTAMP - MAX(li.created_at))) / 3600.0 AS age_hours
            FROM listing_interest li
            JOIN listings l ON l.id = li.listing_id
            JOIN storefronts s ON s.id = l.storefront_id
            JOIN users u ON u.id = li.user_id
            WHERE li.created_at >= LOCALTIMESTAMP - make_interval(hours => %(window)s)
              AND {COUNTED_ENGAGER_SQL}
              AND {PUBLIC_LISTING_VISIBILITY_SQL}
              AND {AVAILABLE_SQL}
            GROUP BY li.listing_id, l.storefront_id, li.user_id, li.kind;
        """, {"window": int(window_hours), "min_age": int(min_account_age_hours)})
        rows = cur.fetchall()
        cur.close()
    except errors.UndefinedTable:
        return []
    finally:
        conn.close()

    return [
        {
            "listing_id": row[0],
            "storefront_id": row[1],
            "user_id": row[2],
            "kind": row[3],
            "age_hours": float(row[4]),
        }
        for row in rows
    ]


def get_storefront_reach(storefront_ids, days, min_account_age_hours=MIN_ACCOUNT_AGE_HOURS):
    """{storefront_id: number of different shoppers} across all of the store's listings."""
    if not storefront_ids:
        return {}

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT l.storefront_id, COUNT(DISTINCT li.user_id)
            FROM listing_interest li
            JOIN listings l ON l.id = li.listing_id
            JOIN storefronts s ON s.id = l.storefront_id
            JOIN users u ON u.id = li.user_id
            WHERE l.storefront_id = ANY(%(stores)s)
              AND li.created_at >= LOCALTIMESTAMP - make_interval(days => %(days)s)
              AND {COUNTED_ENGAGER_SQL}
            GROUP BY l.storefront_id;
        """, {"stores": [int(s) for s in storefront_ids], "days": int(days),
              "min_age": int(min_account_age_hours)})
        rows = cur.fetchall()
        cur.close()
    except errors.UndefinedTable:
        return {}
    finally:
        conn.close()

    return {row[0]: row[1] for row in rows}
