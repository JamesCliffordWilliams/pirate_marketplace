# The Vault Campus Marketplace
# CSC 405 Sp 26'
# Updated by Day Ekoi - 4/22/26
#updated by Aniya Hopson - 10/25/26 ( stock and order are saved tg)

import random
import string
from datetime import datetime

from models.checkout_model import (
    get_order_by_confirmation,
    get_order_items_by_order_id,
    get_orders_by_user_id,
    clear_cart_for_user,
    remove_purchased_from_wishlist,
)

from models.order_model import place_order, expire_old_orders  # Added by Aniya Hopson team 10/26/26


def _generate_confirmation_number():
    date_str = datetime.now().strftime("%y%m%d")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PM-{date_str}-{suffix}"


def complete_transaction_from_session(user_id, session_cart, buyer_details):
    """
    Completes checkout using session cart and submitted buyer details.

    buyer_details keys: first_name, last_name, email, contact, meeting_location
    session_cart items: { id, name, price, quantity, size }
    """
    if not session_cart:
        raise Exception("Cart is empty.")

    buyer = {
        "first_name":(buyer_details.get("first_name") or "").strip(),
        "last_name": (buyer_details.get("last_name") or "").strip(),
        "email": (buyer_details.get("email") or "").strip(),
        "contact": (buyer_details.get("contact") or "").strip(),
        "meeting_location": (buyer_details.get("meeting_location") or "").strip()
    }

    if not all(buyer.values()):
            raise Exception ("All buyer details are required.")
    items = []
    for item in session_cart:
        items.append({
            "listing_id": int(item["id"]) if item.get("id") else None,
            "name": item.get("name", "Item"),
            "quantity": int(item.get("quantity", 1)),
            "price": float(item.get("price", 0)),
            "size": item.get("size") or None,
        })
    total_amount = round(sum(i["price"] * i["quantity"] for i in items), 2)
    confirmation_number = _generate_confirmation_number()

    expire_old_orders()  # put back stock from overdue orders first, so this buyer can get it
    order_id = place_order(user_id, confirmation_number, buyer, items, total_amount)

    clear_cart_for_user(user_id)

    # Remove purchased listings from the user's wishlist
    try:
        remove_purchased_from_wishlist(user_id, [i["listing_id"] for i in items])
    except Exception as e:
        print(f"[checkout] wishlist cleanup failed: {e}")

    return {
        "confirmation_number": confirmation_number,
        "order": get_order_by_confirmation(confirmation_number),
        "order_items": get_order_items_by_order_id(order_id),
        "total_amount": total_amount,
    }

def get_order_summary_service(confirmation_number, user_id):
    """Returns order + items for the confirmation page. Validates user ownership."""
    expire_old_orders() # Added By Aniya Hopson 10/26/26
    order = get_order_by_confirmation(confirmation_number)
    if not order:
        raise Exception("Order not found.")
    if order["user_id"] != user_id:
        raise Exception("Access denied.")
    items = get_order_items_by_order_id(order["id"])
    return {"order": order, "order_items": items}


def get_user_orders_service(user_id):
    """Returns all orders for the given user, newest first."""
    expire_old_orders() # Added By Aniya Hopson 10/26/26
    return get_orders_by_user_id(user_id)
