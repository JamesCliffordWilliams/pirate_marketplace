# Created by James Williams - 11/14/26 - product reviews. Only buyers with a completed order can review

from db import get_connection


def get_review_summary(listing_id):
    """Returns the reviews (newest first), the average, and how many of each star rating."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.user_id, u.username, r.rating, r.body, TO_CHAR(r.created_at, 'Mon DD, YYYY')
                FROM reviews r JOIN users u ON u.id = r.user_id
                WHERE r.listing_id = %s ORDER BY r.created_at DESC;
            """, (listing_id,))
            rows = cur.fetchall()
    finally:
        conn.close()
    reviews = [{"user_id": r[0], "username": r[1], "rating": r[2], "body": r[3], "date": r[4]} for r in rows]
    counts = {star: sum(1 for r in reviews if r["rating"] == star) for star in range(5, 0, -1)}
    average = round(sum(r["rating"] for r in reviews) / len(reviews), 1) if reviews else 0
    return {"reviews": reviews, "average": average, "count": len(reviews), "counts": counts}


def has_completed_purchase(user_id, listing_id):
    """True once the seller has marked this buyer's order item as completed."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM order_items oi JOIN orders o ON o.id = oi.order_id
                WHERE o.user_id = %s AND oi.listing_id = %s AND oi.completed_at IS NOT NULL LIMIT 1;
            """, (user_id, listing_id))
            return cur.fetchone() is not None
    finally:
        conn.close()


def save_review(user_id, listing_id, rating, body):
    """Adds the review, or updates it if this buyer already reviewed the listing."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO reviews (user_id, listing_id, rating, body) VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, listing_id)
                DO UPDATE SET rating = EXCLUDED.rating, body = EXCLUDED.body, created_at = CURRENT_TIMESTAMP;
            """, (user_id, listing_id, rating, body))
        conn.commit()
    finally:
        conn.close()
