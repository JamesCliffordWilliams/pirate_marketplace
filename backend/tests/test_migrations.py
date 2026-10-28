# Created by James Williams - 10/26/26 - the three migrations are safe to run more than once

import os
import sys
import unittest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path += [os.path.dirname(BACKEND_ROOT), BACKEND_ROOT]

from tests.db_test_guard import require_local_db
from tests.hot_test_db import ThrowawaySchema
from migrations.add_product_categories import apply_product_categories
from migrations.add_listing_interest import apply_listing_interest
from migrations.add_listing_create_requests import apply_listing_create_requests


@require_local_db
class TestMigrations(unittest.TestCase):

    def test_each_migration_runs_twice(self):
        # create() runs init_db, which already runs all three once, so this is the second run
        db = ThrowawaySchema(prefix="test_migrations").create()
        self.addCleanup(db.drop)
        conn = db.connect()
        cur = conn.cursor()
        apply_product_categories(cur)
        self.assertFalse(apply_listing_interest(cur)["table_created"])
        self.assertFalse(apply_listing_create_requests(cur)["table_created"])
        conn.commit()
        conn.close()
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM product_categories WHERE parent_id IS NULL;"), 12)


if __name__ == "__main__":
    unittest.main()
