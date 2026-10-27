# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - keeps database tests off production
#
# Purpose:
# Keeps database-backed tests from ever running against a remote database
# (the repo .env points at production RDS) unless someone explicitly opts in.
#
# Usage:
#     from tests.db_test_guard import require_local_db
#
#     @require_local_db
#     class MyDbTests(unittest.TestCase):
#         ...
#
# DB tests are skipped unless DB_HOST is localhost / 127.0.0.1 / ::1,
# or ALLOW_REMOTE_DB_TESTS=1 is set in the environment. They are also skipped
# (not failed) when the local database cannot be reached.

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

# Load .env the same way the app does, so the guard sees the same DB_HOST
# the code under test would connect to. Shell variables still win.
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}


def remote_db_allowed():
    return os.getenv("ALLOW_REMOTE_DB_TESTS") == "1"


def db_host_is_local():
    return (os.getenv("DB_HOST") or "").strip().lower() in LOCAL_DB_HOSTS


def local_db_skip_reason():
    """
    Returns None when DB tests may run, otherwise a human-readable skip reason.
    """
    if not db_host_is_local() and not remote_db_allowed():
        return (
            f"DB tests skipped: DB_HOST={os.getenv('DB_HOST')!r} is not local. "
            "Point DB_* at a local database or set ALLOW_REMOTE_DB_TESTS=1."
        )

    try:
        from db import get_connection
        conn = get_connection()
        conn.close()
    except Exception as e:
        return f"DB tests skipped: could not connect to the test database ({e})."

    return None


def require_local_db(cls):
    """
    Class decorator: skips the whole TestCase unless a local (or explicitly
    allowed) database is reachable.
    """
    reason = local_db_skip_reason()
    if reason:
        return unittest.skip(reason)(cls)
    return cls
