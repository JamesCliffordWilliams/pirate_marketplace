
from flask import Blueprint, request, jsonify
from services.wallet_service import WalletService

wallet_bp = Blueprint('wallet', __name__, url_prefix="/api")
wallet_service = WalletService()


def get_current_user():
    user_id = request.headers.get("X-User-Id")
    role = request.headers.get("X-User-Role", "user")

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
            return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

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
            return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

        data = request.get_json()
        if not data or 'amount' not in data:
            return jsonify({"error": "Missing required field: amount"}), 400

        success, result = wallet_service.add_funds(current_user['id'], data['amount'])

        if success:
            return jsonify({
                "message": "Funds added successfully",
                "transaction": result,
                "balance": result["balance_after"]
            }), 201
        else:
            return jsonify({"error": result}), 400

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@wallet_bp.route('/wallet/withdraw', methods=['POST'])
def remove_funds():
    try:
        current_user = get_current_user()
        if current_user is None:
            return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

        data = request.get_json()
        if not data or 'amount' not in data:
            return jsonify({"error": "Missing required field: amount"}), 400

        success, result = wallet_service.remove_funds(current_user['id'], data['amount'])

        if success:
            return jsonify({
                "message": "Funds removed successfully",
                "transaction": result,
                "balance": result["balance_after"]
            }), 201
        else:
            return jsonify({"error": result}), 400

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@wallet_bp.route('/wallet/transactions', methods=['GET'])
def get_wallet_transactions():
    try:
        current_user = get_current_user()
        if current_user is None:
            return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

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