# Pirate Market Campus Marketplace
# Created by Aniya Hopson  - 10/25/26 - order completion and 30-day pickup window

"""
models/order_model.py

How an order works:
1. Checkout (place_order) takes the stock off the shelf and saves the order.
   The order gets a pickup deadline 30 days out (the expires_at default in init_db.py).
2. The seller hands the items over and clicks "Mark as Picked Up" (complete_order).
   The stock stays sold.
3. If the deadline passes first, expire_old_orders marks the order EXPIRED
   and puts the stock back.
"""

from db import get_connection


def _change_stock(cur, listing_id, size, amount):
    """
    Changes a listing's stock by `amount`: negative takes stock (checkout),
    positive puts it back (expired order).

    FOR UPDATE locks the listing row until the transaction ends, so two
    buyers can't both buy the last item at the same moment.
    """
    cur.execute("""
        SELECT title, status, quantity_on_hand, is_made_to_order, fulfillment_type
        FROM listings WHERE id = %s FOR UPDATE;
    """, (listing_id,))
    row = cur.fetchone()
    if row is None:
        if amount < 0:
            raise Exception("An item in your bag is no longer available.")
        return
    title, status, on_hand, made_to_order, fulfillment_type = row

    if amount < 0 and status != "ACTIVE":
        raise Exception(f'"{title}" is sold out.' if status == "SOLD_OUT" else f'"{title}" is no longer available.')

    # Made-to-order and preorder items have no stock count.
    if made_to_order or fulfillment_type == "PREORDER":
        return

    cur.execute("""
        SELECT quantity FROM listing_sizes
        WHERE listing_id = %s AND size = %s FOR UPDATE;
    """, (listing_id, size))
    size_row = cur.fetchone()

    available = size_row[0] if size_row else on_hand
    if available is None:
        return  # this listing doesn't track stock
    if available + amount < 0:
        raise Exception(f'Only {available} of "{title}" left.')

    if size_row:
        # Change the size's count, then make the listing total match the sizes.
        cur.execute("""
            UPDATE listing_sizes SET quantity = quantity + %s
            WHERE listing_id = %s AND size = %s;
        """, (amount, listing_id, size))
        cur.execute("""
            UPDATE listings
            SET quantity_on_hand = (SELECT SUM(quantity) FROM listing_sizes WHERE listing_id = %s)
            WHERE id = %s;
        """, (listing_id, listing_id))
    else:
        cur.execute("""
            UPDATE listings SET quantity_on_hand = quantity_on_hand + %s WHERE id = %s;
        """, (amount, listing_id))

    # SOLD_OUT at zero, back to ACTIVE when stock returns.
    cur.execute("""
        UPDATE listings
        SET status = CASE
                WHEN quantity_on_hand = 0 AND status = 'ACTIVE' THEN 'SOLD_OUT'
                WHEN quantity_on_hand > 0 AND status = 'SOLD_OUT' THEN 'ACTIVE'
                ELSE status
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s;
    """, (listing_id,))


def place_order(user_id, confirmation_number, buyer, items, total_amount):
    """
    Takes the stock and saves the order and its items in ONE transaction:
    if any item is short, nothing is saved. Returns the new order's id.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Lock listings in id order so two checkouts never wait on each other forever.
        for item in sorted(items, key=lambda i: i["listing_id"] or 0):
            if item["listing_id"]:
                _change_stock(cur, item["listing_id"], item["size"], -item["quantity"])

        cur.execute("""
            INSERT INTO orders (user_id, confirmation_number, buyer_first_name, buyer_last_name,
                                buyer_email, buyer_contact, buyer_meeting_location, total_amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (user_id, confirmation_number, buyer["first_name"], buyer["last_name"],
              buyer["email"], buyer["contact"], buyer["meeting_location"], total_amount))
        order_id = cur.fetchone()[0]

        for item in items:
            cur.execute("""
                INSERT INTO order_items (order_id, listing_id, item_name, quantity,
                                         price_at_purchase, selected_size)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (order_id, item["listing_id"], item["name"], item["quantity"],
                  item["price"], item["size"]))

        conn.commit()
        return order_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def expire_old_orders():
    """
    Marks open orders past their deadline EXPIRED and puts back the stock for
    items the seller didn't hand over. Returns how many orders expired.

    Only SUBMITTED orders are changed, so running this twice never returns stock twice.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE orders SET order_status = 'EXPIRED'
            WHERE order_status = 'SUBMITTED' AND expires_at < CURRENT_TIMESTAMP
            RETURNING id;
        """)
        order_ids = [row[0] for row in cur.fetchall()]

        if order_ids:
            cur.execute("""
                SELECT listing_id, selected_size, quantity FROM order_items
                WHERE order_id = ANY(%s) AND completed_at IS NULL AND listing_id IS NOT NULL
                ORDER BY listing_id;
            """, (order_ids,))
            for listing_id, size, quantity in cur.fetchall():
                _change_stock(cur, listing_id, size, quantity)

        conn.commit()
        return len(order_ids)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def get_seller_orders(storefront_id):
    """Orders that include this storefront's listings, newest first, with only this seller's items."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.id, o.confirmation_number, o.buyer_first_name || ' ' || o.buyer_last_name,
               o.buyer_contact, o.buyer_meeting_location, o.order_status,
               TO_CHAR(o.expires_at, 'Mon DD, YYYY'),
               oi.item_name, oi.selected_size, oi.quantity, oi.completed_at IS NOT NULL
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        JOIN listings l ON l.id = oi.listing_id
        WHERE l.storefront_id = %s
        ORDER BY o.created_at DESC, oi.id;
    """, (storefront_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    orders = {}
    for r in rows:
        if r[0] not in orders:
            orders[r[0]] = {
                "id": r[0],
                "confirmation_number": r[1],
                "buyer_name": r[2],
                "buyer_contact": r[3],
                "buyer_meeting_location": r[4],
                "order_status": r[5],
                "pickup_by": r[6],
                "items": [],
            }
        orders[r[0]]["items"].append({
            "item_name": r[7],
            "selected_size": r[8],
            "quantity": r[9],
            "picked_up": r[10],
        })
    return list(orders.values())


def complete_order(order_id, storefront_id):
    """
    The seller marks their items in the order as handed over. When every item
    is handed over, the order becomes COMPLETED. Returns the order's status.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Find the order only if this seller has items in it, and lock it.
        cur.execute("""
            SELECT order_status, expires_at < CURRENT_TIMESTAMP FROM orders o
            WHERE id = %s AND EXISTS (
                SELECT 1 FROM order_items oi JOIN listings l ON l.id = oi.listing_id
                WHERE oi.order_id = o.id AND l.storefront_id = %s)
            FOR UPDATE;
        """, (order_id, storefront_id))
        row = cur.fetchone()
        if row is None:
            raise Exception("Order not found.")
        status, past_deadline = row
        if status != "SUBMITTED":
            raise Exception(f"This order is already {status.lower()}.")
        if past_deadline:
            raise Exception("This order's pickup window has ended.")

        # Mark this seller's items handed over.
        cur.execute("""
            UPDATE order_items oi SET completed_at = CURRENT_TIMESTAMP
            FROM listings l
            WHERE l.id = oi.listing_id AND oi.order_id = %s
              AND l.storefront_id = %s AND oi.completed_at IS NULL;
        """, (order_id, storefront_id))

        # Complete the order if no item is still waiting.
        cur.execute("""
            UPDATE orders SET order_status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
            WHERE id = %s AND NOT EXISTS (
                SELECT 1 FROM order_items oi JOIN listings l ON l.id = oi.listing_id
                WHERE oi.order_id = %s AND oi.completed_at IS NULL)
            RETURNING order_status;
        """, (order_id, order_id))
        new_status = "COMPLETED" if cur.fetchone() else "SUBMITTED"

        conn.commit()
        return new_status
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()