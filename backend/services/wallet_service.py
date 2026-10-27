from decimal import Decimal, InvalidOperation
from models.wallet_model import (
    get_wallet_balance,
    create_wallet_transaction,
    get_wallet_transactions_by_user_id,
)

MAX_SINGLE_DEPOSIT = Decimal("10000.00")
VALID_TRANSACTION_TYPES = ("DEPOSIT", "WITHDRAW", "PURCHASE")


def parse_amount(raw_amount):
    if isinstance(raw_amount, bool):
        return None

    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError):
        return None

    if not amount.is_finite() or amount <= 0:
        return None

    if amount != amount.quantize(Decimal("0.01")):
        return None

    return amount


class WalletService:

    def get_wallet(self, user_id):
        try:
            return True, {"balance": get_wallet_balance(user_id)}
        except Exception as e:
            return False, f"Failed to retrieve wallet: {str(e)}"

    def add_funds(self, user_id, raw_amount):
        amount = parse_amount(raw_amount)
        if amount is None:
            return False, "Amount must be a positive number with at most 2 decimal places"

        if amount > MAX_SINGLE_DEPOSIT:
            return False, f"Maximum single deposit is {MAX_SINGLE_DEPOSIT}"

        try:
            transaction = create_wallet_transaction(user_id, "DEPOSIT", amount, "Added funds")
            return True, transaction
        except Exception as e:
            return False, f"Failed to add funds: {str(e)}"

    def remove_funds(self, user_id, raw_amount):
        amount = parse_amount(raw_amount)
        if amount is None:
            return False, "Amount must be a positive number with at most 2 decimal places"

        try:
            transaction = create_wallet_transaction(user_id, "WITHDRAW", amount, "Removed funds")
            return True, transaction
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Failed to remove funds: {str(e)}"

    def get_transaction_history(self, user_id, transaction_type=None, limit=50, offset=0):
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