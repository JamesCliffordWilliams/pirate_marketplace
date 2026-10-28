# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
config/hot_ranking.py

This file has the ranking settings for the Hot page.
A detail_view means a logged in shopper opened a product page. Cards in a grid don't count.
Each shopper only counts once per listing, using their strongest recent action.
Storefront owners don't count, and neither do accounts newer than MIN_ACCOUNT_AGE_HOURS.
Set it to 0 to turn that off.
"""

# Points for each action. Only a shopper's strongest action counts
WEIGHTS = {
    "order": 6,
    "cart": 4,
    "wishlist": 3,
    "detail_view": 1,
}

# A listing needs at least one shopper who did one of these. Views alone don't count
STRONG_KINDS = ("wishlist", "cart", "order")

MIN_ACCOUNT_AGE_HOURS = 24

# Hot Right Now
HOT_WINDOW_DAYS = 14
HOT_HALF_LIFE_HOURS = 96
HOT_MIN_ENGAGERS = 3
HOT_MAX_PER_STOREFRONT = 2
HOT_MIN_RESULTS = 4          # goes past the storefront limit if needed to show this many
HOT_LIMIT = 8

# Rising
RISING_WINDOW_DAYS = 7
RISING_HALF_LIFE_HOURS = 48
RISING_MIN_ENGAGERS = 2
RISING_MIN_RAW_SCORE = 2.5
RISING_RECENT_HOURS = 72     # needs at least one action this recent
RISING_REACH_DAYS = 30
RISING_REACH_SCALE = 20      # rising score = raw score / sqrt(1 + reach / scale)
RISING_MAX_PER_STOREFRONT = 1
RISING_LIMIT = 8
