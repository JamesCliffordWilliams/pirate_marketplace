# Billy
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from app import create_app
from backend.config.db import get_connection

class TestWalletAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()
        cls.user_id = cls._resolve_user_id()

        if cls.user_id is None:
            raise unittest.SkipTest("No seeded user available for wallet tests.")

    @staticmethod
    def _resolve_user_id():
        conn = get_connection()
        if conn is None:
            return None
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM users ORDER BY id LIMIT 1;")
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            cur.close()
            conn.close()

    def setUp(self):
        self.start_balance, self.last_tx_id = self._snapshot()

    def tearDown(self):
        self._restore()

    def _snapshot(self):
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT balance FROM wallets WHERE user_id = %s;", (self.user_id,))
            row = cur.fetchone()
            cur.execute("SELECT COALESCE(MAX(id), 0) FROM wallet_transactions WHERE user_id = %s;",
                        (self.user_id,))
            return (row[0] if row else None), cur.fetchone()[0]
        finally:
            cur.close()
            conn.close()

    def _restore(self):
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM wallet_transactions WHERE user_id = %s AND id > %s;",
                        (self.user_id, self.last_tx_id))
            if self.start_balance is None:
                cur.execute("DELETE FROM wallets WHERE user_id = %s;", (self.user_id,))
            else:
                cur.execute("UPDATE wallets SET balance = %s WHERE user_id = %s;",
                            (self.start_balance, self.user_id))
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def _auth_headers(self):
        return {"X-User-Id": str(self.user_id)}

    def _balance(self):
        return float(self.client.get("/api/wallet", headers=self._auth_headers()).get_json()["balance"])

    def test_missing_header(self):
        calls = [
            self.client.get("/api/wallet"),
            self.client.post("/api/wallet/deposit", json={"amount": 5}),
            self.client.post("/api/wallet/withdraw", json={"amount": 5}),
            self.client.get("/api/wallet/transactions"),
        ]
        self.assertEqual([r.status_code for r in calls], [401] * 4)

    def test_invalid_header(self):
        response = self.client.get("/api/wallet", headers={"X-User-Id": "a"})
        self.assertEqual(response.status_code, 401)

    def test_get_wallet(self):
        response = self.client.get("/api/wallet", headers=self._auth_headers())
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    def test_deposit_then_withdraw(self):
        before = self._balance()

        deposit = self.client.post("/api/wallet/deposit", json={"amount": 25},
                                   headers=self._auth_headers())
        self.assertEqual(deposit.status_code, 201, deposit.get_data(as_text=True))
        self.assertEqual(self._balance(), before + 25)

        withdraw = self.client.post("/api/wallet/withdraw", json={"amount": 10},
                                    headers=self._auth_headers())
        self.assertEqual(withdraw.status_code, 201, withdraw.get_data(as_text=True))
        self.assertEqual(self._balance(), before + 15)

    def test_overdraw_rejected(self):
        before = self._balance()
        response = self.client.post("/api/wallet/withdraw", json={"amount": before + 1000},
                                    headers=self._auth_headers())
        self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
        self.assertEqual(self._balance(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)