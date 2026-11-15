# Pirate Market - Forgot Password feature
# Added by Aniya Hopson 11/10/26
# Creates, checks, and uses the one-time links that let a user reset their password

import hashlib
import secrets
from utils.auth_utils import hash_password

TOKEN_LIFETIME_MINUTES = 15
RESEND_WAIT_MINUTES = 2

class PasswordResetService:

    def _hash_token(self, raw_token):
        # We only ever store the SHA-256 hash of the token, never the token itself
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def create_reset_token(self, email, db_conn):
        """Returns (username, email, raw_token) if the email has an account, otherwise None."""
        try:
            cur = db_conn.cursor()
            cur.execute("SELECT id, username, email FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
            user = cur.fetchone()
            if not user:
                cur.close()
                return None

            user_id, username, stored_email = user
            
            # Limit: if this user already got a link in the last 2 minutes, don't send another.
            # Stops someone from flooding a student's inbox or using up our SES quota.
            cur.execute("""
                SELECT 1 FROM password_reset_tokens
                WHERE user_id = %s AND created_at > NOW() - make_interval(mins => %s)
            """, (user_id, RESEND_WAIT_MINUTES))
            if cur.fetchone():
                cur.close()
                return None

            # Clean up expired links from all users so the table doesn't collect old rows
            cur.execute("DELETE FROM password_reset_tokens WHERE expires_at < NOW()")

            # Only the newest link should work, so remove any older ones for this user
            cur.execute("DELETE FROM password_reset_tokens WHERE user_id = %s", (user_id,))

            raw_token = secrets.token_urlsafe(32)
            cur.execute("""
                INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
                VALUES (%s, %s, NOW() + make_interval(mins => %s))
            """, (user_id, self._hash_token(raw_token), TOKEN_LIFETIME_MINUTES))

            db_conn.commit()
            cur.close()
            return username, stored_email, raw_token
        except Exception as e:
            print(f"Password Reset Error (create): {e}")
            db_conn.rollback()
            return None

    def is_token_valid(self, raw_token, db_conn):
        """True if the link exists and has not expired. Does NOT use up the link."""
        try:
            cur = db_conn.cursor()
            cur.execute("""
                SELECT 1 FROM password_reset_tokens
                WHERE token_hash = %s AND expires_at > NOW()
            """, (self._hash_token(raw_token),))
            row = cur.fetchone()
            cur.close()
            return row is not None
        except Exception as e:
            print(f"Password Reset Error (check): {e}")
            return False

    def reset_password(self, raw_token, new_password, db_conn):
        """Uses up the link and saves the new password. Returns True if it worked."""
        try:
            cur = db_conn.cursor()
            # DELETE ... RETURNING checks the link and uses it up in one step,
            # so the same link can't be used twice
            cur.execute("""
                DELETE FROM password_reset_tokens
                WHERE token_hash = %s AND expires_at > NOW()
                RETURNING user_id
            """, (self._hash_token(raw_token),))
            row = cur.fetchone()
            if not row:
                db_conn.rollback()
                cur.close()
                return False

            user_id = row[0]
            cur.execute("UPDATE users SET password = %s WHERE id = %s", (hash_password(new_password), user_id))
            db_conn.commit()
            cur.close()
            return True
        except Exception as e:
            print(f"Password Reset Error (reset): {e}")
            db_conn.rollback()
            return False