from decimal import Decimal
from db import get_connection


def get_wallet_balance(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO wallets (user_id)
        VALUES (%s)
        ON CONFLICT (user_id) DO NOTHING;
    """, (user_id,))

    cur.execute("SELECT balance FROM wallets WHERE user_id = %s;", (user_id,))
    row = cur.fetchone()
    conn.commit()

    cur.close()
    conn.close()

    return float(row[0])


def create_wallet_transaction(user_id, transaction_type, amount, description=None, order_id=None, conn=None):
    amount = Decimal(str(amount))

    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO wallets (user_id)
            VALUES (%s)
            ON CONFLICT (user_id) DO NOTHING;
        """, (user_id,))

        cur.execute("SELECT balance FROM wallets WHERE user_id = %s FOR UPDATE;", (user_id,))
        balance = cur.fetchone()[0]

        if transaction_type in ("DEPOSIT"):
            new_balance = balance + amount
        elif transaction_type in ("WITHDRAW", "PURCHASE"):
            new_balance = balance - amount
            if new_balance < 0:
                raise ValueError("Insufficient wallet funds")
        else:
            raise ValueError("Invalid transaction type")

        cur.execute("""
            UPDATE wallets
            SET balance = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s;
        """, (new_balance, user_id))

        query = """
            INSERT INTO wallet_transactions (user_id, type, amount, balance_after, description, order_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, user_id, type, amount, balance_after, description, order_id, created_at;
        """

        cur.execute(query, (user_id, transaction_type, amount, new_balance, description, order_id))
        row = cur.fetchone()

        if owns_conn:
            conn.commit()

    except Exception:
        if owns_conn:
            conn.rollback()
        raise

    finally:
        cur.close()
        if owns_conn:
            conn.close()

    return {
        "id": row[0],
        "user_id": row[1],
        "type": row[2],
        "amount": float(row[3]),
        "balance_after": float(row[4]),
        "description": row[5],
        "order_id": row[6],
        "created_at": row[7],
    }


def get_wallet_transactions_by_user_id(user_id, transaction_type=None, limit=50, offset=0):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT id, user_id, type, amount, balance_after, description, order_id, created_at
        FROM wallet_transactions
        WHERE user_id = %s
    """
    params = [user_id]

    if transaction_type:
        query += " AND type = %s"
        params.append(transaction_type)

    query += " ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s;"
    params.extend([limit, offset])

    cur.execute(query, params)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    transactions = []
    for row in rows:
        transactions.append({
            "id": row[0],
            "user_id": row[1],
            "type": row[2],
            "amount": float(row[3]),
            "balance_after": float(row[4]),
            "description": row[5],
            "order_id": row[6],
            "created_at": row[7],
        })

    return transactions