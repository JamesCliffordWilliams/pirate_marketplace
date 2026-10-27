# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
services/hot_service.py

This code is responsible for building the Hot page, which has Hot Right Now and Rising.
The database gives us each shopper's latest actions, and the scoring is plain Python so we can test it without a database.
The ranking is saved for a bit, but the card data is loaded fresh every time so sold out or hidden listings don't show up.
The ranking settings are in config/hot_ranking.py.
"""

import math
import time

from config import hot_ranking as cfg
from models.interest_model import get_engagement_events, get_storefront_reach
from models.listing_model import browse_public_listings

CACHE_SECONDS = 120     # how long each app process keeps the ranking
MAX_CANDIDATES = 100    # ranked listings we keep per section before the storefront limits


# ________________________________________________________
# SCORING (no database needed)
# ________________________________________________________

def decay(age_hours, half_life_hours):
    """Lowers the points over time. It's 1.0 now, 0.5 after one half life and 0.25 after two."""
    return 0.5 ** (max(age_hours, 0) / half_life_hours)


def score_listings(events, window_hours, half_life_hours):
    """Groups the actions by listing and shopper and adds up each listing's score."""
    listings = {}
    for e in events:
        if e["age_hours"] > window_hours:
            continue
        listing = listings.setdefault(e["listing_id"], {"storefront_id": e["storefront_id"], "shoppers": {}})
        listing["shoppers"].setdefault(e["user_id"], []).append(e)

    scored = {}
    for listing_id, listing in listings.items():
        points = []
        strong_engagers = 0
        ages = []
        for shopper_events in listing["shoppers"].values():
            # Each shopper only counts once, using their strongest action
            points.append(max(cfg.WEIGHTS[e["kind"]] * decay(e["age_hours"], half_life_hours)
                              for e in shopper_events))
            if any(e["kind"] in cfg.STRONG_KINDS for e in shopper_events):
                strong_engagers += 1
            ages += [e["age_hours"] for e in shopper_events]

        scored[listing_id] = {
            "listing_id": listing_id,
            "storefront_id": listing["storefront_id"],
            "raw_score": sum(points),
            "engagers": len(listing["shoppers"]),
            "strong_engagers": strong_engagers,
            "latest_age_hours": min(ages),
        }
    return scored


def rank_key(candidate):
    # Sorts by highest score, then most recent action, then newest listing
    return (-candidate["score"], candidate["latest_age_hours"], -candidate["listing_id"])


def rank_hot(events):
    """Returns every listing that qualifies for Hot, best first."""
    scored = score_listings(events, cfg.HOT_WINDOW_DAYS * 24, cfg.HOT_HALF_LIFE_HOURS)
    ranked = []
    for s in scored.values():
        if s["engagers"] >= cfg.HOT_MIN_ENGAGERS and s["strong_engagers"] >= 1:
            ranked.append({**s, "score": s["raw_score"]})
    return sorted(ranked, key=rank_key)


def rank_rising(events, reach_by_storefront):
    """
    Returns every listing that qualifies for Rising, best first.
    The minimums use the raw score. The boost for smaller storefronts only changes the order.
    """
    scored = score_listings(events, cfg.RISING_WINDOW_DAYS * 24, cfg.RISING_HALF_LIFE_HOURS)
    ranked = []
    for s in scored.values():
        if (s["engagers"] >= cfg.RISING_MIN_ENGAGERS
                and s["strong_engagers"] >= 1
                and s["raw_score"] >= cfg.RISING_MIN_RAW_SCORE
                and s["latest_age_hours"] <= cfg.RISING_RECENT_HOURS):
            reach = reach_by_storefront.get(s["storefront_id"], 0)
            score = s["raw_score"] / math.sqrt(1 + reach / cfg.RISING_REACH_SCALE)
            ranked.append({**s, "score": score})
    return sorted(ranked, key=rank_key)


# ________________________________________________________
# PICKING THE SECTIONS
# ________________________________________________________

def pick_per_storefront(candidates, max_per_storefront, limit, exclude_ids=()):
    """Picks listings in order, skipping any storefront that already has its max."""
    picked = []
    per_store = {}
    for c in candidates:
        if len(picked) >= limit:
            break
        store = c["storefront_id"]
        if c["listing_id"] in exclude_ids or per_store.get(store, 0) >= max_per_storefront:
            continue
        per_store[store] = per_store.get(store, 0) + 1
        picked.append(c["listing_id"])
    return picked


def select_hot(candidates):
    """Picks up to 8 listings with at most 2 per storefront. If that gives less than 4, it adds more by score."""
    picked = pick_per_storefront(candidates, cfg.HOT_MAX_PER_STOREFRONT, cfg.HOT_LIMIT)
    if len(picked) < cfg.HOT_MIN_RESULTS:
        chosen = set(picked)
        for c in candidates:
            if len(chosen) >= cfg.HOT_MIN_RESULTS:
                break
            chosen.add(c["listing_id"])
        # This keeps them in score order
        picked = [c["listing_id"] for c in candidates if c["listing_id"] in chosen]
    return picked


def select_sections(hot_candidates, rising_candidates, available_ids):
    """
    Picks the Hot listings first, then Rising, which skips anything already in Hot.
    available_ids are the listings that are still visible and in stock.
    """
    hot_candidates = [c for c in hot_candidates if c["listing_id"] in available_ids]
    rising_candidates = [c for c in rising_candidates if c["listing_id"] in available_ids]
    hot = select_hot(hot_candidates)
    rising = pick_per_storefront(rising_candidates, cfg.RISING_MAX_PER_STOREFRONT, cfg.RISING_LIMIT,
                                 exclude_ids=hot)
    return {"hot": hot, "rising": rising}


# ________________________________________________________
# HOT PAGE
# ________________________________________________________

# Each app process keeps its own copy of the ranking. It only has ids and scores, not card data.
_cached_ranking = None
_cache_expires_at = 0.0


def clear_ranking_cache():
    global _cached_ranking, _cache_expires_at
    _cached_ranking = None
    _cache_expires_at = 0.0


def get_hot_page_data():
    """Returns the Hot and Rising cards in the same format as the category cards."""
    global _cached_ranking, _cache_expires_at

    ranked = _cached_ranking
    if ranked is None or time.monotonic() >= _cache_expires_at:
        # If any of this fails, nothing gets saved
        events = get_engagement_events(max(cfg.HOT_WINDOW_DAYS, cfg.RISING_WINDOW_DAYS) * 24)
        reach = get_storefront_reach({e["storefront_id"] for e in events}, cfg.RISING_REACH_DAYS)
        ranked = {
            "hot": rank_hot(events)[:MAX_CANDIDATES],
            "rising": rank_rising(events, reach)[:MAX_CANDIDATES],
        }
        _cached_ranking = ranked
        _cache_expires_at = time.monotonic() + CACHE_SECONDS

    # This loads fresh card data for the ranked listings that are visible and in stock right now
    candidate_ids = list(dict.fromkeys(c["listing_id"] for c in ranked["hot"] + ranked["rising"]))
    cards = {}
    if candidate_ids:
        listings, _ = browse_public_listings(listing_ids=candidate_ids, available_only=True,
                                             limit=len(candidate_ids))
        cards = {listing["id"]: listing for listing in listings}

    sections = select_sections(ranked["hot"], ranked["rising"], available_ids=set(cards))
    return {
        "hot": [cards[i] for i in sections["hot"]],
        "rising": [cards[i] for i in sections["rising"]],
    }
