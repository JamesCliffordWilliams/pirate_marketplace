# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
config/hot_ranking.py

Purpose:
Every setting for the Hot page in one place.

Notes:
- detail_view = a logged-in shopper opened a listing's image viewer or followed
  a "View in storefront" link. Cards shown in a grid are never counted.
- Each shopper counts once per listing: their strongest recent action.
- Storefront owners never count, and neither do accounts newer than
  MIN_ACCOUNT_AGE_HOURS (0 turns that off).
"""

# Points for each action (strongest one per shopper wins)
WEIGHTS = {
    "order": 6,
    "cart": 4,
    "wishlist": 3,
    "detail_view": 1,
}
INTEREST_KINDS = tuple(WEIGHTS)

# A listing needs at least one shopper who did one of these (views alone never count)
STRONG_KINDS = ("wishlist", "cart", "order")

MIN_ACCOUNT_AGE_HOURS = 24

# Hot Right Now
HOT_WINDOW_DAYS = 14
HOT_HALF_LIFE_HOURS = 96
HOT_MIN_ENGAGERS = 3
HOT_MIN_STRONG_ENGAGERS = 1
HOT_MAX_PER_STOREFRONT = 2
HOT_MIN_RESULTS = 4          # top up past the storefront limit to reach this many
HOT_LIMIT = 8

# Rising
RISING_WINDOW_DAYS = 7
RISING_HALF_LIFE_HOURS = 48
RISING_MIN_ENGAGERS = 2
RISING_MIN_STRONG_ENGAGERS = 1
RISING_MIN_RAW_SCORE = 2.5
RISING_RECENT_HOURS = 72     # needs at least one engagement this recent
RISING_REACH_DAYS = 30
RISING_REACH_SCALE = 20      # rising_score = raw / sqrt(1 + reach / scale)
RISING_MAX_PER_STOREFRONT = 1
RISING_LIMIT = 8

# Just Listed (only when Hot + Rising are nearly empty)
JUST_LISTED_SHOW_BELOW = 4
JUST_LISTED_MAX_PER_STOREFRONT = 2
JUST_LISTED_LIMIT = 8

# Tracking gives up after this long, so it can never hold up wishlist, cart or checkout
TRACKING_TIMEOUT_SECONDS = 2

# Caching
CACHE_SECONDS = 120          # ranked ids, per app process
API_MAX_AGE_SECONDS = 60     # Cache-Control on GET /api/hot
MAX_CANDIDATES = 100         # ranked ids kept per section before storefront limits
