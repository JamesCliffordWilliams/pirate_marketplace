# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - category list tests (no database needed)

import os
import re
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from config.product_categories import PRODUCT_CATEGORIES, OTHER_SLUG
from migrations.add_product_categories import validate_taxonomy

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def author_slug(name):
    """The authoring rule from the spec: lowercase, & -> and, commas dropped, other non-alphanumerics -> -."""
    value = name.lower().replace("&", "and").replace(",", "")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


class TestProductCategoryTaxonomy(unittest.TestCase):

    def test_twelve_parents(self):
        self.assertEqual(len(PRODUCT_CATEGORIES), 12)

    def test_slugs_unique_and_valid(self):
        slugs = []
        for parent in PRODUCT_CATEGORIES:
            slugs.append(parent["slug"])
            slugs.extend(child["slug"] for child in parent.get("children", []))

        self.assertEqual(len(slugs), len(set(slugs)), "duplicate slugs")
        for slug in slugs:
            self.assertRegex(slug, SLUG_PATTERN)
            self.assertLessEqual(len(slug), 80)

    def test_slugs_follow_authoring_rule(self):
        for parent in PRODUCT_CATEGORIES:
            self.assertEqual(parent["slug"], author_slug(parent["name"]), parent["name"])
            for child in parent.get("children", []):
                self.assertEqual(child["slug"], author_slug(child["name"]), child["name"])

    def test_every_parent_except_other_has_children(self):
        for parent in PRODUCT_CATEGORIES:
            if parent["slug"] == OTHER_SLUG:
                self.assertEqual(parent.get("children", []), [])
            else:
                self.assertGreaterEqual(len(parent.get("children", [])), 1, parent["name"])

    def test_no_grandchildren(self):
        for parent in PRODUCT_CATEGORIES:
            for child in parent.get("children", []):
                self.assertFalse(child.get("children"), f"{child['name']} has children")

    def test_other_is_last(self):
        self.assertEqual(PRODUCT_CATEGORIES[-1]["slug"], OTHER_SLUG)
        self.assertEqual(PRODUCT_CATEGORIES[-1]["name"], "Other")

    def test_other_leaves_are_last_in_parent(self):
        for parent in PRODUCT_CATEGORIES:
            children = parent.get("children", [])
            if not children:
                continue
            other_positions = [i for i, c in enumerate(children) if c["name"].startswith("Other ")]
            self.assertEqual(other_positions, [len(children) - 1], parent["name"])

    def test_parents_have_icons_and_children_do_not(self):
        for parent in PRODUCT_CATEGORIES:
            self.assertTrue(parent.get("icon"), parent["name"])
            for child in parent.get("children", []):
                self.assertFalse(child.get("icon"), child["name"])

    def test_keywords_are_lowercase_string_lists(self):
        for parent in PRODUCT_CATEGORIES:
            for node in [parent] + parent.get("children", []):
                keywords = node.get("keywords", [])
                self.assertIsInstance(keywords, list, node["slug"])
                for keyword in keywords:
                    self.assertIsInstance(keyword, str)
                    self.assertEqual(keyword, keyword.strip().lower(), node["slug"])

    def test_laptops_findable_by_mac(self):
        electronics = next(p for p in PRODUCT_CATEGORIES if p["slug"] == "electronics-and-technology")
        laptops = next(c for c in electronics["children"] if c["slug"] == "laptops-and-computers")
        self.assertIn("mac", laptops["keywords"])

    def test_names_fit_column(self):
        for parent in PRODUCT_CATEGORIES:
            self.assertLessEqual(len(parent["name"]), 80)
            for child in parent.get("children", []):
                self.assertLessEqual(len(child["name"]), 80)

    def test_expected_counts_per_parent(self):
        expected = {
            "clothing-and-apparel": 12,
            "shoes-and-footwear": 7,
            "electronics-and-technology": 10,
            "home-and-dorm-essentials": 10,
            "books-and-school-supplies": 8,
            "accessories-and-jewelry": 11,
            "gaming-and-entertainment": 7,
            "sports-and-fitness": 5,
            "art-crafts-and-handmade": 5,
            "beauty-and-personal-care": 9,
            "collectibles-and-memorabilia": 7,
            "other": 0,
        }
        actual = {p["slug"]: len(p.get("children", [])) for p in PRODUCT_CATEGORIES}
        self.assertEqual(actual, expected)

    def test_spec_descriptions_present(self):
        by_slug = {p["slug"]: p for p in PRODUCT_CATEGORIES}
        self.assertIn("Handmade clothing and jewelry", by_slug["art-crafts-and-handmade"]["description"])
        hampton = next(
            c for c in by_slug["collectibles-and-memorabilia"]["children"]
            if c["slug"] == "hampton-university-merchandise"
        )
        self.assertEqual(hampton["description"], "Any Hampton-branded item, including apparel.")

    def test_validate_taxonomy_accepts_config(self):
        validate_taxonomy(PRODUCT_CATEGORIES)

    def test_validate_taxonomy_rejects_duplicates(self):
        bad = [
            {"slug": "a", "name": "A", "icon": "box", "children": [{"slug": "dup", "name": "Dup"}]},
            {"slug": "b", "name": "B", "icon": "box", "children": [{"slug": "dup", "name": "Dup 2"}]},
            {"slug": "other", "name": "Other", "icon": "box", "children": []},
        ]
        with self.assertRaises(ValueError):
            validate_taxonomy(bad)

    def test_validate_taxonomy_rejects_grandchildren(self):
        bad = [
            {"slug": "a", "name": "A", "icon": "box", "children": [
                {"slug": "a1", "name": "A1", "children": [{"slug": "a1x", "name": "A1x"}]},
            ]},
            {"slug": "other", "name": "Other", "icon": "box", "children": []},
        ]
        with self.assertRaises(ValueError):
            validate_taxonomy(bad)

    def test_validate_taxonomy_rejects_other_with_children(self):
        bad = [
            {"slug": "other", "name": "Other", "icon": "box", "children": [{"slug": "x", "name": "X"}]},
        ]
        with self.assertRaises(ValueError):
            validate_taxonomy(bad)

    def test_validate_taxonomy_rejects_bad_slug(self):
        bad = [
            {"slug": "Bad Slug", "name": "Bad", "icon": "box", "children": [{"slug": "ok", "name": "Ok"}]},
            {"slug": "other", "name": "Other", "icon": "box", "children": []},
        ]
        with self.assertRaises(ValueError):
            validate_taxonomy(bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
