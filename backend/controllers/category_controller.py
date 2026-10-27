# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
controllers/category_controller.py

Purpose:
Routes for product categories. Anyone can browse; no login needed.

API:
- GET /api/categories                   -> all categories
- GET /api/categories/<slug>/listings   -> listings in a category

Pages:
- GET /categories                        -> All Categories page
- GET /categories/<parent>               -> listings in a main category
- GET /categories/<parent>/<sub>         -> listings in a subcategory
"""

import re

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session

from services.category_service import (
    get_category_tree_service,
    browse_category_listings_service,
    get_category_page_service,
    CategoryRedirect,
    MSG_CATEGORY_NOT_FOUND,
)

# API blueprint
category_bp = Blueprint("category_bp", __name__, url_prefix="/api/categories")

# Page blueprint
category_pages_bp = Blueprint("category_pages_bp", __name__)

SLUG_RE = re.compile(r"^[a-z0-9-]{1,80}$")


def _valid_slug(slug):
    return bool(slug) and SLUG_RE.match(slug) is not None


#_________________________________________________________
# API Routes
#_________________________________________________________

# GET /api/categories
@category_bp.get("")
def get_categories_route():
    try:
        response = jsonify(get_category_tree_service())
        response.headers["Cache-Control"] = "public, max-age=300"
        return response, 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# GET /api/categories/<slug>/listings?sort=&page=&per_page=
@category_bp.get("/<slug>/listings")
def get_category_listings_route(slug):
    if not _valid_slug(slug):
        return jsonify({"error": MSG_CATEGORY_NOT_FOUND}), 404

    try:
        result = browse_category_listings_service(
            slug,
            sort=request.args.get("sort"),
            page=request.args.get("page"),
            per_page=request.args.get("per_page"),
        )
        return jsonify(result), 200
    except Exception as e:
        if "not found" in str(e).lower():
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 500


#_________________________________________________________
# Page Routing
#_________________________________________________________

def _render_categories_grid(not_found=False):
    status = 404 if not_found else 200
    return render_template(
        "categories.html",
        categories=get_category_tree_service(),
        not_found=not_found,
    ), status


@category_pages_bp.route("/categories")
def categories_page():
    return _render_categories_grid()


@category_pages_bp.route("/categories/<parent_slug>")
@category_pages_bp.route("/categories/<parent_slug>/<sub_slug>")
def category_listings_page(parent_slug, sub_slug=None):
    if not _valid_slug(parent_slug) or (sub_slug is not None and not _valid_slug(sub_slug)):
        return _render_categories_grid(not_found=True)

    try:
        page = get_category_page_service(parent_slug, sub_slug)
    except CategoryRedirect as moved:
        target = url_for(
            "category_pages_bp.category_listings_page",
            parent_slug=moved.parent_slug,
            sub_slug=moved.sub_slug,
        )
        if request.query_string:
            target = f"{target}?{request.query_string.decode('utf-8', 'ignore')}"
        return redirect(target, code=301)
    except Exception as e:
        if "not found" in str(e).lower():
            return _render_categories_grid(not_found=True)
        raise

    sort = request.args.get("sort")
    if sort not in ("newest", "price_asc", "price_desc"):
        sort = "newest"

    return render_template(
        "category_listings.html",
        page=page,
        parent=page["parent"],
        active_sub=page["active_sub"],
        current=page["current"],
        subcategories=page["subcategories"],
        sort=sort,
        current_user_id=session.get("user_id"),
    )
