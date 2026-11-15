# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
models/interest_model.py

This file has the database code for listing_interest, which tracks what shoppers do for the Hot page.
There's at most one row per listing, shopper, kind and day.
Owners clicking their own listings and hidden listings are never saved.
If the table doesn't exist yet, the Hot queries just return nothing instead of crashing.
"""

from psycopg2 import errors

from db import get_connection
from config.hot_ranking import WEIGHTS, MIN_ACCOUNT_AGE_HOURS
from models.listing_model import PUBLIC_LISTING_VISIBILITY_SQL, AVAILABLE_SQL

# Tracking gives up after this long so it never slows down wishlist, cart or checkout
TRACKING_TIMEOUT_SECONDS = 2


# A shopper only counts if they aren't the storefront owner and their account was old enough at the time
COUNTED_ENGAGER_SQL = """
    li.user_id <> s.owner_id
    AND (%(min_age)s = 0 OR u.created_at IS NULL
         OR li.created_at - u.created_at >= make_interval(hours => %(min_age)s))
"""


def record_interest(listing_id, user_id, kind):
    """Saves one shopper action. Returns True if a new row was added."""
    return record_interests([listing_id], user_id, kind) > 0


def record_interests(listing_ids, user_id, kind):
    """
    Saves the same action for several listings using one connection.
    Gives up after TRACKING_TIMEOUT_SECONDS and returns how many rows were added.
    """
    if kind not in WEIGHTS:
        raise ValueError(f"Unknown interest kind: {kind!r}")
    if not listing_ids:
        return 0

    conn = get_connection(connect_timeout=TRACKING_TIMEOUT_SECONDS)
    try:
        cur = conn.cursor()
        cur.execute("SET LOCAL statement_timeout = %s;", (TRACKING_TIMEOUT_SECONDS * 1000,))
        cur.execute(f"""
            INSERT INTO listing_interest (listing_id, user_id, kind)
            SELECT l.id, %s, %s
            FROM listings l
            JOIN storefronts s ON s.id = l.storefront_id
            WHERE l.id = ANY(%s)
              AND {PUBLIC_LISTING_VISIBILITY_SQL}
              AND s.owner_id <> %s
            ON CONFLICT (listing_id, user_id, kind, day) DO NOTHING
            RETURNING id;
        """, (user_id, kind, [int(listing_id) for listing_id in listing_ids], user_id))
        inserted = len(cur.fetchall())
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
    Gets each shopper's latest action of each kind on listings that are visible and in stock.
    age_hours is how long ago it happened, using the database clock.
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
    """Counts how many different shoppers interacted with each storefront's listings."""
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
