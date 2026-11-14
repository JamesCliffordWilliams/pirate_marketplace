
"""
controllers/saved_payment_method_controller.py

Purpose:
Provides API routes for viewing and removing saved cards.

Stripe handles card collection and payment processing.
This controller never accepts raw card numbers or CVVs.
"""

from flask import Blueprint, jsonify, session

from services.saved_payment_method_service import (
    get_saved_cards_service,
    remove_saved_card_service,
)

saved_payment_method_bp = Blueprint(
    "saved_payment_method",
    __name__,
    url_prefix="/api"
)


def get_current_user():
    """Return the logged-in user's ID."""

    user_id = session.get("user_id")

    if not user_id:
        return None

    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


@saved_payment_method_bp.route(
    "/saved-cards",
    methods=["GET"]
)
def get_saved_cards():
    """Return saved cards belonging to the logged-in user."""

    user_id = get_current_user()

    if user_id is None:
        return jsonify({
            "error": "Please log in to view your saved cards."
        }), 401

    try:
        cards = get_saved_cards_service(user_id)

        return jsonify({
            "saved_cards": cards
        }), 200

    except Exception:
        return jsonify({
            "error": "Unable to retrieve saved cards."
        }), 500


@saved_payment_method_bp.route(
    "/saved-cards/<int:payment_method_id>",
    methods=["DELETE"]
)
def delete_saved_card(payment_method_id):
    """Delete a saved card belonging to the logged-in user."""

    user_id = get_current_user()

    if user_id is None:
        return jsonify({
            "error": "Please log in to remove a saved card."
        }), 401

    try:
        deleted = remove_saved_card_service(
            user_id,
            payment_method_id
        )

        if not deleted:
            return jsonify({
                "error": "Saved card not found."
            }), 404

        return jsonify({
            "message": "Saved card removed successfully."
        }), 200

    except ValueError as error:
        return jsonify({
            "error": str(error)
        }), 404

    except Exception:
        return jsonify({
            "error": "Unable to remove saved card."
        }), 500
