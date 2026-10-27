# Pirate Market Campus Marketplace
# Created by Aniya Hopson - 10/26/26 - sellers see and complete their orders

"""
controllers/order_controller.py

GET  /api/seller/orders                      orders that include my listings
POST /api/seller/orders/<order_id>/complete  mark my items in that order picked up
"""

from flask import Blueprint, jsonify, session

from models.order_model import complete_order, expire_old_orders, get_seller_orders
from models.storefront_model import get_storefront_by_owner_id

orders_bp = Blueprint("orders", __name__)


@orders_bp.route("/seller/orders", methods=["GET"])
def seller_orders():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    storefront = get_storefront_by_owner_id(user_id)
    if not storefront:
        return jsonify({"error": "You don't have a storefront."}), 404

    expire_old_orders()  # so statuses are up to date
    return jsonify({"orders": get_seller_orders(storefront["id"])}), 200


@orders_bp.route("/seller/orders/<int:order_id>/complete", methods=["POST"])
def mark_order_picked_up(order_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    storefront = get_storefront_by_owner_id(user_id)
    if not storefront:
        return jsonify({"error": "You don't have a storefront."}), 404

    try:
        expire_old_orders()
        status = complete_order(order_id, storefront["id"])
        return jsonify({"success": True, "order_status": status}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400