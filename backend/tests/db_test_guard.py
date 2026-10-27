# The Vault Campus Marketplace
# Created by James Williams - 10/26/26 - keeps database tests off production
#
# This skips database tests unless DB_HOST is a local database, since the
# repo .env points at the real production database.
# To run them on a remote database anyway, set ALLOW_REMOTE_DB_TESTS=1.
# They also skip if the local database can't be reached.
#
# How to use it:
#     from tests.db_test_guard import require_local_db
#
#     @require_local_db
#     class MyDbTests(unittest.TestCase):
#         ...

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.append(path)

# This loads .env like the app does so we check the same DB_HOST.
# Variables set in the shell still win.
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}


def require_local_db(cls):
    """Skips the whole test class unless we can reach a local or allowed database."""
    host = os.getenv("DB_HOST")
    if (host or "").strip().lower() not in LOCAL_DB_HOSTS and os.getenv("ALLOW_REMOTE_DB_TESTS") != "1":
        return unittest.skip(
            f"DB tests skipped: DB_HOST={host!r} is not local. "
            "Point DB_* at a local database or set ALLOW_REMOTE_DB_TESTS=1."
        )(cls)

    try:
        from db import get_connection
        get_connection().close()
    except Exception as e:
        return unittest.skip(f"DB tests skipped: could not connect to the test database ({e}).")(cls)

    return cls
