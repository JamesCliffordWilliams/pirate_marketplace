# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - landing, log in and sign up pages (no database needed)

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from app import create_app
from controllers import auth_controller


class TestEntryPages(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.secret_key = "test"
        self.client = self.app.test_client()
        patcher = patch.object(auth_controller, "get_connection", return_value=MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_landing_uses_real_links_not_button_images(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('href="/auth/login"', html)
        self.assertIn('href="/auth/signup"', html)
        self.assertIn(">Log in<", html)
        self.assertIn(">Create account<", html)
        self.assertNotIn("login_button.png", html)
        self.assertNotIn("signup_button.png", html)

    def test_login_form_has_labels_and_autocomplete(self):
        html = self.client.get("/auth/login").get_data(as_text=True)
        self.assertIn('<label class="pm-label" for="username">Username</label>', html)
        self.assertIn('autocomplete="username"', html)
        self.assertIn('autocomplete="current-password"', html)
        self.assertIn(">Log in</button>", html)
        for vault_copy in ("Decrypt", "Access Cipher", "Authorize", "Create Identity"):
            self.assertNotIn(vault_copy, html)

    def test_wrong_password_shows_the_form_again_with_a_message(self):
        with patch.object(auth_controller.service, "validate_login", return_value=(False, None)):
            response = self.client.post("/auth/login", data={"username": "pat", "password": "nope"})
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("That username and password don&#39;t match.", html)  # escaped by Jinja
        self.assertIn('value="pat"', html)          # keeps the username
        self.assertNotIn('value="nope"', html)      # never echoes the password
        self.assertIn('<form', html)

    def test_signup_problem_shows_the_form_again_with_the_reason(self):
        with patch.object(auth_controller.service, "register_user",
                          return_value=(False, "You Must Use a Hampton University Associated Email")):
            response = self.client.post("/auth/signup", data={
                "username": "pat", "email": "pat@gmail.com", "password": "secret1"})
        html = response.get_data(as_text=True)
        self.assertIn("Use your Hampton University email", html)
        self.assertIn('value="pat@gmail.com"', html)
        self.assertNotIn('value="secret1"', html)

    def test_signup_success_shows_message_on_login(self):
        with patch.object(auth_controller.service, "register_user", return_value=(True, "ok")):
            response = self.client.post("/auth/signup", data={
                "username": "pat", "email": "pat@my.hamptonu.edu", "password": "secret1"}, follow_redirects=True)
        self.assertIn("Account created. Log in to start shopping.", response.get_data(as_text=True))

    # Added by James Williams 10/27/26 - the site is only for logged-in users
    def test_pages_need_a_login(self):
        for path in ("/storefronts", "/storefronts/1", "/listings/1", "/categories", "/categories/other",
                     "/hot", "/listings/create", "/storefronts/my", "/storefront", "/about", "/cart"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers["Location"].endswith("/auth/login"))
        for path in ("/", "/auth/login", "/auth/signup"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
