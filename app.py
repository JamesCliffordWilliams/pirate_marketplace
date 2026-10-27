import os
import sys
from datetime import timedelta

from flask import Flask, render_template, redirect, request, url_for, session

# Added back by James Williams 10/27/26 - lets python3 app.py find the backend folder outside PyCharm
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

# Billy: Rewrite
from controllers.admin_controller import admin_bp
from controllers.auth_controller import auth_bp
from controllers.category_controller import category_bp, category_pages_bp # James
from controllers.checkout_controller import checkout_bp
from controllers.hot_controller import hot_bp, hot_pages_bp # James
from controllers.listing_controller import listing_bp
from controllers.message_controller import message_bp
from controllers.purchase_controller import purchase_bp
from controllers.return_controller import returns_bp
from controllers.storefront_controller import storefront_bp, storefront_pages_bp
from controllers.wallet_controller import wallet_bp # Billy
from controllers.wishlist_controller import wishlist_bp

# Billy: Session Timeout
SESSION_LIFETIME_MINUTES = 15

# Billy
PUBLIC_PAGES = [
    ("/", "index", "index.html"),
]

# Billy
PRIVATE_PAGES = [
    ("/about", "about", "about.html"),
    ("/storefront", "storefront", "homepage.html"),
    ("/create-storefront", "create_storefront", "create_storefront.html"),
    ("/create-listing", "create_listing", "create_listing.html"),
    ("/cart", "cart", "cart.html"),
    ("/checkout", "checkout", "checkout.html"),
    ("/order-confirmation", "order_confirmation", "order_confirmation.html"),
    ("/my-storefront", "my_storefront", "my_storefront.html"),
]

# Added by James Williams 10/27/26 - storefront, product, category and Hot pages need a login too
LOGIN_REQUIRED_BLUEPRINTS = ("storefront_pages_bp", "category_pages_bp", "hot_pages_bp")

# Billy: Rewrite
BLUEPRINTS = [
    (auth_bp, "/auth"),
    (checkout_bp, "/api"),
    (listing_bp, None),
    (message_bp, None), # Billy
    (storefront_bp, None),
    (storefront_pages_bp, None),
    (purchase_bp, None),
    (wishlist_bp, None),
    (admin_bp, None),
    (returns_bp, None),
    (wallet_bp, None),
    (category_bp, None), # James
    (category_pages_bp, None), # James
    (hot_bp, None), # James
    (hot_pages_bp, None), # James
]

# Billy: Rewrite
def register_pages(app):
    for url, endpoint, template in PUBLIC_PAGES:
        app.add_url_rule(url, endpoint, lambda t=template: render_template(t))
    for url, endpoint, template in PRIVATE_PAGES: # Aniya: reroute the user login if they are not a user
        app.add_url_rule(url, endpoint, lambda t=template: render_template(t) if session.get('user') else redirect(url_for("auth.login")))

# Billy: Rewrite
def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.secret_key = os.getenv('SECRET_KEY') # James: the secret key comes from an environment variable so it isn't sitting in the code

    if not app.secret_key:
        raise RuntimeError("SECRET_KEY is not set.")

    # Billy: Session Timeout
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=SESSION_LIFETIME_MINUTES)

    # Billy: Session Timeout
    @app.before_request
    def make_session_permanent():
        if session.get("user"):
            session.permanent = True

    # Added by James Williams 10/26/26 - limits upload size and shows a clear message if it's too big
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

    @app.errorhandler(413)
    def upload_too_large(_error):
        return {"error": "That upload is too large. Photos must add up to less than 32 MB."}, 413

    # Added by James Williams 10/26/26 - adds the file's last saved time to static links
    # so browsers load the new CSS and JS after a deploy
    static_versions = {}

    @app.url_defaults
    def static_version(endpoint, values):
        if endpoint != "static" or "filename" not in values or "v" in values:
            return
        filename = values["filename"]
        if filename not in static_versions or app.debug:
            try:
                static_versions[filename] = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
            except OSError:
                return
        values["v"] = static_versions[filename]

    # Added by James Williams 10/26/26 - values the shared header needs on every page
    @app.context_processor
    def shell_context():
        bag_count = 0
        for item in session.get("cart") or []:
            try:
                bag_count += max(int(item.get("quantity", 1)), 0)
            except (TypeError, ValueError, AttributeError):
                bag_count += 1
        return {"bag_count": bag_count}

    # Added by James Williams 10/26/26 - style guide page, only turned on for development
    if app.debug or os.getenv("PM_STYLEGUIDE") == "1":
        @app.get("/dev/styleguide")
        def styleguide():
            return render_template("dev/styleguide.html")

    # Added by James Williams 10/27/26 - sends logged out users to login, same as PRIVATE_PAGES
    @app.before_request
    def require_login():
        if request.blueprint in LOGIN_REQUIRED_BLUEPRINTS and not session.get("user"):
            return redirect(url_for("auth.login"))

    register_pages(app)

    for blueprint, prefix in BLUEPRINTS:
        app.register_blueprint(blueprint, url_prefix=prefix)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)