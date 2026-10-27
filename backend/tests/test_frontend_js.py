# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - JavaScript checks that don't need a browser
#
# - Every static/js file parses (JavaScriptCore `jsc`, ships with macOS; skipped if absent)
# - Picker search/selection logic and card helpers (tests/js/frontend_logic_test.js)
# - Static guards: the shared card never puts data into innerHTML; the nav toggle
#   lives in nav_pane.js; templates reference static files that exist

import glob
import os
import re
import shutil
import subprocess
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
JS_DIR = os.path.join(PROJECT_ROOT, "static", "js")

JSC_CANDIDATES = [
    "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc",
    shutil.which("jsc") or "",
]
JSC = next((path for path in JSC_CANDIDATES if path and os.path.exists(path)), None)


def read(relative_path):
    with open(os.path.join(PROJECT_ROOT, relative_path), encoding="utf-8") as handle:
        return handle.read()


@unittest.skipIf(JSC is None, "JavaScriptCore (jsc) not available")
class TestJavaScriptWithJsc(unittest.TestCase):

    def test_all_scripts_parse(self):
        for path in sorted(glob.glob(os.path.join(JS_DIR, "*.js"))):
            with self.subTest(script=os.path.basename(path)):
                result = subprocess.run(
                    [JSC, "-e", f"checkSyntax({path!r})"], capture_output=True, text=True, timeout=30
                )
                self.assertEqual(result.stdout + result.stderr, "", path)

    def test_picker_and_card_logic(self):
        script = os.path.join(os.path.dirname(__file__), "js", "frontend_logic_test.js")
        result = subprocess.run(
            [JSC, script, "--", PROJECT_ROOT], capture_output=True, text=True, timeout=30
        )
        output = result.stdout + result.stderr
        self.assertTrue(output.startswith("OK "), output)


class TestFrontendStaticGuards(unittest.TestCase):

    def test_listing_card_innerhtml_is_constant_only(self):
        source = read("static/js/listing_card.js")
        allowed = {'""', '"&times;"', '"&#10094;"', '"&#10095;"', "WISHLIST_ICON_SVG"}
        # value up to the end of the line (string literals here contain ";", e.g. "&times;")
        assignments = [value.rstrip().rstrip(";") for value in re.findall(r"\.innerHTML\s*=\s*(.+)$", source, re.M)]
        self.assertTrue(assignments)
        for value in assignments:
            self.assertIn(value.strip(), allowed, f"innerHTML assigned non-constant: {value}")
        self.assertNotIn("insertAdjacentHTML", source)
        self.assertNotIn("outerHTML", source)

    def test_category_scripts_never_use_innerhtml_with_data(self):
        for path in ("static/js/category_listings.js", "static/js/category_picker.js"):
            with self.subTest(path=path):
                source = read(path)
                self.assertNotRegex(source, r"\.innerHTML\s*=")
                for match in re.findall(r"insertAdjacentHTML\([^,]+,\s*([^)]+)\)", source):
                    self.assertEqual(match.strip(), "CHEVRON_SVG")

    def test_nav_toggle_moved_to_nav_pane(self):
        self.assertNotIn('document.querySelector(".menu-btn")', read("static/js/storefront.js"))
        self.assertIn('document.querySelector(".menu-btn")', read("static/js/nav_pane.js"))

    def test_storefront_view_uses_shared_card(self):
        source = read("static/js/storefront_view.js")
        self.assertIn("VaultListingCard.create(", source)
        self.assertNotIn("function createListingCard", source)
        self.assertIn("focusLinkedListing", source)

    def test_edit_page_no_longer_forces_active(self):
        source = read("static/js/edit_listing.js")
        self.assertNotIn('status: "ACTIVE"', source)
        self.assertIn("computeSaveStatus", source)

    def test_templates_reference_existing_static_files(self):
        for template in glob.glob(os.path.join(PROJECT_ROOT, "templates", "**", "*.html"), recursive=True):
            with open(template, encoding="utf-8") as handle:
                html = handle.read()
            for filename in re.findall(r"url_for\('static', filename='([^']+)'\)", html):
                with self.subTest(template=os.path.basename(template), file=filename):
                    self.assertTrue(os.path.exists(os.path.join(PROJECT_ROOT, "static", filename)))

    def test_placeholder_image_exists(self):
        self.assertTrue(os.path.exists(os.path.join(PROJECT_ROOT, "static", "images", "listing-placeholder.svg")))
        self.assertNotIn("placeholder-storefront.png", read("static/js/listing_card.js"))
        self.assertNotIn("placeholder-storefront.png", read("static/js/storefront_view.js"))

    # Added by James Williams 10/26/26
    def test_hot_page_never_renders_from_the_browser_cache(self):
        # /api/hot is cacheable (max-age=60); the page itself always asks the server again
        source = read("static/js/hot.js")
        self.assertRegex(source, r'fetch\("/api/hot",\s*\{\s*cache:\s*"no-cache"\s*\}\)')


if __name__ == "__main__":
    unittest.main(verbosity=2)
