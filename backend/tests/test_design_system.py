# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - theme files, versioned static links and the dev styleguide

import os
import re
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

from app import create_app


class TestDesignSystem(unittest.TestCase):

    def test_static_urls_carry_a_version(self):
        app = create_app()
        with app.test_request_context():
            from flask import url_for
            url = url_for("static", filename="css/theme.css")
        mtime = int(os.path.getmtime(os.path.join(PROJECT_ROOT, "static", "css", "theme.css")))
        self.assertEqual(url, f"/static/css/theme.css?v={mtime}")

    def test_missing_static_file_gets_no_version(self):
        app = create_app()
        with app.test_request_context():
            from flask import url_for
            self.assertEqual(url_for("static", filename="css/nope.css"), "/static/css/nope.css")

    def test_styleguide_is_off_by_default(self):
        with patch.dict(os.environ, {"PM_STYLEGUIDE": "0"}):
            app = create_app()
        self.assertEqual(app.test_client().get("/dev/styleguide").status_code, 404)

    def test_styleguide_renders_when_enabled(self):
        with patch.dict(os.environ, {"PM_STYLEGUIDE": "1"}):
            app = create_app()
        response = app.test_client().get("/dev/styleguide")
        self.assertEqual(response.status_code, 200)
        self.assertIn('class="pm"', response.get_data(as_text=True))

    def test_fonts_are_self_hosted_with_license(self):
        with open(os.path.join(PROJECT_ROOT, "static", "css", "theme.css"), encoding="utf-8") as f:
            css = f.read()
        for font in re.findall(r'url\("\.\./fonts/([^"]+)"\)', css):
            self.assertTrue(os.path.exists(os.path.join(PROJECT_ROOT, "static", "fonts", font)), font)
        self.assertNotIn("fonts.googleapis.com", css)
        self.assertTrue(os.path.exists(os.path.join(PROJECT_ROOT, "static", "fonts", "OFL.txt")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
