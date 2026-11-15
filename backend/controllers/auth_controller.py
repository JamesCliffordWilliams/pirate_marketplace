# By Ryan Grimes - Updated 3/19/2026
from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify
from services.auth_services import AuthService
from config.db import get_connection
from services.interest_service import track_interest  # Added by James Williams 10/26/26
from services.password_reset_service import PasswordResetService  # Added by Aniya Hopson 11/10/26
from utils.email_sender import send_password_reset_email  # Added by Aniya Hopson 11/10/26

auth_bp = Blueprint('auth', __name__)
service = AuthService()

LOGIN_MAX_ATTEMPTS = 5
LOGIN_TIMEOUT = 15

reset_service = PasswordResetService()  # Added by Aniya Hopson 11/10/26

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    user = request.form.get('username')
    pw = request.form.get('password')
    ip = request.remote_addr

    conn = get_connection()
    if conn is None:
        return render_template(
            'login.html',
            error="Pirate Market can't log you in right now. Try again in a minute.",
            username=user,
        )

    try:
        # Added by Billy Anders - Login Attempts
        if is_timed_out(conn, user, ip):
            return render_template(
                'login.html',
                error="Too many failed attempts. Try again in a few minutes.",
                username=user,
            ), 429

        success, role = service.validate_login(user, pw, conn)

        # Added by Billy Anders - Login Attempts
        if not success:
            add_failure(conn, user, ip)
            return render_template(
                'login.html',
                error="That username and password don't match.",
                username=user,
            )

        clear_failures(conn, user, ip)

        session['user'] = user
        session['role'] = role

        # Store user_id for storefront ownership checks - added by Day E 4/9/26
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = %s", (user,))
            row = cur.fetchone()
            cur.close()
            if row:
                session['user_id'] = row[0]
                session['cart'] = service.get_user_cart(conn, row[0])  # load saved cart
        except Exception as e:
            print(f"Error fetching user_id for session: {e}")

        # Redirect based on role - added by David Jackson 3/23/2026
        if role and role.lower() == 'admin':
            return redirect(url_for('admin.admin_dashboard'))
        return redirect(url_for('auth.listings'))

    finally:
        conn.close()


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        email = request.form.get('email')

        conn = get_connection()
        if conn is None:
            return render_template('signup.html',
                                   error="Pirate Market can't create accounts right now. Try again in a minute.",
                                   username=user, email=email)

        success, message = service.register_user(user, pw, email, conn)
        conn.close()

        if success:
            flash("Account created. Log in to start shopping.", "success")
            return redirect(url_for('auth.login'))
        # Updated by James Williams 10/26/26 - show the form again with the reason
        if message == "You Must Use a Hampton University Associated Email":
            error = "Use your Hampton University email (@hamptonu.edu or @my.hamptonu.edu)."
        else:
            error = "Your account wasn't created. That username or email may already be taken."
        return render_template('signup.html', error=error, username=user, email=email)

    return render_template('signup.html')


@auth_bp.route('/listings')
def listings():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    return render_template('homepage.html')


@auth_bp.route('/account')
def account():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    return render_template('account.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/cart')
def view_cart():
    if 'cart' not in session:
        session['cart'] = []
    # Added by James Williams 10/26/26 - gets the main photo for each item in one query
    photos = {}
    item_ids = [int(item['id']) for item in session['cart'] if str(item.get('id', '')).isdigit()]
    if item_ids:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT listing_id, image_url FROM listing_images WHERE is_primary = TRUE AND listing_id = ANY(%s);",
                (item_ids,)
            )
            photos = {str(listing_id): url for listing_id, url in cur.fetchall()}
            cur.close()
            conn.close()
        except Exception as e:
            print(f"DB Error loading bag photos: {e}")
    return render_template('cart.html', photos=photos)


@auth_bp.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        flash("Please login to add items to your bag.", "error")
        return redirect(url_for('auth.login'))

    item_id = request.form.get('item_id')
    item_name = request.form.get('item_name')
    price = request.form.get('price', 0)
    quantity = request.form.get('quantity', 1)
    size = request.form.get('size')

    # Validate listing availability before adding to cart
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT status, quantity_on_hand, is_made_to_order FROM listings WHERE id = %s",
            (item_id,)
        )
        listing = cur.fetchone()
        cur.close()
        conn.close()
        if not listing:
            return jsonify({"error": "This item is no longer available."}), 404
        listing_status, qty_on_hand, is_made_to_order = listing
        if listing_status == "SOLD_OUT" or (
                not is_made_to_order and qty_on_hand is not None and int(qty_on_hand) <= 0
        ):
            return jsonify({"error": f"{item_name} is sold out and cannot be added to your bag."}), 409
    except Exception as e:
        print(f"DB Error checking listing availability: {e}")

    # PERSIST TO DATABASE
    cart_saved = False  # Added by James Williams 10/26/26
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
                    INSERT INTO cart_items (user_id, item_id, item_name, price, quantity, size)
                    VALUES (%s, %s, %s, %s, %s, %s)
        """, (session['user_id'], item_id, item_name, price, quantity, size))
        conn.commit()
        cart_saved = True  # Added by James Williams 10/26/26
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB Error adding to cart: {e}")

    # Added by James Williams 10/26/26 - counts this for the Hot page, but only after the cart row is saved
    if cart_saved:
        track_interest(item_id, session['user_id'], "cart")

    # Update session for immediate UI feedback
    if 'cart' not in session:
        session['cart'] = []

    cart_item = {'id': item_id, 'name': item_name, 'price': float(price), 'quantity': int(quantity), 'size': size}
    temp_cart = session['cart']
    temp_cart.append(cart_item)
    session['cart'] = temp_cart
    session.modified = True

    flash(f"Added {item_name} to your bag!", "success")
    return redirect(url_for('auth.view_cart'))


@auth_bp.route('/remove_from_cart/<int:index>', methods=['POST'])
def remove_from_cart(index):
    if 'cart' in session and 'user_id' in session:
        temp_cart = session['cart']
        if 0 <= index < len(temp_cart):
            removed_item = temp_cart.pop(index)

            # REMOVE FROM DATABASE
            try:
                conn = get_connection()
                cur = conn.cursor()
                # We delete one instance of this item for this user
                cur.execute("""
                            DELETE
                            FROM cart_items
                            WHERE id = (SELECT id
                                        FROM cart_items
                                        WHERE user_id = %s
                                          AND item_name = %s
                                          AND size = %s
                                LIMIT 1
                                )
                """, (session['user_id'], removed_item['name'], removed_item['size']))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"DB Error removing item: {e}")

            session['cart'] = temp_cart
            session.modified = True
            flash(f"Removed {removed_item['name']} from bag.", "info")
    return redirect(url_for('auth.view_cart'))


# Added by James Williams 10/26/26 - changes an item's quantity in the bag, from 1 up to what's in stock
@auth_bp.route('/update_cart/<int:index>', methods=['POST'])
def update_cart(index):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    cart = session.get('cart') or []
    try:
        quantity = int(request.form.get('quantity', ''))
    except ValueError:
        return redirect(url_for('auth.view_cart'))
    if not 0 <= index < len(cart) or quantity < 1:
        return redirect(url_for('auth.view_cart'))

    item = cart[index]
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT quantity_on_hand, is_made_to_order FROM listings WHERE id = %s", (item['id'],))
        row = cur.fetchone()
        if row and not row[1] and row[0] is not None:
            quantity = min(quantity, max(int(row[0]), 1))
        quantity = min(quantity, 99)
        # This updates the same row that remove_from_cart would delete
        cur.execute("""
                    UPDATE cart_items
                    SET quantity = %s
                    WHERE id = (SELECT id
                                FROM cart_items
                                WHERE user_id = %s
                                  AND item_name = %s
                                  AND size = %s
                        LIMIT 1
                        )
        """, (quantity, session['user_id'], item['name'], item['size']))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB Error updating bag quantity: {e}")
        return redirect(url_for('auth.view_cart'))

    item['quantity'] = quantity
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('auth.view_cart'))


# Added by Day E 4/9/26 - returns current session user info for frontend auth checks
@auth_bp.route('/api/auth/me')
def get_current_session_user():
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, role FROM users WHERE username = %s", (session['user'],))
        user = cur.fetchone()
        conn.close()

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "id": user[0],
            "username": user[1],
            "role": user[2]
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route('/cart/json')
def get_cart_json():
    return jsonify(session.get('cart', []))


@auth_bp.route('/debug/session')
def debug_session():
    return jsonify(dict(session))


# Admin login route - added by David Jackson 4/19/26
@auth_bp.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')

        # temporary hardcoded admin login for testing
        if user == "admin" and pw == "admin123":
            session['user'] = user
            session['role'] = 'admin'
            return redirect(url_for('admin.admin_dashboard'))

        return "Invalid Admin Credentials. <a href='/auth/admin-login'>Try again</a>"

    return render_template('admin_login.html')

# Added by Billy Anders - Login Limit
def is_timed_out(conn, username, ip):
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM login_attempts
        WHERE username = %s AND ip = %s
          AND attempted_at > NOW() - (%s * INTERVAL '1 minute')
    """, (username, ip, LOGIN_TIMEOUT))
    count = cur.fetchone()[0]
    cur.close()
    return count >= LOGIN_MAX_ATTEMPTS

# Added by Billy Anders - Login Limit
def add_failure(conn, username, ip):
    cur = conn.cursor()
    cur.execute("INSERT INTO login_attempts (username, ip) VALUES (%s, %s)", (username, ip))
    conn.commit()
    cur.close()

# Added by Billy Anders - Login Limit
def clear_failures(conn, username, ip):
    cur = conn.cursor()
    cur.execute("DELETE FROM login_attempts WHERE username = %s AND ip = %s", (username, ip))
    conn.commit()
    cur.close()

# Forgot Password - Added by Aniya Hopson 11/14/26 

# Same message whether or not the email has an account, so no one can use this page
# to find out which emails are signed up
RESET_SENT_MESSAGE = ("If that email belongs to a Pirate Market account, we sent a link to reset "
                      "your password. The link expires in 30 minutes.")
RESET_BAD_LINK_MESSAGE = "That reset link is invalid or has expired. Request a new one below."
MIN_PASSWORD_LENGTH = 8

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        if not email:
            return render_template('forgot_password.html', error="Enter the email you used to sign up.")

        conn = get_connection()
        if conn is None:
            return render_template('forgot_password.html', email=email,
                                   error="Pirate Market can't send reset emails right now. Try again in a minute.")

        result = reset_service.create_reset_token(email, conn)
        conn.close()

        if result:
            username, stored_email, raw_token = result
            reset_link = url_for('auth.reset_password', token=raw_token, _external=True)
            send_password_reset_email(stored_email, username, reset_link)

        flash(RESET_SENT_MESSAGE)
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # GET: just check the link and show the form. Opening the link does not use it up.
    if request.method == 'GET':
        conn = get_connection()
        if conn is None:
            return render_template('reset_password.html', token=token,
                                   error="Pirate Market can't reset passwords right now. Try again in a minute.")
        valid = reset_service.is_token_valid(token, conn)
        conn.close()
        if not valid:
            flash(RESET_BAD_LINK_MESSAGE)
            return redirect(url_for('auth.forgot_password'))
        return render_template('reset_password.html', token=token)

    # POST: check the new password, then use up the link and save it
    new_pw = request.form.get('password') or ''
    confirm_pw = request.form.get('confirm_password') or ''

    if len(new_pw) < MIN_PASSWORD_LENGTH:
        return render_template('reset_password.html', token=token,
                               error=f"Your new password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if new_pw != confirm_pw:
        return render_template('reset_password.html', token=token, error="The two passwords don't match.")

    conn = get_connection()
    if conn is None:
        return render_template('reset_password.html', token=token,
                               error="Pirate Market can't reset passwords right now. Try again in a minute.")
    success = reset_service.reset_password(token, new_pw, conn)
    conn.close()

    if not success:
        flash(RESET_BAD_LINK_MESSAGE)
        return redirect(url_for('auth.forgot_password'))

    session.clear()  # logs out any session that was open in this browser
    flash("Your password was updated. Log in with your new password.")
    return redirect(url_for('auth.login'))