# Created by James Williams - 11/14/26 - product reviews: posting, updating, who can review, and the rating summary

import os
import sys
import unittest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path += [os.path.dirname(BACKEND_ROOT), BACKEND_ROOT]

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema
from app import create_app


@require_local_db
class TestReviews(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = ThrowawaySchema(prefix="test_reviews").create()
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.db.drop()

    def setUp(self):
        self.listing = self.db.add_listing(self.db.add_storefront(), "Hoodie")
        self.buyer = self.add_buyer()

    def add_buyer(self, completed=True):
        """Makes a user with an order for the hoodie. completed=False means the seller hasn't handed it over yet."""
        user_id = self.db.add_user()
        order_id = self.db.scalar("""
            INSERT INTO orders (user_id, confirmation_number, buyer_first_name, buyer_last_name, buyer_email,
                                buyer_contact, buyer_meeting_location, total_amount)
            VALUES (%s, %s, 'A', 'B', 'a@example.com', '555', 'Library', 10) RETURNING id;
        """, (user_id, f"PM-{user_id}"))
        self.db.execute("""
            INSERT INTO order_items (order_id, listing_id, item_name, quantity, price_at_purchase, completed_at)
            VALUES (%s, %s, 'Hoodie', 1, 10, CASE WHEN %s THEN CURRENT_TIMESTAMP END);
        """, (order_id, self.listing, completed))
        return user_id

    def client_for(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess["user"] = "shopper"
            sess["user_id"] = user_id
        return client

    def post_review(self, user_id, rating, body="Great fit"):
        return self.client_for(user_id).post(f"/listings/{self.listing}/reviews", json={"rating": rating, "body": body})

    def review_rows(self):
        return self.db.execute("SELECT user_id, rating, body FROM reviews WHERE listing_id = %s;", (self.listing,))

    def test_buyer_can_post_review(self):
        page = self.client_for(self.buyer).get(f"/listings/{self.listing}").get_data(as_text=True)
        self.assertIn('id="reviews" open', page)  # opens on its own so buyers see the form

        response = self.post_review(self.buyer, 5)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.review_rows(), [(self.buyer, 5, "Great fit")])

        page = self.client_for(self.buyer).get(f"/listings/{self.listing}").get_data(as_text=True)
        self.assertIn("Great fit", page)
        self.assertIn("Update review", page)

    def test_posting_again_updates_the_same_review(self):
        self.post_review(self.buyer, 5, "Great fit")
        self.assertEqual(self.post_review(self.buyer, 2, "Shrank in the wash").status_code, 201)
        self.assertEqual(self.review_rows(), [(self.buyer, 2, "Shrank in the wash")])

    def test_only_buyers_with_a_completed_order_can_review(self):
        never_bought = self.db.add_user()
        not_handed_over = self.add_buyer(completed=False)
        for user_id in (never_bought, not_handed_over):
            self.assertEqual(self.post_review(user_id, 5).status_code, 403, user_id)
            page = self.client_for(user_id).get(f"/listings/{self.listing}").get_data(as_text=True)
            self.assertNotIn('id="reviewForm"', page)
        self.assertEqual(self.review_rows(), [])

    def test_rating_must_be_a_whole_number_from_1_to_5(self):
        for rating in (0, 6, "5", 4.5, True, None):
            self.assertEqual(self.post_review(self.buyer, rating).status_code, 400, repr(rating))
        self.assertEqual(self.post_review(self.buyer, 5, "x" * 2001).status_code, 400)
        self.assertEqual(self.review_rows(), [])

    def test_average_and_star_counts(self):
        from models.review_model import get_review_summary
        for rating in (5, 4, 4):
            self.assertEqual(self.post_review(self.add_buyer(), rating).status_code, 201)

        summary = get_review_summary(self.listing)
        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["average"], 4.3)
        self.assertEqual(summary["counts"], {5: 1, 4: 2, 3: 0, 2: 0, 1: 0})

        page = self.client_for(self.buyer).get(f"/listings/{self.listing}").get_data(as_text=True)
        self.assertIn("4.3 · 3 reviews", page)

    def test_listing_with_no_reviews(self):
        from models.review_model import get_review_summary
        self.assertEqual(get_review_summary(self.listing),
                         {"reviews": [], "average": 0, "count": 0, "counts": {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}})
        page = self.client_for(self.buyer).get(f"/listings/{self.listing}").get_data(as_text=True)
        self.assertIn("No reviews yet.", page)
        self.assertNotIn('class="pm-rating"', page)


if __name__ == "__main__":
    unittest.main()
