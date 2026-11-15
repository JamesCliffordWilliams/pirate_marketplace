"""
init_db.py

Purpose:
This file initializes the PostgreSQL database schema for Pirate Market.
It creates all required database tables if they do not already exist.

Run this file manually when:
- Setting up the project for the first time
- Deploying to a new environment
- Pulling in a change that adds tables or columns
"""

# Pirate Market Campus Marketplace
# CSC 405 Sp 26'
import os
import sys

import psycopg2
from dotenv import load_dotenv

from migrations.add_product_categories import apply_product_categories
from migrations.add_listing_interest import apply_listing_interest
from migrations.add_listing_create_requests import apply_listing_create_requests

load_dotenv()

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_users(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            role VARCHAR(10) DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_storefronts(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS storefronts (
            id SERIAL PRIMARY KEY,
            owner_id INTEGER NOT NULL UNIQUE,
            brand_name VARCHAR(80) NOT NULL,
            bio TEXT,
            logo_url TEXT,
            banner_url TEXT,
            contact_info TEXT,
            preview_image_1 TEXT,
            preview_image_2 TEXT,
            preview_image_3 TEXT,
            preview_image_4 TEXT,
            categories TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_storefront_owner
                FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    for column, definition in [
        ("contact_info", "TEXT"),
        ("preview_image_1", "TEXT"),
        ("preview_image_2", "TEXT"),
        ("preview_image_3", "TEXT"),
        ("preview_image_4", "TEXT"),
        ("categories", "TEXT"),
        ("is_active", "BOOLEAN DEFAULT TRUE"),
    ]:
        cur.execute(f"ALTER TABLE storefronts ADD COLUMN IF NOT EXISTS {column} {definition};")

    cur.execute("UPDATE storefronts SET is_active = TRUE WHERE is_active IS NULL;")

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_listings(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id SERIAL PRIMARY KEY,
            storefront_id INTEGER NOT NULL,

            title VARCHAR(120) NOT NULL,
            description TEXT,
            price NUMERIC(10,2) NOT NULL CHECK (price >= 0),

            fulfillment_type VARCHAR(20) NOT NULL
                CHECK (fulfillment_type IN ('IN_STOCK', 'PREORDER')),

            quantity_on_hand INTEGER CHECK (quantity_on_hand >= 0),
            sizes_available TEXT,

            status VARCHAR(20) DEFAULT 'ACTIVE'
                CHECK (status IN ('ACTIVE', 'INACTIVE', 'SOLD_OUT', 'DELETED')),

            storefront_restore_status VARCHAR(20),
            deleted_restore_status VARCHAR(20),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_listing_storefront
                FOREIGN KEY(storefront_id) REFERENCES storefronts(id) ON DELETE CASCADE
        );
    """)
    cur.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS storefront_restore_status VARCHAR(20);")
    cur.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS deleted_restore_status VARCHAR(20);")
    cur.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS is_made_to_order BOOLEAN DEFAULT FALSE;")
    cur.execute("UPDATE listings SET is_made_to_order = FALSE WHERE is_made_to_order IS NULL;")
    # Adds a deletion timestamp for soft deletion of listings - Miles Walker 11/11/2026
    cur.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;")

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_listing_images(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS listing_images (
            id SERIAL PRIMARY KEY,
            listing_id INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            is_primary BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_image_listing
                FOREIGN KEY(listing_id) REFERENCES listings(id) ON DELETE CASCADE
        );
    """)

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_listing_sizes(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS listing_sizes (
            id SERIAL PRIMARY KEY,
            listing_id INTEGER NOT NULL,
            size VARCHAR(20) NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity >= 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_size_listing
                FOREIGN KEY(listing_id) REFERENCES listings(id) ON DELETE CASCADE,
            CONSTRAINT unique_listing_size UNIQUE (listing_id, size)
        );
    """)

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_purchases(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            listing_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            purchase_price NUMERIC(10,2) NOT NULL CHECK (purchase_price >= 0),
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_purchase_user
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT fk_purchase_listing
                FOREIGN KEY(listing_id) REFERENCES listings(id) ON DELETE CASCADE
        );
    """)

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_wishlist(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            listing_id INTEGER NOT NULL,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_wishlist_user
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT fk_wishlist_listing
                FOREIGN KEY(listing_id) REFERENCES listings(id) ON DELETE CASCADE,
            CONSTRAINT unique_user_listing_wishlist UNIQUE (user_id, listing_id)
        );
    """)

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_returns(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS returns (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            order_number VARCHAR(120) NOT NULL,
            reason TEXT NOT NULL,
            has_damage BOOLEAN NOT NULL,
            damage_image_url TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'reviewed', 'resolved')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT FALSE,

            CONSTRAINT fk_return_user
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    cur.execute("ALTER TABLE returns ADD COLUMN IF NOT EXISTS damage_image_url TEXT;")
    cur.execute("ALTER TABLE returns ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
    cur.execute("ALTER TABLE returns ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;")

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_cart_items(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            item_id INTEGER,
            item_name VARCHAR(255) NOT NULL,
            price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
            quantity INTEGER NOT NULL DEFAULT 1,
            size VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_cart_user
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

# Updated by Aniya Hopson 10/26/26
# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_orders(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            confirmation_number VARCHAR(50) UNIQUE NOT NULL,
            buyer_first_name VARCHAR(100) NOT NULL,
            buyer_last_name VARCHAR(100) NOT NULL,
            buyer_email VARCHAR(255) NOT NULL,
            buyer_contact VARCHAR(100) NOT NULL,
            buyer_meeting_location TEXT NOT NULL,
            total_amount NUMERIC(10,2) NOT NULL,
            order_status VARCHAR(20) DEFAULT 'SUBMITTED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_order_user
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days');")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;")

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_order_items(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL,
            listing_id INTEGER,
            item_name VARCHAR(255) NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            price_at_purchase NUMERIC(10,2) NOT NULL,
            selected_size VARCHAR(50),

            CONSTRAINT fk_order_item_order
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        );
    """)
    cur.execute("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;")


# Added by Billy Anders
def create_wallets(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE,
            balance NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (balance >= 0),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_wallet_user
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

# Added by Billy Anders
def create_wallet_transactions(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            type VARCHAR(10) NOT NULL
                CHECK (type IN ('DEPOSIT', 'WITHDRAW', 'PURCHASE')),
            amount NUMERIC(10,2) NOT NULL CHECK (amount > 0),
            balance_after NUMERIC(10,2) NOT NULL,
            description TEXT,
            order_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_wallet_tx_user
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT fk_wallet_tx_order
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE SET NULL
        );
    """)
    cur.execute("ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS stripe_session_id TEXT UNIQUE;")

# Added by Billy Anders
def create_login_attempts(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) NOT NULL,
            ip VARCHAR(45) NOT NULL,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_pair ON login_attempts(username, ip, attempted_at);")

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_messages(cur):
    # Added by Miles Walker 10/25/26
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            listing_id INTEGER, 
            body TEXT NOT NULL CHECK (char_length(body) >= 1 AND char_length(body) <= 2000),
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_message_sender
                FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT fk_message_receiver
                FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT fk_msg_listing
                FOREIGN KEY(listing_id) REFERENCES listings(id) ON DELETE SET NULL,
            CONSTRAINT chk_not_self CHECK (sender_id <> receiver_id)
        );
    """)

    # Aniya Hopson 10/27/26 - remove the unused "content" column from older databases
    cur.execute("ALTER TABLE messages DROP COLUMN IF EXISTS content;")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiver_id, is_read);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_pair ON messages(sender_id, receiver_id, created_at);")

# Added by James Williams 11/14/26 - one review per buyer per listing
def create_reviews(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
            rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
            body TEXT CHECK (char_length(body) <= 2000),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_user_listing_review UNIQUE (user_id, listing_id)
        );
    """)

#Updated by Aniya Hopson - Forgot Password feature 11/10/26
def create_password_reset_tokens(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token_hash CHAR(64) UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_reset_user
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_reset_user ON password_reset_tokens(user_id);")

SCHEMA_STEPS = [
    create_users,
    create_storefronts,
    create_listings,
    apply_product_categories,         # James Williams: Creates product_categories and adds listings.category_id
    apply_listing_create_requests,    # James Williams: so a retried create can't make two listings
    create_listing_images,
    create_listing_sizes,
    create_purchases,
    create_wishlist,
    create_returns,
    create_cart_items,
    create_orders,
    create_order_items,
    create_wallets,
    create_wallet_transactions,
    create_login_attempts,
    create_messages,
    apply_listing_interest,           # James Williams: the table that tracks shopper activity for the Hot page
    create_reviews,                   # James Williams: product reviews
    create_password_reset_tokens      # Aniya Hopson : one-time link for the Forgot Password
]

# Updated by Billy Anders - split create_wallet_tables into individual functions.
def create_vault_tables():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for step in SCHEMA_STEPS:
                step(cur)

            conn.commit()

            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cur.fetchall()]

        print(f"DATABASE INITIALIZED: {len(tables)} tables are ready:")
        for name in tables:
            print(f"  - {name}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Updated by Billy Anders
if __name__ == "__main__":
    try:
        create_vault_tables()
    except Exception as e:
        print(f"SCHEMA ERROR: {e}", file=sys.stderr)
        sys.exit(1)