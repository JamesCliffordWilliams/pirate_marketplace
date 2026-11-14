
"""
models/saved_payment_method_model.py

Purpose:
Handles database operations for saved payment methods.

Sensitive card information is handled by Stripe.
Only the Stripe payment method reference and
non-sensitive display information are stored here.
"""

from db import get_connection


def add_saved_payment_method(
    user_id,
    stripe_payment_method_id,
    card_brand,
    last_four,
    expiration_month,
    expiration_year
):
    """Save a user's Stripe payment method."""

    if not stripe_payment_method_id:
        raise ValueError("A valid Stripe payment method is required.")

    if not last_four or len(str(last_four)) != 4 or not str(last_four).isdigit():
        raise ValueError("Card last four must contain exactly four digits.")

    if not 1 <= int(expiration_month) <= 12:
        raise ValueError("Invalid expiration month.")

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO saved_payment_methods (
                user_id,
                stripe_payment_method_id,
                card_brand,
                last_four,
                expiration_month,
                expiration_year
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (stripe_payment_method_id) DO NOTHING
            RETURNING id, user_id, stripe_payment_method_id,
                      card_brand, last_four, expiration_month,
                      expiration_year, created_at;
        """, (
            user_id,
            stripe_payment_method_id,
            card_brand,
            str(last_four),
            int(expiration_month),
            int(expiration_year)
        ))

        row = cur.fetchone()

        if row is None:
            cur.execute("""
                SELECT id, user_id, stripe_payment_method_id,
                       card_brand, last_four, expiration_month,
                       expiration_year, created_at
                FROM saved_payment_methods
                WHERE stripe_payment_method_id = %s
                  AND user_id = %s;
            """, (stripe_payment_method_id, user_id))

            row = cur.fetchone()

        conn.commit()

        if row is None:
            return None

        return {
            "id": row[0],
            "user_id": row[1],
            "stripe_payment_method_id": row[2],
            "card_brand": row[3],
            "last_four": row[4],
            "expiration_month": row[5],
            "expiration_year": row[6],
            "created_at": row[7]
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


def get_saved_payment_methods(user_id):
    """Retrieve all saved payment methods belonging to a user."""

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, user_id, stripe_payment_method_id,
                   card_brand, last_four, expiration_month,
                   expiration_year, created_at
            FROM saved_payment_methods
            WHERE user_id = %s
            ORDER BY created_at DESC;
        """, (user_id,))

        rows = cur.fetchall()

        return [
            {
                "id": row[0],
                "user_id": row[1],
                "stripe_payment_method_id": row[2],
                "card_brand": row[3],
                "last_four": row[4],
                "expiration_month": row[5],
                "expiration_year": row[6],
                "created_at": row[7]
            }
            for row in rows
        ]

    finally:
        cur.close()
        conn.close()


def get_saved_payment_method_by_id(user_id, payment_method_id):
    """Retrieve one saved payment method owned by a specific user."""

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, user_id, stripe_payment_method_id,
                   card_brand, last_four, expiration_month,
                   expiration_year, created_at
            FROM saved_payment_methods
            WHERE id = %s AND user_id = %s;
        """, (payment_method_id, user_id))

        row = cur.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "user_id": row[1],
            "stripe_payment_method_id": row[2],
            "card_brand": row[3],
            "last_four": row[4],
            "expiration_month": row[5],
            "expiration_year": row[6],
            "created_at": row[7]
        }

    finally:
        cur.close()
        conn.close()


def delete_saved_payment_method(user_id, payment_method_id):
    """Delete a saved payment method belonging to a specific user."""

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            DELETE FROM saved_payment_methods
            WHERE id = %s AND user_id = %s;
        """, (payment_method_id, user_id))

        deleted = cur.rowcount > 0
        conn.commit()

        return deleted

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()
