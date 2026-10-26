# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
services/interest_service.py

Purpose:
Records shopper engagement for the Hot page without ever getting in the way.
track_interest() uses its own connection, catches every error, and never raises,
so tracking can't undo, slow down with an error, or change the action that called it.
"""

from psycopg2 import errors

from models.interest_model import record_interest


def track_interest(listing_id, user_id, kind):
    """Returns True if a row was recorded. Never raises."""
    try:
        if not listing_id or not user_id:
            return False
        return record_interest(int(listing_id), int(user_id), kind)
    except errors.UndefinedTable:
        # table not created yet (migration not run): do nothing
        return False
    except Exception as e:
        print(f"[interest] not recorded ({kind}, listing {listing_id}): {e}")
        return False


def track_order(user_id, order_items):
    """Records 'order' for each listing in a saved order. Never raises."""
    try:
        listing_ids = dict.fromkeys(item.get("listing_id") for item in order_items or [])
        for listing_id in listing_ids:
            track_interest(listing_id, user_id, "order")
    except Exception as e:
        print(f"[interest] order not recorded: {e}")
