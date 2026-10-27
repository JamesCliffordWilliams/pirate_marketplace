# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - category page tests
#
# TestCategoryPagesOffline renders the real templates with the category data
# mocked (no database). TestCategoryPagesOnDatabase repeats the key checks
# against a LOCAL migrated database (skipped otherwise).

import os
import re
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from tests.db_test_guard import require_local_db
from app import create_app
from config.product_categories import PRODUCT_CATEGORIES
from services import category_service


def build_fake_db():
    """Turns the config taxonomy into the rows the category model would return."""
    tree, by_slug, children_of = [], {}, {}
    next_id = 1
    for p_index, parent in enumerate(PRODUCT_CATEGORIES, start=1):
        parent_id = next_id
        next_id += 1
        parent_node = {"id": parent_id, "slug": parent["slug"], "name": parent["name"], "parent_id": None,
                       "description": parent.get("description"), "icon": parent["icon"],
                       "sort_order": p_index, "is_active": True, "children": []}
        by_slug[parent["slug"]] = {**{k: v for k, v in parent_node.items() if k != "children"},
                                   "parent_slug": None, "parent_name": None,
                                   "child_count": len(parent.get("children", []))}
        children_of[parent_id] = []
        for c_index, child in enumerate(parent.get("children", []), start=1):
            child_node = {"id": next_id, "slug": child["slug"], "name": child["name"], "parent_id": parent_id,
                          "description": child.get("description"), "icon": None,
                          "sort_order": c_index, "is_active": True, "children": []}
            next_id += 1
            parent_node["children"].append(child_node)
            row = {**{k: v for k, v in child_node.items() if k != "children"},
                   "parent_slug": parent["slug"], "parent_name": parent["name"], "child_count": 0}
            by_slug[child["slug"]] = row
            children_of[parent_id].append(row)
        tree.append(parent_node)
    return tree, by_slug, children_of


class TestCategoryPagesOffline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()
        cls.tree, cls.by_slug, cls.children_of = build_fake_db()

    def setUp(self):
        self.counts = {}
        for name, kwargs in (
            ("get_category_tree", {"return_value": self.tree}),
            ("get_category_by_slug", {"side_effect": self.by_slug.get}),
            ("get_child_categories", {"side_effect": lambda pid: self.children_of.get(pid, [])}),
            ("get_visible_listing_counts", {"side_effect": lambda ids: {i: self.counts.get(i, 0) for i in ids}}),
        ):
            p = patch.object(category_service, name, **kwargs)
            p.start()
            self.addCleanup(p.stop)

    def test_grid_page_lists_all_twelve(self):
        response = self.client.get("/categories")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for parent in PRODUCT_CATEGORIES:
            self.assertIn(parent["name"].replace("&", "&amp;"), html)
            self.assertIn(f'href="/categories/{parent["slug"]}"', html)
        self.assertEqual(html.count('class="cat-card"'), 12)
        self.assertIn("Laptops &amp; Computers, Phones, Tablets &amp; eReaders…", html)
        self.assertIn("Everything else.", html)
        self.assertIn('href="/categories"', html)  # nav link from the shared partial

    def test_parent_page(self):
        laptops = self.by_slug["laptops-and-computers"]["id"]
        self.counts = {laptops: 3}
        response = self.client.get("/categories/electronics-and-technology")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-slug="electronics-and-technology"', html)
        self.assertIn("All Electronics &amp; Technology", html)
        # only leaves with visible items get chips
        self.assertIn('/categories/electronics-and-technology/laptops-and-computers"', html)
        self.assertNotIn('/categories/electronics-and-technology/phones"', html)
        self.assertIn("3 items", html)
        self.assertIn('data-show-category="true"', html)

    def test_valid_sub_page_keeps_empty_active_chip(self):
        response = self.client.get("/categories/electronics-and-technology/phones?sort=price_asc")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-slug="phones"', html)
        self.assertRegex(html, r'class="cat-chip is-active"\s+href="/categories/electronics-and-technology/phones\?sort=price_asc"')
        self.assertIn('<option value="price_asc" selected>', html)
        self.assertIn("0 items", html)
        self.assertIn('data-is-sub="true"', html)

    def test_other_page_has_no_chips(self):
        response = self.client.get("/categories/other")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('class="cat-chips"', response.get_data(as_text=True))

    def test_mismatched_sub_404(self):
        response = self.client.get("/categories/shoes-and-footwear/phones")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Category not found", response.get_data(as_text=True))

    def test_unknown_404(self):
        for path in ("/categories/nope", "/categories/nope/phones", "/categories/BAD_slug",
                     "/categories/electronics-and-technology/nope"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertIn("Category not found", response.get_data(as_text=True))

    def test_leaf_as_parent_redirects_301(self):
        response = self.client.get("/categories/laptops-and-computers?sort=price_desc")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.headers["Location"].endswith(
            "/categories/electronics-and-technology/laptops-and-computers?sort=price_desc"))

    def test_leaf_with_sub_is_404(self):
        response = self.client.get("/categories/laptops-and-computers/phones")
        self.assertEqual(response.status_code, 404)

    def test_bad_sort_param_defaults(self):
        response = self.client.get("/categories/other?sort=<script>")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('<option value="newest" selected>', html)
        self.assertNotIn("<script>", html.split("<body>")[1].split("<script src")[0])

    def test_homepage_links_all_categories(self):
        response = self.client.get("/storefronts")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        # Updated by James Williams 10/26/26 - new header: links only to pages that exist
        self.assertIn('href="/categories">All categories</a>', html)
        self.assertIn('href="/hot"', html)
        for dead in ("Explore Brands", "New Drops", "Sitemap"):
            self.assertNotIn(dead, html)
        self.assertIn("js/nav_pane.js", html)
        self.assertIn("js/storefront.js", html)

    def test_category_pages_include_shared_nav(self):
        for path in ("/categories", "/categories/other"):
            with self.subTest(path=path):
                html = self.client.get(path).get_data(as_text=True)
                self.assertIn('id="navPane"', html)
                self.assertIn("menu-btn", html)  # Updated by James Williams 10/26/26 - new header
                self.assertIn("css/nav.css", html)
                self.assertIn("js/nav_pane.js", html)
                self.assertIn("css/storefront.css", html)
                self.assertIn("css/categories.css", html)

    def test_storefront_view_includes_shared_card(self):
        html = self.client.get("/storefronts/1").get_data(as_text=True)
        self.assertLess(html.index("js/listing_card.js"), html.index("js/storefront_view.js"))
        self.assertIn("css/listing_card.css", html)

    def test_listing_forms_include_picker(self):
        for path in ("/create-listing",):
            with self.subTest(path=path):
                html = self.client.get(path).get_data(as_text=True)
                self.assertIn('id="categoryPicker"', html)
                self.assertIn('name="category_id"', html)
                self.assertLess(html.index("js/category_picker.js"), html.index("js/create_listing.js"))
                # placed after Listing Name and before Available Sizes
                self.assertLess(html.index('id="listingName"'), html.index('id="categoryPicker"'))
                self.assertLess(html.index('id="categoryPicker"'), html.index("Available Sizes"))


@require_local_db
class TestCategoryPagesOnDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_pages(self):
        self.assertEqual(self.client.get("/categories").status_code, 200)
        html = self.client.get("/categories").get_data(as_text=True)
        for parent in PRODUCT_CATEGORIES:
            self.assertIn(parent["name"].replace("&", "&amp;"), html)
        self.assertEqual(self.client.get("/categories/electronics-and-technology").status_code, 200)
        self.assertEqual(self.client.get("/categories/electronics-and-technology/phones").status_code, 200)
        self.assertEqual(self.client.get("/categories/shoes-and-footwear/phones").status_code, 404)
        self.assertEqual(self.client.get("/categories/nope").status_code, 404)
        self.assertEqual(self.client.get("/categories/laptops-and-computers").status_code, 301)


if __name__ == "__main__":
    unittest.main(verbosity=2)
