# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - category rules tests
#
# These tests mock the model layer, so they run without a database.

import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from services import category_service, listing_service
from services.category_service import (
    resolve_assignable_category,
    browse_category_listings_service,
    get_category_tree_service,
    MSG_CHOOSE_CATEGORY,
    MSG_CHOOSE_SUBCATEGORY,
    MSG_CATEGORY_MISSING,
)

# id -> category row as returned by models.category_model.get_category_by_id
CATEGORIES = {
    1: {"id": 1, "slug": "electronics-and-technology", "name": "Electronics & Technology", "parent_id": None,
        "is_active": True, "child_count": 2, "description": None, "icon": "laptop",
        "parent_slug": None, "parent_name": None},
    2: {"id": 2, "slug": "laptops-and-computers", "name": "Laptops & Computers", "parent_id": 1,
        "is_active": True, "child_count": 0, "description": None, "icon": None,
        "parent_slug": "electronics-and-technology", "parent_name": "Electronics & Technology"},
    3: {"id": 3, "slug": "phones", "name": "Phones", "parent_id": 1,
        "is_active": True, "child_count": 0, "description": None, "icon": None,
        "parent_slug": "electronics-and-technology", "parent_name": "Electronics & Technology"},
    4: {"id": 4, "slug": "retired-leaf", "name": "Retired Leaf", "parent_id": 1,
        "is_active": False, "child_count": 0, "description": None, "icon": None,
        "parent_slug": "electronics-and-technology", "parent_name": "Electronics & Technology"},
    9: {"id": 9, "slug": "other", "name": "Other", "parent_id": None,
        "is_active": True, "child_count": 0, "description": None, "icon": "box",
        "parent_slug": None, "parent_name": None},
}
BY_SLUG = {c["slug"]: c for c in CATEGORIES.values()}


def fake_get_category_by_id(category_id):
    return CATEGORIES.get(category_id)


def fake_get_category_by_slug(slug):
    return BY_SLUG.get(slug)


class TestResolveAssignableCategory(unittest.TestCase):

    def setUp(self):
        patcher = patch.object(category_service, "get_category_by_id", side_effect=fake_get_category_by_id)
        self.lookup = patcher.start()
        self.addCleanup(patcher.stop)

    def assertRejected(self, raw, message):
        with self.assertRaises(Exception) as ctx:
            resolve_assignable_category(raw)
        self.assertEqual(str(ctx.exception), message)

    def test_valid_leaf_int(self):
        self.assertEqual(resolve_assignable_category(2)["id"], 2)

    def test_valid_leaf_digit_string(self):
        self.assertEqual(resolve_assignable_category("3")["id"], 3)
        self.assertEqual(resolve_assignable_category(" 3 ")["id"], 3)

    def test_other_is_assignable(self):
        self.assertEqual(resolve_assignable_category(9)["slug"], "other")

    def test_parent_rejected(self):
        self.assertRejected(1, MSG_CHOOSE_SUBCATEGORY)
        self.assertEqual(MSG_CHOOSE_SUBCATEGORY, "Choose a specific subcategory, not a main category.")

    def test_missing_values_rejected(self):
        self.assertRejected(None, MSG_CHOOSE_CATEGORY)
        self.assertRejected("", MSG_CHOOSE_CATEGORY)
        self.assertRejected("   ", MSG_CHOOSE_CATEGORY)
        self.assertEqual(MSG_CHOOSE_CATEGORY, "Please choose a category.")

    def test_nonexistent_rejected(self):
        self.assertRejected(12345, MSG_CATEGORY_MISSING)
        self.assertEqual(MSG_CATEGORY_MISSING, "That category doesn't exist.")

    def test_inactive_rejected(self):
        self.assertRejected(4, MSG_CATEGORY_MISSING)

    def test_malformed_values_rejected_without_lookup(self):
        for raw in ("3abc", "abc", "-3", "3.0", "+3", 3.0, 2.5, True, False, [2], {"id": 2}, -3, 0, 2 ** 40):
            with self.subTest(raw=raw):
                self.assertRejected(raw, MSG_CATEGORY_MISSING)
        self.lookup.assert_not_called()


class TestBrowseParams(unittest.TestCase):

    def setUp(self):
        for name, fake in (
            ("get_category_by_slug", fake_get_category_by_slug),
        ):
            patcher = patch.object(category_service, name, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)

        patcher = patch.object(category_service, "get_child_categories",
                               side_effect=lambda pid: [CATEGORIES[2], CATEGORIES[3]] if pid == 1 else [])
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch.object(category_service, "browse_public_listings", return_value=([], 0))
        self.browse = patcher.start()
        self.addCleanup(patcher.stop)

    def _kwargs(self):
        return self.browse.call_args.kwargs

    def test_parent_expands_to_children_plus_itself(self):
        browse_category_listings_service("electronics-and-technology", None, None, None)
        self.assertEqual(sorted(self._kwargs()["category_ids"]), [1, 2, 3])

    def test_leaf_maps_to_itself(self):
        browse_category_listings_service("phones", None, None, None)
        self.assertEqual(self._kwargs()["category_ids"], [3])

    def test_unknown_or_inactive_slug_raises_not_found(self):
        for slug in ("nope", "retired-leaf"):
            with self.subTest(slug=slug):
                with self.assertRaises(Exception) as ctx:
                    browse_category_listings_service(slug, None, None, None)
                self.assertIn("not found", str(ctx.exception).lower())

    def test_params_are_clamped_and_defaulted(self):
        cases = [
            ((None, None, None), ("newest", 24, 0)),
            (("price_asc", "2", "10"), ("price_asc", 10, 10)),
            (("price_desc", "1", "1000"), ("price_desc", 48, 0)),
            (("drop table", "abc", "0"), ("newest", 1, 0)),
            (("newest", "-5", "-1"), ("newest", 1, 0)),
            (("newest", "3", "xyz"), ("newest", 24, 48)),
            (("newest", "99999999999999", "24"), ("newest", 24, None)),
        ]
        for (sort, page, per_page), (exp_sort, exp_limit, exp_offset) in cases:
            with self.subTest(sort=sort, page=page, per_page=per_page):
                result = browse_category_listings_service("phones", sort, page, per_page)
                kwargs = self._kwargs()
                self.assertEqual(kwargs["sort"], exp_sort)
                self.assertEqual(kwargs["limit"], exp_limit)
                if exp_offset is not None:
                    self.assertEqual(kwargs["offset"], exp_offset)
                self.assertGreaterEqual(result["pagination"]["page"], 1)

    def test_pagination_totals(self):
        self.browse.return_value = ([], 50)
        result = browse_category_listings_service("phones", "newest", "9", "24")
        self.assertEqual(result["pagination"], {"page": 9, "per_page": 24, "total": 50, "total_pages": 3})
        self.assertEqual(result["listings"], [])

    def test_category_payload(self):
        result = browse_category_listings_service("phones", None, None, None)
        self.assertEqual(result["category"]["slug"], "phones")
        self.assertEqual(result["category"]["parent_slug"], "electronics-and-technology")


class TestCategoryTree(unittest.TestCase):

    def test_tree_marks_selectable_nodes(self):
        tree = [
            {"id": 1, "slug": "electronics-and-technology", "name": "Electronics & Technology",
             "description": None, "icon": "laptop", "children": [
                 {"id": 2, "slug": "laptops-and-computers", "name": "Laptops & Computers",
                  "description": None, "icon": None, "children": []},
             ]},
            {"id": 9, "slug": "other", "name": "Other", "description": None, "icon": "box", "children": []},
        ]
        with patch.object(category_service, "get_category_tree", return_value=tree):
            result = get_category_tree_service()

        self.assertEqual([n["slug"] for n in result], ["electronics-and-technology", "other"])
        self.assertFalse(result[0]["is_selectable"])
        self.assertTrue(result[0]["children"][0]["is_selectable"])
        self.assertTrue(result[1]["is_selectable"])
        for node in (result[0], result[0]["children"][0], result[1]):
            self.assertEqual(
                set(node), {"id", "slug", "name", "description", "icon", "is_selectable", "keywords", "children"}
            )
        # search keywords come from config, e.g. "mac" -> Laptops & Computers
        self.assertIn("mac", result[0]["children"][0]["keywords"])
        self.assertEqual(result[1]["keywords"], [])


class TestListingServiceCategoryRules(unittest.TestCase):
    """create/update listing services enforce the category rules."""

    OWNER = {"id": 7, "role": "user"}
    STRANGER = {"id": 8, "role": "user"}

    def setUp(self):
        self.listing = {
            "id": 50, "storefront_id": 5, "title": "Mac", "fulfillment_type": "IN_STOCK",
            "quantity_on_hand": 2, "status": "ACTIVE", "is_made_to_order": False, "category_id": 9,
        }
        patches = {
            "get_storefront_by_id": patch.object(listing_service, "get_storefront_by_id",
                                                 return_value={"id": 5, "owner_id": 7, "is_active": True}),
            "get_listing_by_id": patch.object(listing_service, "get_listing_by_id",
                                              side_effect=lambda _id: dict(self.listing)),
            "update_listing": patch.object(listing_service, "update_listing",
                                           side_effect=lambda **kw: {**self.listing, **{k: v for k, v in kw.items() if v is not None}}),
            "create_listing": patch.object(listing_service, "create_listing",
                                           side_effect=lambda **kw: {"id": 99, **kw}),
            "lookup": patch.object(category_service, "get_category_by_id", side_effect=fake_get_category_by_id),
        }
        self.mocks = {}
        for name, p in patches.items():
            self.mocks[name] = p.start()
            self.addCleanup(p.stop)

    def _create(self, **extra):
        data = {"title": "Mac", "price": 100, "fulfillment_type": "IN_STOCK", "quantity_on_hand": 1}
        data.update(extra)
        return listing_service.create_listing_service(self.OWNER, 5, data)

    def test_create_requires_category(self):
        with self.assertRaises(Exception) as ctx:
            self._create()
        self.assertEqual(str(ctx.exception), MSG_CHOOSE_CATEGORY)
        self.mocks["create_listing"].assert_not_called()

    def test_create_rejects_parent(self):
        with self.assertRaises(Exception) as ctx:
            self._create(category_id=1)
        self.assertEqual(str(ctx.exception), MSG_CHOOSE_SUBCATEGORY)
        self.mocks["create_listing"].assert_not_called()

    def test_create_with_leaf_passes_category_id(self):
        created = self._create(category_id="2")
        self.assertEqual(created["category_id"], 2)

    def test_update_without_category_leaves_it_unchanged(self):
        listing_service.update_listing_service(self.OWNER, 50, {"title": "New"})
        self.assertIsNone(self.mocks["update_listing"].call_args.kwargs["category_id"])

    def test_update_with_null_category_rejected(self):
        with self.assertRaises(Exception) as ctx:
            listing_service.update_listing_service(self.OWNER, 50, {"category_id": None})
        self.assertEqual(str(ctx.exception), MSG_CHOOSE_CATEGORY)
        self.mocks["update_listing"].assert_not_called()

    def test_update_with_parent_rejected(self):
        with self.assertRaises(Exception) as ctx:
            listing_service.update_listing_service(self.OWNER, 50, {"category_id": 1})
        self.assertEqual(str(ctx.exception), MSG_CHOOSE_SUBCATEGORY)

    def test_update_with_leaf_changes_category(self):
        listing_service.update_listing_service(self.OWNER, 50, {"category_id": 2})
        self.assertEqual(self.mocks["update_listing"].call_args.kwargs["category_id"], 2)

    def test_update_keeping_inactive_category_still_saves(self):
        self.listing["category_id"] = 4  # category was retired after the listing used it
        listing_service.update_listing_service(self.OWNER, 50, {"category_id": 4, "title": "Still here"})
        self.assertIsNone(self.mocks["update_listing"].call_args.kwargs["category_id"])

    def test_bool_is_never_treated_as_current_category(self):
        self.listing["category_id"] = 1
        with self.assertRaises(Exception) as ctx:
            listing_service.update_listing_service(self.OWNER, 50, {"category_id": True})
        self.assertEqual(str(ctx.exception), MSG_CATEGORY_MISSING)

    def test_non_owner_cannot_change_category(self):
        with self.assertRaises(Exception) as ctx:
            listing_service.update_listing_service(self.STRANGER, 50, {"category_id": 2})
        self.assertIn("Unauthorized", str(ctx.exception))
        self.mocks["update_listing"].assert_not_called()


class TestEditStatusFix(unittest.TestCase):
    """
    The edit page used to always send status=ACTIVE, which silently reactivated
    INACTIVE listings (and would push them into public category browse).
    """

    OWNER = {"id": 7, "role": "user"}

    def setUp(self):
        self.listing = {
            "id": 50, "storefront_id": 5, "title": "Mac", "fulfillment_type": "IN_STOCK",
            "quantity_on_hand": 2, "status": "INACTIVE", "is_made_to_order": False, "category_id": 9,
        }
        for target, kwargs in (
            ("get_storefront_by_id", {"return_value": {"id": 5, "owner_id": 7, "is_active": True}}),
            ("get_listing_by_id", {"side_effect": lambda _id: dict(self.listing)}),
            ("update_listing", {"side_effect": lambda **kw: kw}),
        ):
            p = patch.object(listing_service, target, **kwargs)
            setattr(self, target, p.start())
            self.addCleanup(p.stop)

    def _saved_status(self, data):
        listing_service.update_listing_service(self.OWNER, 50, data)
        return self.update_listing.call_args.kwargs["status"]

    def test_inactive_listing_stays_inactive_when_status_omitted(self):
        self.assertIsNone(self._saved_status({"title": "x", "quantity_on_hand": 3}))

    def test_inactive_listing_stays_inactive_even_if_stale_client_sends_active(self):
        self.assertIsNone(self._saved_status({"title": "x", "quantity_on_hand": 3, "status": "ACTIVE"}))

    def test_deleted_listing_keeps_status(self):
        self.listing["status"] = "DELETED"
        self.assertIsNone(self._saved_status({"quantity_on_hand": 3, "status": "ACTIVE"}))

    def test_active_with_zero_qty_becomes_sold_out(self):
        self.listing["status"] = "ACTIVE"
        self.assertEqual(self._saved_status({"quantity_on_hand": 0}), "SOLD_OUT")

    def test_sold_out_restocked_becomes_active(self):
        self.listing["status"] = "SOLD_OUT"
        self.assertEqual(self._saved_status({"quantity_on_hand": 4}), "ACTIVE")

    def test_made_to_order_with_zero_qty_is_active(self):
        self.listing["status"] = "SOLD_OUT"
        self.assertEqual(self._saved_status({"quantity_on_hand": 0, "is_made_to_order": True}), "ACTIVE")

    def test_explicit_inactive_on_live_listing_still_honored(self):
        self.listing["status"] = "ACTIVE"
        self.assertEqual(self._saved_status({"status": "INACTIVE"}), "INACTIVE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
