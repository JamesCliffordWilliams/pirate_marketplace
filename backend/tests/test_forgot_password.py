# Pirate Market - Forgot Password unit tests
# Added by Aniya Hopson 11/14/26
# Tests the reset-link logic and the two pages without a real database or real emails.

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path += [os.path.dirname(BACKEND_ROOT), BACKEND_ROOT]
os.environ.setdefault("SECRET_KEY", "pirate-market-test-key")  # the app won't start without one

from services.password_reset_service import PasswordResetService
from utils.auth_utils import verify_password
from app import create_app


def make_fake_db(*fetchone_results):
    """Builds a fake database connection. Each call to fetchone() returns the next value given."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = list(fetchone_results)
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor

class TestPasswordResetService(unittest.TestCase):

    def setUp(self):
        self.service = PasswordResetService()

    def test_token_hash_is_sha256_and_not_the_raw_token(self):
        hashed = self.service._hash_token("abc123")
        self.assertEqual(len(hashed), 64)
        self.assertNotEqual(hashed, "abc123")
        self.assertEqual(hashed, self.service._hash_token("abc123"))

    def test_unknown_email_returns_none(self):
        conn, cursor = make_fake_db(None)
        result = self.service.create_reset_token("nobody@hamptonu.edu", conn)
        self.assertIsNone(result)
        conn.commit.assert_not_called()

    def test_second_request_within_two_minutes_returns_none(self):
        conn, cursor = make_fake_db((1, "pirate1", "pirate1@hamptonu.edu"), (1,))
        result = self.service.create_reset_token("pirate1@hamptonu.edu", conn)
        self.assertIsNone(result)
        conn.commit.assert_not_called()

    def test_known_email_creates_token_and_stores_only_the_hash(self):
        conn, cursor = make_fake_db((1, "pirate1", "pirate1@hamptonu.edu"), None)
        result = self.service.create_reset_token("Pirate1@HamptonU.edu", conn)

        self.assertIsNotNone(result)
        username, email, raw_token = result
        self.assertEqual(username, "pirate1")
        self.assertEqual(email, "pirate1@hamptonu.edu")

        insert_params = cursor.execute.call_args_list[-1][0][1]
        self.assertEqual(insert_params[1], self.service._hash_token(raw_token))
        self.assertNotIn(raw_token, insert_params)
        conn.commit.assert_called_once()

    def test_database_error_rolls_back_and_returns_none(self):
        conn, cursor = make_fake_db()
        cursor.execute.side_effect = Exception("database is down")
        result = self.service.create_reset_token("pirate1@hamptonu.edu", conn)
        self.assertIsNone(result)
        conn.rollback.assert_called_once()

    def test_valid_token_is_accepted(self):
        conn, cursor = make_fake_db((1,))
        self.assertTrue(self.service.is_token_valid("good-token", conn))

    def test_expired_or_fake_token_is_rejected(self):
        conn, cursor = make_fake_db(None)
        self.assertFalse(self.service.is_token_valid("bad-token", conn))

    def test_reset_password_saves_hashed_new_password(self):
        conn, cursor = make_fake_db((7,))
        self.assertTrue(self.service.reset_password("good-token", "NewPass123", conn))

        update_params = cursor.execute.call_args_list[-1][0][1]
        saved_hash, user_id = update_params
        self.assertEqual(user_id, 7)
        self.assertNotEqual(saved_hash, "NewPass123")
        self.assertTrue(verify_password(saved_hash, "NewPass123"))
        conn.commit.assert_called_once()

    def test_reset_password_with_used_or_expired_token_fails(self):
        conn, cursor = make_fake_db(None)
        self.assertFalse(self.service.reset_password("used-token", "NewPass123", conn))
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()

class TestForgotPasswordPages(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()
        self.conn_patch = patch("controllers.auth_controller.get_connection", return_value=MagicMock())
        self.service_patch = patch("controllers.auth_controller.reset_service")
        self.email_patch = patch("controllers.auth_controller.send_password_reset_email")
        self.mock_conn = self.conn_patch.start()
        self.mock_service = self.service_patch.start()
        self.mock_email = self.email_patch.start()

    def tearDown(self):
        patch.stopall()

    def test_forgot_password_page_loads(self):
        response = self.client.get("/auth/forgot-password")
        self.assertEqual(response.status_code, 200)

    def test_blank_email_shows_error(self):
        response = self.client.post("/auth/forgot-password", data={"email": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Enter the email you used to sign up.", response.data)
        self.mock_service.create_reset_token.assert_not_called()

    def test_known_email_sends_reset_email_and_goes_to_login(self):
        self.mock_service.create_reset_token.return_value = ("pirate1", "pirate1@hamptonu.edu", "raw-token")
        response = self.client.post("/auth/forgot-password", data={"email": "pirate1@hamptonu.edu"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/auth/login"))
        self.mock_email.assert_called_once()
        to_email, username, link = self.mock_email.call_args[0]
        self.assertEqual(to_email, "pirate1@hamptonu.edu")
        self.assertIn("/auth/reset-password/raw-token", link)

    def test_unknown_email_gets_same_redirect_but_no_email(self):
        self.mock_service.create_reset_token.return_value = None
        response = self.client.post("/auth/forgot-password", data={"email": "nobody@hamptonu.edu"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/auth/login"))
        self.mock_email.assert_not_called()

    def test_database_down_shows_friendly_error(self):
        self.mock_conn.return_value = None
        response = self.client.post("/auth/forgot-password", data={"email": "pirate1@hamptonu.edu"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pirate Market can", response.data)

    def test_valid_link_shows_reset_form(self):
        self.mock_service.is_token_valid.return_value = True
        response = self.client.get("/auth/reset-password/good-token")
        self.assertEqual(response.status_code, 200)

    def test_bad_link_redirects_to_forgot_password(self):
        self.mock_service.is_token_valid.return_value = False
        response = self.client.get("/auth/reset-password/bad-token")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/auth/forgot-password"))

    def test_short_password_is_rejected(self):
        response = self.client.post("/auth/reset-password/good-token",
                                    data={"password": "short", "confirm_password": "short"})
        self.assertIn(b"at least 8 characters", response.data)
        self.mock_service.reset_password.assert_not_called()

    def test_mismatched_passwords_are_rejected(self):
        response = self.client.post("/auth/reset-password/good-token",
                                    data={"password": "NewPass123", "confirm_password": "NewPass999"})
        self.assertIn(b"don&#39;t match", response.data)
        self.mock_service.reset_password.assert_not_called()

    def test_successful_reset_logs_out_and_goes_to_login(self):
        self.mock_service.reset_password.return_value = True
        with self.client.session_transaction() as sess:
            sess["user"] = "pirate1"

        response = self.client.post("/auth/reset-password/good-token",
                                    data={"password": "NewPass123", "confirm_password": "NewPass123"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/auth/login"))
        with self.client.session_transaction() as sess:
            self.assertNotIn("user", sess)

    def test_used_link_cannot_reset_password(self):
        self.mock_service.reset_password.return_value = False
        response = self.client.post("/auth/reset-password/used-token",
                                    data={"password": "NewPass123", "confirm_password": "NewPass123"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/auth/forgot-password"))


if __name__ == "__main__":
    unittest.main()