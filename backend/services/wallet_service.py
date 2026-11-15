# Added by Billy Anders - implement wallet with stripe integration
import decimal
import os

import flask
import psycopg2
import stripe

from models.wallet_model import (
    get_wallet_balance,
    create_wallet_transaction,
    get_wallet_transactions_by_user_id,
)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

MAX_SINGLE_DEPOSIT = decimal.Decimal("100.00")
VALID_TRANSACTION_TYPES = ("DEPOSIT", "PURCHASE")

def parse_amount(raw_amount):
    if isinstance(raw_amount, bool):
        return None

    try:
        amount = decimal.Decimal(str(raw_amount))
    except decimal.InvalidOperation:
        return None

    if not amount.is_finite() or amount <= 0:
        return None

    exponent = amount.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -2:
        return None

    return amount

class WalletService:
    @staticmethod
    def get_wallet(user_id):
        try:
            return True, {"balance": get_wallet_balance(user_id)}
        except Exception as e:
            return False, f"Failed to retrieve wallet: {str(e)}"

    @staticmethod
    def validate_deposit_amount(raw_amount):
        amount = parse_amount(raw_amount)
        if amount is None:
            return None, "Amount must be a positive number with at most 2 decimal places"
        if amount > MAX_SINGLE_DEPOSIT:
            return None, f"Maximum single deposit is {MAX_SINGLE_DEPOSIT}"
        return amount, None

    def create_deposit_session(self, user_id, raw_amount):
        amount, error = self.validate_deposit_amount(raw_amount)
        if error:
            return False, error

        try:
            base_url = flask.request.host_url.rstrip("/")
            session = stripe.checkout.Session.create(
                mode="payment",
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "Wallet"},
                        "unit_amount": int(amount * 100),
                    },
                    "quantity": 1,
                }],
                client_reference_id=str(user_id),
                metadata={"user_id": str(user_id)},
                success_url=f"{base_url}/wallet?status=success",
                cancel_url=f"{base_url}/wallet?status=cancelled",
            )
            return True, {"checkout_url": session.url}
        except stripe.StripeError as e:
            return False, f"Payment provider error: {e.user_message or str(e)}"
        except Exception as e:
            return False, f"Failed to start payment: {str(e)}"

    @staticmethod
    def fulfill_checkout(session):
        if session["payment_status"] != "paid":
            return True, None

        user_id = int(session["metadata"]["user_id"])
        amount = decimal.Decimal(session["amount_total"]) / 100

        try:
            tx = create_wallet_transaction(
                user_id, "DEPOSIT", amount,
                description="Stripe",
                stripe_session_id=session["id"],
            )
            return True, tx
        except psycopg2.errors.UniqueViolation:
            return True, None
        except Exception as e:
            return False, str(e)

    def add_demo_funds(self, user_id, raw_amount):
        amount, error = self.validate_deposit_amount(raw_amount)
        if error:
            return False, error

        try:
            tx = create_wallet_transaction(user_id, "DEPOSIT", amount, "Demo")
            return True, tx
        except Exception as e:
            return False, f"Failed to add funds: {str(e)}"

    @staticmethod
    def get_transaction_history(user_id, transaction_type=None, limit=50, offset=0):
        if transaction_type:
            transaction_type = transaction_type.upper()
            if transaction_type not in VALID_TRANSACTION_TYPES:
                return False, f"Invalid type filter. Use one of: {', '.join(VALID_TRANSACTION_TYPES)}"

        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        try:
            transactions = get_wallet_transactions_by_user_id(user_id, transaction_type, limit, offset)
            return True, transactions
        except Exception as e:
            return False, f"Failed to retrieve transaction history: {str(e)}"