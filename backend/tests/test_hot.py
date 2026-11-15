# Created by James Williams - 10/26/26 - Hot ranking, the Hot API and the interest API

import os
import sys
import unittest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path += [os.path.dirname(BACKEND_ROOT), BACKEND_ROOT]

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema
from app import create_app
from services import hot_service
from services.hot_service import rank_hot, select_hot


def hot_events(listing_id, store_id, engagers):
    # One shopper saves it and the rest view it
    return [{"listing_id": listing_id, "storefront_id": store_id, "user_id": listing_id * 100 + i,
             "kind": "wishlist" if i == 0 else "detail_view", "age_hours": 1} for i in range(engagers)]


class TestHotRanking(unittest.TestCase):

    def test_most_engaged_first_and_two_per_store(self):
        events = hot_events(10, 1, 6) + hot_events(11, 1, 5) + hot_events(12, 1, 4)
        events += hot_events(20, 2, 3) + hot_events(21, 2, 3)
        # Listing 12 is the third one from store 1, so it gets left out
        self.assertEqual(select_hot(rank_hot(events)), [10, 11, 21, 20])

    def test_interest_needs_login(self):
        client = create_app().test_client()
        response = client.post("/api/listings/1/interest", json={"kind": "detail_view"})
        self.assertEqual(response.status_code, 401)


@require_local_db
class TestHotApi(unittest.TestCase):

    def setUp(self):
        hot_service.clear_ranking_cache()
        self.addCleanup(hot_service.clear_ranking_cache)
        self.db = ThrowawaySchema().create()
        self.addCleanup(self.db.drop)
        shoppers = [self.db.add_user(age_hours=500) for _ in range(3)]
        self.listings = []
        for i in range(3):
            listing = self.db.add_listing(self.db.add_storefront(), f"Hot {i}")
            self.listings.append(listing)
            for shopper, kind in zip(shoppers, ("wishlist", "detail_view", "detail_view")):
                self.db.add_interest(listing, shopper, kind, hours_ago=2)

    def test_api_shape_and_sold_out_hidden(self):
        sold_out = self.listings[0]
        self.db.execute("UPDATE listings SET status = 'SOLD_OUT' WHERE id = %s;", (sold_out,))
        client = create_app().test_client()
        with client.session_transaction() as sess:
            sess["user"] = "shopper"
        data = client.get("/api/hot").get_json()
        self.assertEqual(set(data), {"hot", "rising"})
        self.assertEqual(sorted(c["id"] for c in data["hot"]), sorted(self.listings[1:]))


if __name__ == "__main__":
    unittest.main()
