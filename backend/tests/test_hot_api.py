# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - Hot service, cache, API and page
#
# TestHotServiceOffline / TestHotApiOffline: model layer mocked (no database).
# TestHotOnDatabase: throwaway schema on a LOCAL database (skipped otherwise, see db_test_guard.py).

import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema
from app import create_app
from config import hot_ranking as cfg
from services import hot_service


def ev(listing_id, storefront_id, user_id, kind="wishlist", age=1.0):
    return {"listing_id": listing_id, "storefront_id": storefront_id, "user_id": user_id,
            "kind": kind, "age_hours": age}


def hot_events(listing_id, storefront_id, engagers=3, first_user=None):
    base = first_user or listing_id * 100
    return [ev(listing_id, storefront_id, base + i, "wishlist" if i == 0 else "detail_view")
            for i in range(engagers)]


def card(listing_id, storefront_id=1):
    return {"id": listing_id, "storefront_id": storefront_id, "title": f"L{listing_id}"}


class FakeModels:
    """Stands in for the database calls hot_service makes."""

    def __init__(self, events, cards):
        self.events = events
        self.cards = {c["id"]: c for c in cards}
        self.event_calls = 0
        self.browse_calls = []

    def get_engagement_events(self, window_hours, *args, **kwargs):
        self.event_calls += 1
        return list(self.events)

    def get_storefront_reach(self, storefront_ids, days, *args, **kwargs):
        return {}

    def browse_public_listings(self, listing_ids=None, available_only=False, limit=24, **kwargs):
        self.browse_calls.append((list(listing_ids), available_only))
        found = [self.cards[i] for i in sorted(listing_ids) if i in self.cards]   # not in ranked order
        return found, len(found)

    def patch(self, test):
        for name in ("get_engagement_events", "get_storefront_reach", "browse_public_listings"):
            p = patch.object(hot_service, name, side_effect=getattr(self, name))
            p.start()
            test.addCleanup(p.stop)


class TestHotServiceOffline(unittest.TestCase):

    def setUp(self):
        hot_service.clear_ranking_cache()
        self.addCleanup(hot_service.clear_ranking_cache)

    def ids(self, data):
        return {key: [c["id"] for c in value] for key, value in data.items()}

    def test_cached_ids_card_data_reread(self):
        events = hot_events(1, 1, engagers=4) + hot_events(2, 2) + hot_events(3, 3) + hot_events(4, 4)
        fake = FakeModels(events, [card(i, i) for i in (1, 2, 3, 4)])
        fake.patch(self)

        first = self.ids(hot_service.get_hot_page_data())
        self.assertEqual(first["hot"], [1, 4, 3, 2])

        # listing 1 sells out: still in the cached ranking, gone from the fresh read
        del fake.cards[1]
        second = self.ids(hot_service.get_hot_page_data())
        self.assertEqual(fake.event_calls, 1)
        self.assertEqual(second["hot"], [4, 3, 2])
        self.assertTrue(all(available for _, available in fake.browse_calls))

    def test_cache_expires(self):
        fake = FakeModels(hot_events(1, 1), [card(1)])
        fake.patch(self)
        clock = [1000.0]
        with patch.object(hot_service.time, "monotonic", side_effect=lambda: clock[0]):
            hot_service.get_hot_page_data()
            clock[0] += cfg.CACHE_SECONDS - 1
            hot_service.get_hot_page_data()
            self.assertEqual(fake.event_calls, 1)
            clock[0] += 2
            hot_service.get_hot_page_data()
            self.assertEqual(fake.event_calls, 2)

    def test_failed_ranking_is_not_cached_and_shows_nothing_stale(self):
        fake = FakeModels(hot_events(1, 1), [card(1)])
        fake.patch(self)
        with patch.object(hot_service, "get_engagement_events", side_effect=RuntimeError("db down")):
            with self.assertRaises(RuntimeError):
                hot_service.get_hot_page_data()
        self.assertEqual(self.ids(hot_service.get_hot_page_data())["hot"], [1])

    def test_card_read_failure_raises_instead_of_serving_cached_cards(self):
        fake = FakeModels(hot_events(1, 1), [card(1)])
        fake.patch(self)
        hot_service.get_hot_page_data()
        with patch.object(hot_service, "browse_public_listings", side_effect=RuntimeError("db down")):
            with self.assertRaises(RuntimeError):
                hot_service.get_hot_page_data()

    def test_cached_value_cannot_be_changed_by_callers(self):
        fake = FakeModels(hot_events(1, 1), [card(1)])
        fake.patch(self)
        hot_service.get_hot_page_data()
        cached = hot_service._ranking_cache.peek()
        with self.assertRaises((TypeError, AttributeError)):
            cached["hot"].append({"listing_id": 99})

    def test_ranked_order_preserved(self):
        events = hot_events(5, 5, engagers=3) + hot_events(9, 9, engagers=6) + hot_events(7, 7, engagers=4)
        fake = FakeModels(events, [card(5, 5), card(7, 7), card(9, 9)])
        fake.patch(self)
        self.assertEqual(self.ids(hot_service.get_hot_page_data())["hot"], [9, 7, 5])

    def test_nothing_anywhere(self):
        fake = FakeModels([], [])
        fake.patch(self)
        self.assertEqual(self.ids(hot_service.get_hot_page_data()), {"hot": [], "rising": []})

    def test_fork_gets_a_fresh_cache(self):
        fake = FakeModels(hot_events(1, 1), [card(1)])
        fake.patch(self)
        hot_service.get_hot_page_data()
        self.assertIsNotNone(hot_service._ranking_cache.peek())
        hot_service._ranking_cache.reset_after_fork()
        self.assertIsNone(hot_service._ranking_cache.peek())


class TestHotApiOffline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()
        with cls.client.session_transaction() as sess:
            sess["user"] = "shopper"  # Added by James Williams 10/27/26 - pages need a login

    def setUp(self):
        hot_service.clear_ranking_cache()
        self.addCleanup(hot_service.clear_ranking_cache)

    def test_shape_and_cache_header(self):
        FakeModels(hot_events(1, 1), [card(1)]).patch(self)
        response = self.client.get("/api/hot")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "public, max-age=60")
        data = response.get_json()
        self.assertEqual(set(data), {"hot", "rising"})
        self.assertEqual(data["hot"], [card(1)])

    def test_errors_are_json_500(self):
        secret = 'could not connect to server "db.internal.example" port 5432'
        with patch.object(hot_service, "get_engagement_events", side_effect=RuntimeError(secret)):
            with self.assertLogs(self.app.logger, level="ERROR") as logs:
                response = self.client.get("/api/hot")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "Couldn't load the Hot page. Please try again."})
        self.assertNotIn("db.internal.example", response.get_data(as_text=True))
        self.assertIsNone(response.headers.get("Cache-Control"))
        # the real error is kept in the server log
        self.assertIn("db.internal.example", "\n".join(logs.output))

    def test_page_renders(self):
        response = self.client.get("/hot")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('<h1 class="cat-title">Hot</h1>', html)
        self.assertIn("How this works", html)
        self.assertIn("Hot Right Now", html)
        self.assertIn("What shoppers are saving, carting, and buying over the last two weeks.", html)
        self.assertNotIn("this week", html)
        self.assertIn("Picking up momentum, with a boost for smaller storefronts.", html)
        self.assertNotIn("Just Listed", html)
        for asset in ("css/storefront.css", "css/listing_card.css", "css/categories.css", "css/hot.css",
                      "js/nav_pane.js", "js/listing_card.js", "js/hot.js"):
            self.assertIn(asset, html)

    def test_every_nav_link_reaches_a_route(self):
        # Updated by James Williams 10/26/26 - new header, drawer and footer link only to real pages
        import re
        from controllers import category_controller
        with patch.object(category_controller, "get_category_tree_service", return_value=[]):
            pages = {path: self.client.get(path).get_data(as_text=True)
                     for path in ("/hot", "/categories", "/storefronts")}
        adapter = self.app.url_map.bind("localhost")
        for path, html in pages.items():
            shell = html[html.index('<header class="pm pm-header">'):html.index('<span id="main"')]
            shell += html[html.index('<footer class="pm pm-footer">'):]
            links = set(re.findall(r'href="(/[^"#?]*)"', shell))
            # the old menu's items, Home first (Updated by James Williams 10/26/26)
            for href in ("/storefronts", "/storefronts/create", "/listings/create", "/my-storefront",
                         "/categories", "/hot", "/returns"):
                self.assertIn(href, links, path)
            self.assertFalse(any(link.startswith("/categories/") for link in links), path)
            for link in links:
                with self.subTest(page=path, link=link):
                    adapter.match(link, method="GET")  # raises NotFound for a dead link
            for dead in ("Explore Brands", "New Drops", "Sitemap"):
                self.assertNotIn(dead, html)


@require_local_db
class TestHotOnDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        hot_service.clear_ranking_cache()
        self.addCleanup(hot_service.clear_ranking_cache)
        self.db = ThrowawaySchema().create()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["user"] = "shopper"  # Added by James Williams 10/27/26 - pages need a login
        self.shoppers = [self.db.add_user(age_hours=500) for _ in range(4)]
        self.stores = [self.db.add_storefront(name=f"Store {i}") for i in range(4)]
        self.listings = [self.db.add_listing(store, f"Hot {i}") for i, store in enumerate(self.stores)]
        for listing in self.listings:
            self.db.add_interest(listing, self.shoppers[0], "wishlist", hours_ago=2)
            self.db.add_interest(listing, self.shoppers[1], "detail_view", hours_ago=2)
            self.db.add_interest(listing, self.shoppers[2], "detail_view", hours_ago=2)

    def tearDown(self):
        self.db.drop()

    def api(self):
        response = self.client.get("/api/hot")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def test_card_shape_matches_category_api(self):
        from models.listing_model import browse_public_listings
        expected_keys = set(browse_public_listings(listing_ids=[self.listings[0]])[0][0])
        data = self.api()
        self.assertEqual(sorted(c["id"] for c in data["hot"]), sorted(self.listings))
        self.assertEqual(set(data["hot"][0]), expected_keys)

    def test_unavailable_listings_never_appear_even_from_cache(self):
        self.assertEqual(len(self.api()["hot"]), 4)     # warms the cache
        sold_out, deleted, inactive, closed_store_listing = self.listings
        self.db.execute("UPDATE listings SET status = 'SOLD_OUT' WHERE id = %s;", (sold_out,))
        self.db.execute("UPDATE listings SET status = 'DELETED' WHERE id = %s;", (deleted,))
        self.db.execute("UPDATE listings SET status = 'INACTIVE' WHERE id = %s;", (inactive,))
        self.db.execute("UPDATE storefronts SET is_active = FALSE WHERE id = %s;", (self.stores[3],))
        self.assertIsNotNone(hot_service._ranking_cache.peek())
        data = self.api()
        shown = [c["id"] for section in data.values() for c in section]
        for listing in self.listings:
            self.assertNotIn(listing, shown)

    def test_out_of_stock_dropped_from_cache(self):
        self.api()
        self.db.execute("UPDATE listings SET quantity_on_hand = 0 WHERE id = %s;", (self.listings[0],))
        self.assertNotIn(self.listings[0], [c["id"] for c in self.api()["hot"]])

    def test_missing_table_falls_back(self):
        self.db.execute("DROP TABLE listing_interest;")
        data = self.api()
        self.assertEqual(data, {"hot": [], "rising": []})

    def test_page_renders(self):
        self.assertEqual(self.client.get("/hot").status_code, 200)

    def test_independent_processes(self):
        """Each app process has its own cache, and none of them can show a listing that became unavailable."""
        script = (
            "import json, sys\n"
            f"sys.path[:0] = [{PROJECT_ROOT!r}, {BACKEND_ROOT!r}]\n"
            "from services import hot_service\n"
            "def ids():\n"
            "    return [c['id'] for c in hot_service.get_hot_page_data()['hot']]\n"
            "print(json.dumps(ids()), flush=True)\n"
            "sys.stdin.readline()\n"
            "# the ranking must come from this process's cache now\n"
            "hot_service.get_engagement_events = None\n"
            "print(json.dumps(ids()), flush=True)\n"
        )
        procs = [subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  env=dict(os.environ))
                 for _ in range(2)]
        try:
            for proc in procs:
                first = json.loads(proc.stdout.readline())
                self.assertEqual(sorted(first), sorted(self.listings))

            self.db.execute("UPDATE listings SET status = 'SOLD_OUT' WHERE id = %s;", (self.listings[0],))

            for proc in procs:
                out, err = proc.communicate("go\n", timeout=30)
                self.assertEqual(proc.returncode, 0, err)
                second = json.loads(out.strip().splitlines()[-1])
                self.assertEqual(sorted(second), sorted(self.listings[1:]))
        finally:
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()


if __name__ == "__main__":
    unittest.main()
