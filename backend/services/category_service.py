# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
services/category_service.py

Purpose:
Rules for product categories.

Rules enforced:
- A listing can only use a subcategory (or "Other"), never a main category
- A main category page shows the listings from all of its subcategories
- Bad page/sort values fall back to defaults instead of erroring
"""

import math

from config.product_categories import PRODUCT_CATEGORIES
from models.category_model import (
    get_category_tree,
    get_category_by_slug,
    get_category_by_id,
    get_child_categories,
    get_visible_listing_counts,
)
from models.listing_model import browse_public_listings, BROWSE_SORTS


MSG_CHOOSE_CATEGORY = "Please choose a category."
MSG_CHOOSE_SUBCATEGORY = "Choose a specific subcategory, not a main category."
MSG_CATEGORY_MISSING = "That category doesn't exist."
MSG_CATEGORY_NOT_FOUND = "Category not found."

DEFAULT_SORT = "newest"
DEFAULT_PER_PAGE = 24
MAX_PER_PAGE = 48
MAX_PAGE = 100000          # stops huge ?page= values
MAX_POSTGRES_INTEGER = 2147483647


class CategoryRedirect(Exception):
    """Used when /categories/<subcategory> should redirect to /categories/<parent>/<subcategory>."""

    def __init__(self, parent_slug, sub_slug):
        super().__init__(f"Category moved to /categories/{parent_slug}/{sub_slug}")
        self.parent_slug = parent_slug
        self.sub_slug = sub_slug


# ________________________________________________________
# TREE
# ________________________________________________________

def _config_keywords():
    """Search words for the seller's picker, from config."""
    keywords = {}
    for parent in PRODUCT_CATEGORIES:
        keywords[parent["slug"]] = list(parent.get("keywords", []))
        for child in parent.get("children", []):
            keywords[child["slug"]] = list(child.get("keywords", []))
    return keywords


def _public_node(node, keywords):
    children = [_public_node(child, keywords) for child in node.get("children", [])]
    return {
        "id": node["id"],
        "slug": node["slug"],
        "name": node["name"],
        "description": node.get("description"),
        "icon": node.get("icon"),
        "is_selectable": len(children) == 0,
        "keywords": keywords.get(node["slug"], []),
        "children": children,
    }


def get_category_tree_service():
    """Returns all active categories in display order."""
    keywords = _config_keywords()
    return [_public_node(node, keywords) for node in get_category_tree(active_only=True)]


# ________________________________________________________
# ASSIGNMENT VALIDATION
# ________________________________________________________

def _parse_category_id(raw_value):
    """Turns the submitted value into a category id, or raises an error message for the seller."""
    if raw_value is None:
        raise Exception(MSG_CHOOSE_CATEGORY)

    if isinstance(raw_value, str):
        value = raw_value.strip()
        if value == "":
            raise Exception(MSG_CHOOSE_CATEGORY)
        if not value.isdigit() or not value.isascii():
            raise Exception(MSG_CATEGORY_MISSING)
        category_id = int(value)
    elif isinstance(raw_value, bool) or not isinstance(raw_value, int):
        # True/False count as ints in Python, so reject them here
        raise Exception(MSG_CATEGORY_MISSING)
    else:
        category_id = raw_value

    if category_id <= 0 or category_id > MAX_POSTGRES_INTEGER:
        raise Exception(MSG_CATEGORY_MISSING)
    return category_id


def resolve_assignable_category(raw_value):
    """
    Checks the category a seller picked. It must be an active subcategory (or "Other").
    Returns the category, or raises the error message to show the seller.
    """
    category_id = _parse_category_id(raw_value)

    category = get_category_by_id(category_id)
    if category is None or not category.get("is_active"):
        raise Exception(MSG_CATEGORY_MISSING)

    if category.get("child_count", 0) > 0:
        raise Exception(MSG_CHOOSE_SUBCATEGORY)

    return category


def is_same_category_id(raw_value, current_category_id):
    """True if the submitted category is the one the listing already has."""
    if current_category_id is None:
        return False
    try:
        return _parse_category_id(raw_value) == int(current_category_id)
    except Exception:
        return False


# ________________________________________________________
# BROWSE
# ________________________________________________________

def _clamp_int(raw_value, default, minimum, maximum):
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _normalize_browse_params(sort, page, per_page):
    sort = sort if sort in BROWSE_SORTS else DEFAULT_SORT
    page = _clamp_int(page, 1, 1, MAX_PAGE)
    per_page = _clamp_int(per_page, DEFAULT_PER_PAGE, 1, MAX_PER_PAGE)
    return sort, page, per_page


def _active_category_or_none(slug):
    category = get_category_by_slug(slug)
    if category is None or not category.get("is_active"):
        return None
    return category


def _browse_ids_for(category):
    """A main category includes all of its subcategories."""
    if category["parent_id"] is None:
        child_ids = [child["id"] for child in get_child_categories(category["id"])]
        return [category["id"]] + child_ids
    return [category["id"]]


def _public_category(category):
    return {
        "id": category["id"],
        "slug": category["slug"],
        "name": category["name"],
        "description": category.get("description"),
        "icon": category.get("icon"),
        "parent_id": category["parent_id"],
        "parent_slug": category.get("parent_slug"),
        "parent_name": category.get("parent_name"),
    }


def browse_category_listings_service(slug, sort=None, page=None, per_page=None):
    """Returns the listings for one page of a category."""
    category = _active_category_or_none(slug)
    if category is None:
        raise Exception(MSG_CATEGORY_NOT_FOUND)

    sort, page, per_page = _normalize_browse_params(sort, page, per_page)

    listings, total = browse_public_listings(
        category_ids=_browse_ids_for(category),
        sort=sort,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    return {
        "category": _public_category(category),
        "listings": listings,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    }


# ________________________________________________________
# CATEGORY PAGES (server-rendered shell)
# ________________________________________________________

def get_category_page_service(parent_slug, sub_slug=None):
    """Gets what the category page needs: the category, its subcategories, and item counts."""
    parent = _active_category_or_none(parent_slug)
    if parent is None:
        raise Exception(MSG_CATEGORY_NOT_FOUND)

    if parent["parent_id"] is not None:
        if sub_slug is None:
            raise CategoryRedirect(parent["parent_slug"], parent["slug"])
        raise Exception(MSG_CATEGORY_NOT_FOUND)

    active_sub = None
    if sub_slug is not None:
        active_sub = _active_category_or_none(sub_slug)
        if active_sub is None or active_sub["parent_id"] != parent["id"]:
            raise Exception(MSG_CATEGORY_NOT_FOUND)

    children = get_child_categories(parent["id"])
    counts = get_visible_listing_counts([parent["id"]] + [child["id"] for child in children])

    subcategories = []
    for child in children:
        count = counts.get(child["id"], 0)
        is_active_chip = active_sub is not None and child["id"] == active_sub["id"]
        if count > 0 or is_active_chip:
            subcategories.append({
                "id": child["id"],
                "slug": child["slug"],
                "name": child["name"],
                "count": count,
                "is_active": is_active_chip,
            })

    parent_total = sum(counts.values())
    current_total = counts.get(active_sub["id"], 0) if active_sub else parent_total

    return {
        "parent": _public_category(parent),
        "active_sub": _public_category(active_sub) if active_sub else None,
        "current": _public_category(active_sub or parent),
        "subcategories": subcategories,
        "has_children": len(children) > 0,
        "parent_total": parent_total,
        "current_total": current_total,
    }
