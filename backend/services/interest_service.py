# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
services/interest_service.py

This saves what shoppers do for the Hot page without getting in the way.
It uses its own connection and catches every error, so if tracking breaks
the wishlist, cart or checkout action still works the same.
"""

from psycopg2 import errors

from models.interest_model import record_interest, record_interests


def track_interest(listing_id, user_id, kind):
    """Returns True if a row was saved. It never raises an error."""
    try:
        if not listing_id or not user_id:
            return False
        return record_interest(int(listing_id), int(user_id), kind)
    except errors.UndefinedTable:
        # The table isn't there yet because the migration hasn't been run, so skip it
        return False
    except Exception as e:
        print(f"[interest] not recorded ({kind}, listing {listing_id}): {e}")
        return False


def track_order(user_id, order_items):
    """Saves an 'order' action for every listing in an order at once. It never raises an error."""
    try:
        listing_ids = [item.get("listing_id") for item in order_items or [] if item.get("listing_id")]
        if not user_id or not listing_ids:
            return 0
        return record_interests(list(dict.fromkeys(listing_ids)), int(user_id), "order")
    except errors.UndefinedTable:
        return 0
    except Exception as e:
        print(f"[interest] order not recorded: {e}")
        return 0
