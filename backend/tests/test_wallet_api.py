import os
import sys
import unittest
from unittest.mock import patch

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path += [os.path.dirname(BACKEND_ROOT), BACKEND_ROOT]

from app import create_app
from controllers.wallet_controller import wallet_service
from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema


class TestWalletLogin(unittest.TestCase):
    def test_headers_cannot_replace_login(self):
        client = create_app().test_client()
        for path, payload in (("", None), ("/transactions", None),
                              ("/deposit", {"amount": 5}), ("/withdraw", {"amount": 5})):
            response = client.open("/api/wallet" + path, method="POST" if payload else "GET",
                                   json=payload, headers={"X-User-Id": "123"})
            self.assertEqual(response.status_code, 401)

    def test_session_wins_over_another_user_header(self):
        client = create_app().test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 42
        with patch.object(wallet_service, "get_wallet", return_value=(True, {"balance": 0})) as get:
            response = client.get("/api/wallet", headers={"X-User-Id": "99"})
        self.assertEqual(response.status_code, 200)
        get.assert_called_once_with(42)


@require_local_db
class TestWalletAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = ThrowawaySchema(prefix="test_wallet").create()
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        cls.db.drop()

    def setUp(self):
        self.user_id = self.db.add_user()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["user"] = "shopper"
            sess["user_id"] = self.user_id

    def balance(self):
        response = self.client.get("/api/wallet")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["balance"]

    def test_wallet_page_and_balance(self):
        response = self.client.get("/wallet")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("vaultUserId", response.get_data(as_text=True))
        self.assertEqual(self.balance(), 0)

    def test_deposit_withdraw_and_history(self):
        response = self.client.post("/api/wallet/deposit", json={"amount": "25.50"})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertEqual(self.balance(), 25.50)
        response = self.client.post("/api/wallet/withdraw", json={"amount": "10.25"})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertEqual(self.balance(), 15.25)
        history = self.client.get("/api/wallet/transactions").get_json()["transactions"]
        self.assertEqual([t["type"] for t in history], ["WITHDRAW", "DEPOSIT"])

    def test_overdraw_and_invalid_deposits_leave_balance_unchanged(self):
        self.client.post("/api/wallet/deposit", json={"amount": 5})
        self.assertEqual(self.client.post("/api/wallet/withdraw", json={"amount": 6}).status_code, 400)
        for amount in (0, -1, True, "NaN", "1.234", 10001):
            self.assertEqual(self.client.post("/api/wallet/deposit", json={"amount": amount}).status_code, 400)
        self.assertEqual(self.balance(), 5)


if __name__ == "__main__":
    unittest.main()
