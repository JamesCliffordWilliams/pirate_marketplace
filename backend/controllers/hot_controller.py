# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
controllers/hot_controller.py

Purpose:
Routes for the Hot page.

API:
- GET  /api/hot                    -> Hot, Rising and Just Listed cards
- POST /api/listings/<id>/interest -> records a detail_view (logged-in shoppers only)

Pages:
- GET /hot                         -> Hot page
"""

from flask import Blueprint, request, jsonify, session, render_template

from config.hot_ranking import API_MAX_AGE_SECONDS
from models.interest_model import is_listing_public
from services.interest_service import track_interest
from services.hot_service import get_hot_page_data

# API blueprint
hot_bp = Blueprint("hot_bp", __name__, url_prefix="/api")

# Page blueprint
hot_pages_bp = Blueprint("hot_pages_bp", __name__)


#_________________________________________________________
# API Routes
#_________________________________________________________

# GET /api/hot
@hot_bp.get("/hot")
def get_hot_route():
    try:
        response = jsonify(get_hot_page_data())
        response.headers["Cache-Control"] = f"public, max-age={API_MAX_AGE_SECONDS}"
        return response, 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# POST /api/listings/<id>/interest  {"kind": "detail_view"}
@hot_bp.post("/listings/<int:listing_id>/interest")
def record_listing_interest_route(listing_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    if not request.is_json:
        return jsonify({"error": "Expected JSON"}), 415

    data = request.get_json(silent=True) or {}
    if data.get("kind") != "detail_view":
        return jsonify({"error": "Invalid kind"}), 400

    try:
        if not is_listing_public(listing_id):
            return jsonify({"error": "Listing not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    track_interest(listing_id, user_id, "detail_view")
    return "", 204


#_________________________________________________________
# Page Routing
#_________________________________________________________

@hot_pages_bp.route("/hot")
def hot_page():
    return render_template("hot.html", current_user_id=session.get("user_id"))
