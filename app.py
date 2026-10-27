import os
from datetime import timedelta

from flask import Flask, render_template, redirect, url_for, session

# Billy: Rewrite
from controllers.admin_controller import admin_bp
from controllers.auth_controller import auth_bp
from controllers.category_controller import category_bp, category_pages_bp # James
from controllers.checkout_controller import checkout_bp
<<<<<<< HEAD
from controllers.category_controller import category_bp, category_pages_bp  # Added by James Williams 10/26/26
from controllers.hot_controller import hot_bp, hot_pages_bp  # Added by James Williams 10/26/26
from controllers.order_controllers import orders_bp  # Added by Aniya Hopson 10/27/26
from init_db import create_vault_tables
=======
from controllers.hot_controller import hot_bp, hot_pages_bp # James
from controllers.listing_controller import listing_bp
from controllers.message_controller import message_bp
from controllers.purchase_controller import purchase_bp
from controllers.return_controller import returns_bp
from controllers.storefront_controller import storefront_bp, storefront_pages_bp
from controllers.wallet_controller import wallet_bp # Billy
from controllers.wishlist_controller import wishlist_bp
>>>>>>> b0edc85bfd655d6e0a306eaa27d3551f56346337

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
    app.secret_key = os.getenv('SECRET_KEY') # James: remove exposed secret key for security reasons. Use environment variable instead.

    if not app.secret_key:
        raise RuntimeError("SECRET_KEY is not set.")

    # Billy: Session Timeout
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=SESSION_LIFETIME_MINUTES)

    # Billy: Session Timeout
    @app.before_request
    def make_session_permanent():
        if session.get("user"):
            session.permanent = True

    register_pages(app)

    for blueprint, prefix in BLUEPRINTS:
        app.register_blueprint(blueprint, url_prefix=prefix)

<<<<<<< HEAD
    # Route to the "Create Listing" form - Updated 3/24/2026
    # Aniya rerouted the user to login if they are not a user - Updated 9/28/26
    @app.route('/create-listing')
    def create_listing():
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return render_template('create_listing.html')

    #Route to the Cart screen - Updated 3/22/2026
    # Aniya rerouted the user to login if they are not a user - Updated 9/28/26
    @app.route('/cart')
    def cart():
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return render_template('cart.html')

    #Route to the Checkout - Updated 4/22/2026
    # Aniya rerouted the user to login if they are not a user - Updated 9/28/26
    @app.route('/checkout')
    def checkout():
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return render_template('checkout.html')

    # Route to the Order Confirmation page - Added 4/22/2026
    # Aniya rerouted the user to login if they are not a user - Updated 9/28/26
    @app.route('/order-confirmation')
    def order_confirmation():
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return render_template('order_confirmation.html')
    
    # Route to My Storefront dashboard page - Updated 4/9/2026
    @app.route('/my-storefront')
    def my_storefront():
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return render_template('my_storefront.html')

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(listing_bp)
    app.register_blueprint(storefront_bp)
    app.register_blueprint(storefront_pages_bp)  # Updated by Day E 3/22/26
    app.register_blueprint(purchase_bp)
    app.register_blueprint(wishlist_bp)
    app.register_blueprint(admin_bp) # Updated 3/19/2026 by Ryan Grimes
    app.register_blueprint(returns_bp)
    app.register_blueprint(checkout_bp, url_prefix='/api')
    app.register_blueprint(category_bp)         # Added by James Williams 10/26/26
    app.register_blueprint(category_pages_bp)   # Added by James Williams 10/26/26
    app.register_blueprint(hot_bp)              # Added by James Williams 10/26/26
    app.register_blueprint(hot_pages_bp)        # Added by James Williams 10/26/26
    app.register_blueprint(orders_bp, url_prefix='/api')  # Added by Aniya Hopson 10/27/26
    
=======
>>>>>>> b0edc85bfd655d6e0a306eaa27d3551f56346337
    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)