# Added by Billy Anders - implement wallet with stripe integration
import os

import stripe
from flask import Blueprint, request, jsonify, session
from services.wallet_service import WalletService

wallet_bp = Blueprint('wallet', __name__, url_prefix="/api")
wallet_service = WalletService()


def get_current_user():
    user_id = session.get("user_id")
    role = session.get("role", "user")

    if not user_id:
        return None

    try:
        return {"id": int(user_id), "role": role}
    except Exception:
        return None


@wallet_bp.route('/wallet', methods=['GET'])
def get_wallet():
    try:
        current_user = get_current_user()
        if current_user is None:
            return jsonify({"error": "Please log in to use your wallet."}), 401

        success, result = wallet_service.get_wallet(current_user['id'])

        if success:
            return jsonify(result), 200
        else:
            return jsonify({"error": result}), 500

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@wallet_bp.route('/wallet/deposit', methods=['POST'])
def add_funds():
    try:
        current_user = get_current_user()
        if current_user is None:
            return jsonify({"error": "Please log in to use your wallet."}), 401

        data = request.get_json()
        if not data or 'amount' not in data:
            return jsonify({"error": "Missing required field: amount"}), 400

        method = data.get('method', 'stripe')

        if method == 'demo':
            success, result = wallet_service.add_demo_funds(current_user['id'], data['amount'])
            if success:
                return jsonify({
                    "message": "Demo funds added",
                    "transaction": result,
                    "balance": result["balance_after"]
                }), 201
            return jsonify({"error": result}), 400

        if method == 'stripe':
            success, result = wallet_service.create_deposit_session(current_user['id'], data['amount'])
            if success:
                return jsonify(result), 200
            return jsonify({"error": result}), 400

        return jsonify({"error": "method must be 'stripe' or 'demo'"}), 400

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@wallet_bp.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ["STRIPE_WEBHOOK_SECRET"]
        )
    except (ValueError, stripe.SignatureVerificationError):
        return "", 400

    if event["type"] in ("checkout.session.completed",
                         "checkout.session.async_payment_succeeded"):
        ok, err = wallet_service.fulfill_checkout(event["data"]["object"])
        if not ok:
            return "", 500

    return "", 200


@wallet_bp.route('/wallet/transactions', methods=['GET'])
def get_wallet_transactions():
    try:
        current_user = get_current_user()
        if current_user is None:
            return jsonify({"error": "Please log in to use your wallet."}), 401

        try:
            limit = int(request.args.get('limit', 50))
            offset = int(request.args.get('offset', 0))
        except ValueError:
            return jsonify({"error": "limit and offset must be integers"}), 400

        success, result = wallet_service.get_transaction_history(
            current_user['id'],
            request.args.get('type'),
            limit,
            offset
        )

        if success:
            return jsonify({"transactions": result}), 200
        else:
            return jsonify({"error": result}), 400

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500