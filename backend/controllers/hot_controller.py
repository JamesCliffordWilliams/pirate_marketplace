# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
controllers/hot_controller.py

This file has the routes for the Hot page.

API:
- GET /api/hot gives the Hot and Rising cards
- POST /api/listings/<id>/interest saves a detail_view for a logged in shopper

Pages:
- GET /hot is the Hot page
"""

from flask import Blueprint, request, jsonify, session, render_template, current_app

from models.interest_model import is_listing_public
from services.interest_service import track_interest
from services.hot_service import get_hot_page_data

# API blueprint
hot_bp = Blueprint("hot_bp", __name__, url_prefix="/api")

# Page blueprint
hot_pages_bp = Blueprint("hot_pages_bp", __name__)

API_MAX_AGE_SECONDS = 60     # how long browsers can cache GET /api/hot


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
    except Exception:
        # This logs the full error for us and gives shoppers a simple message
        current_app.logger.exception("GET /api/hot failed")
        return jsonify({"error": "Couldn't load the Hot page. Please try again."}), 500


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
    except Exception:
        current_app.logger.exception("POST /api/listings/%s/interest failed", listing_id)
        return jsonify({"error": "Something went wrong."}), 500

    track_interest(listing_id, user_id, "detail_view")
    return "", 204


#_________________________________________________________
# Page Routing
#_________________________________________________________

@hot_pages_bp.route("/hot")
def hot_page():
    return render_template("hot.html", current_user_id=session.get("user_id"))
