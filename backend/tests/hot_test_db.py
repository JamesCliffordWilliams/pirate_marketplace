# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - throwaway database schema for the Hot tests
#
# Builds the full app schema (init_db.create_vault_tables) inside a new
# Postgres schema and points every new connection at it through PGOPTIONS,
# so the app code runs unchanged and the real tables are never touched.
# Only use from classes decorated with @require_local_db.

import contextlib
import io
import os
import uuid


class ThrowawaySchema:

    def __init__(self, prefix="test_hot"):
        self.name = f"{prefix}_{uuid.uuid4().hex[:10]}"
        self._old_pgoptions = None

    def create(self, init_tables=True):
        from db import get_connection
        conn = get_connection()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"CREATE SCHEMA {self.name};")
        cur.close()
        conn.close()

        self._old_pgoptions = os.environ.get("PGOPTIONS")
        os.environ["PGOPTIONS"] = f"-c search_path={self.name}"

        if init_tables:
            from init_db import create_vault_tables
            with contextlib.redirect_stdout(io.StringIO()) as out:
                create_vault_tables()
            if "SCHEMA ERROR" in out.getvalue():
                raise RuntimeError(out.getvalue())
        return self

    def drop(self):
        if self._old_pgoptions is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = self._old_pgoptions
        from db import get_connection
        conn = get_connection()
        conn.autocommit = True
        cur = conn.cursor()
        # Drops only the throwaway schema this helper created
        cur.execute(f"DROP SCHEMA IF EXISTS {self.name} CASCADE;")
        cur.close()
        conn.close()

    # ---------- queries ----------

    def connect(self):
        from db import get_connection
        return get_connection()

    def execute(self, sql, params=None):
        conn = self.connect()
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall() if cur.description else None
        conn.commit()
        cur.close()
        conn.close()
        return rows

    def scalar(self, sql, params=None):
        return self.execute(sql, params)[0][0]

    # ---------- seed helpers ----------

    def add_user(self, name=None, age_hours=48):
        name = name or f"u_{uuid.uuid4().hex[:8]}"
        return self.scalar("""
            INSERT INTO users (username, password, email, created_at)
            VALUES (%s, 'x', %s, LOCALTIMESTAMP - make_interval(hours => %s))
            RETURNING id;
        """, (name, f"{name}@example.com", age_hours))

    def add_storefront(self, owner_id=None, name="Shop", is_active=True):
        owner_id = owner_id or self.add_user()
        return self.scalar(
            "INSERT INTO storefronts (owner_id, brand_name, is_active) VALUES (%s, %s, %s) RETURNING id;",
            (owner_id, name, is_active),
        )

    def owner_of(self, storefront_id):
        return self.scalar("SELECT owner_id FROM storefronts WHERE id = %s;", (storefront_id,))

    def add_listing(self, storefront_id, title="Item", status="ACTIVE", quantity=5,
                    made_to_order=False, created_hours_ago=1):
        listing_id = self.scalar("""
            INSERT INTO listings (storefront_id, title, price, fulfillment_type, quantity_on_hand,
                                  status, is_made_to_order, created_at)
            VALUES (%s, %s, 10, 'IN_STOCK', %s, %s, %s, LOCALTIMESTAMP - make_interval(hours => %s))
            RETURNING id;
        """, (storefront_id, title, quantity, status, made_to_order, created_hours_ago))
        self.execute(
            "INSERT INTO listing_sizes (listing_id, size, quantity) VALUES (%s, 'M', %s);",
            (listing_id, quantity or 0),
        )
        return listing_id

    def add_interest(self, listing_id, user_id, kind, hours_ago=0):
        self.execute("""
            INSERT INTO listing_interest (listing_id, user_id, kind, day, created_at)
            VALUES (%s, %s, %s,
                    (LOCALTIMESTAMP - make_interval(hours => %s))::date,
                    LOCALTIMESTAMP - make_interval(hours => %s));
        """, (listing_id, user_id, kind, hours_ago, hours_ago))

    def interest_rows(self, listing_id=None):
        if listing_id is None:
            return self.execute("SELECT listing_id, user_id, kind FROM listing_interest ORDER BY id;")
        return self.execute(
            "SELECT listing_id, user_id, kind FROM listing_interest WHERE listing_id = %s ORDER BY id;",
            (listing_id,),
        )
