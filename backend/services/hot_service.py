# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
services/hot_service.py

Purpose:
Builds the Hot page: Hot Right Now and Rising.

How it works:
- The database returns each shopper's latest action of each kind per listing.
- The scoring below is plain Python, so it can be tested without a database.
- Ranked ids are cached per process; card data is always re-read, so a listing
  that sold out or was hidden since then never shows.

Settings live in config/hot_ranking.py.
"""

import math
import os
import threading
import time
from types import MappingProxyType

from config import hot_ranking as cfg
from models.interest_model import get_engagement_events, get_storefront_reach
from models.listing_model import browse_public_listings


# ________________________________________________________
# SCORING (pure)
# ________________________________________________________

def decay(age_hours, half_life_hours):
    """1.0 now, 0.5 after one half-life, 0.25 after two."""
    return 0.5 ** (max(age_hours, 0) / half_life_hours)


def engager_contribution(events, half_life_hours):
    """One shopper's worth to a listing: their strongest action after decay (no stacking)."""
    return max(cfg.WEIGHTS[e["kind"]] * decay(e["age_hours"], half_life_hours) for e in events)


def score_listings(events, window_hours, half_life_hours):
    """
    Groups events by listing and shopper.
    Returns {listing_id: {listing_id, storefront_id, raw_score, engagers,
                          strong_engagers, latest_age_hours}}.
    """
    by_listing = {}
    for e in events:
        if e["age_hours"] > window_hours:
            continue
        listing = by_listing.setdefault(e["listing_id"], {"storefront_id": e["storefront_id"], "users": {}})
        listing["users"].setdefault(e["user_id"], []).append(e)

    scored = {}
    for listing_id, listing in by_listing.items():
        users = listing["users"]
        scored[listing_id] = {
            "listing_id": listing_id,
            "storefront_id": listing["storefront_id"],
            "raw_score": sum(engager_contribution(evs, half_life_hours) for evs in users.values()),
            "engagers": len(users),
            "strong_engagers": sum(
                1 for evs in users.values() if any(e["kind"] in cfg.STRONG_KINDS for e in evs)
            ),
            "latest_age_hours": min(e["age_hours"] for evs in users.values() for e in evs),
        }
    return scored


def _rank_key(candidate):
    # score desc, latest engagement desc, id desc
    return (-candidate["score"], candidate["latest_age_hours"], -candidate["listing_id"])


def rank_hot(events):
    """Every listing that qualifies for Hot, best first."""
    scored = score_listings(events, cfg.HOT_WINDOW_DAYS * 24, cfg.HOT_HALF_LIFE_HOURS)
    ranked = [
        {**s, "score": s["raw_score"]}
        for s in scored.values()
        if s["engagers"] >= cfg.HOT_MIN_ENGAGERS and s["strong_engagers"] >= cfg.HOT_MIN_STRONG_ENGAGERS
    ]
    return sorted(ranked, key=_rank_key)


def rising_score(raw_score, reach):
    """Smaller storefronts (fewer distinct shoppers) get a boost."""
    return raw_score / math.sqrt(1 + reach / cfg.RISING_REACH_SCALE)


def rank_rising(events, reach_by_storefront):
    """
    Every listing that qualifies for Rising, best first.
    Thresholds use the raw score; the boost only changes the order.
    """
    scored = score_listings(events, cfg.RISING_WINDOW_DAYS * 24, cfg.RISING_HALF_LIFE_HOURS)
    ranked = []
    for s in scored.values():
        if (s["engagers"] >= cfg.RISING_MIN_ENGAGERS
                and s["strong_engagers"] >= cfg.RISING_MIN_STRONG_ENGAGERS
                and s["raw_score"] >= cfg.RISING_MIN_RAW_SCORE
                and s["latest_age_hours"] <= cfg.RISING_RECENT_HOURS):
            reach = reach_by_storefront.get(s["storefront_id"], 0)
            ranked.append({**s, "score": rising_score(s["raw_score"], reach)})
    return sorted(ranked, key=_rank_key)


# ________________________________________________________
# SECTIONS (pure)
# ________________________________________________________

def _pick_per_storefront(candidates, max_per_storefront, limit, exclude_ids=()):
    excluded = set(exclude_ids)
    picked = []
    per_store = {}
    for c in candidates:
        if len(picked) >= limit:
            break
        if c["listing_id"] in excluded:
            continue
        store = c["storefront_id"]
        if per_store.get(store, 0) >= max_per_storefront:
            continue
        per_store[store] = per_store.get(store, 0) + 1
        picked.append(c["listing_id"])
    return picked


def select_hot(candidates):
    """Max 2 per storefront; under 4, top up from the rest in score order. Limit 8."""
    picked = _pick_per_storefront(candidates, cfg.HOT_MAX_PER_STOREFRONT, cfg.HOT_LIMIT)
    if len(picked) < cfg.HOT_MIN_RESULTS:
        chosen = set(picked)
        for c in candidates:
            if len(chosen) >= cfg.HOT_MIN_RESULTS:
                break
            chosen.add(c["listing_id"])
        picked = [c["listing_id"] for c in candidates if c["listing_id"] in chosen]
    return picked


def select_rising(candidates, exclude_ids):
    """Max 1 per storefront, nothing already in Hot. Limit 8."""
    return _pick_per_storefront(candidates, cfg.RISING_MAX_PER_STOREFRONT, cfg.RISING_LIMIT, exclude_ids)


def select_sections(hot_candidates, rising_candidates, available_ids):
    """
    Picks Hot then Rising from ranked candidates.
    available_ids: listings still visible and in stock right now (None = skip the check).
    """
    if available_ids is not None:
        hot_candidates = [c for c in hot_candidates if c["listing_id"] in available_ids]
        rising_candidates = [c for c in rising_candidates if c["listing_id"] in available_ids]
    hot = select_hot(hot_candidates)
    rising = select_rising(rising_candidates, exclude_ids=hot)
    return {"hot": hot, "rising": rising}


# ________________________________________________________
# RANKING CACHE (per process)
# ________________________________________________________

class RankingCache:
    """
    Holds the ranked candidates for CACHE_SECONDS in this process only.
    Each app process keeps its own copy; only ids and scores are kept,
    never card data, so a stale entry can't show an unavailable listing.
    """

    def __init__(self, ttl_seconds):
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._value = None
        self._expires_at = 0.0

    def get_or_compute(self, compute):
        with self._lock:
            if self._value is not None and time.monotonic() < self._expires_at:
                return self._value
        value = compute()   # outside the lock; a failure is never cached
        with self._lock:
            self._value = value
            self._expires_at = time.monotonic() + self.ttl_seconds
        return value

    def peek(self):
        return self._value

    def clear(self):
        with self._lock:
            self._value = None
            self._expires_at = 0.0

    def reset_after_fork(self):
        # a forked worker starts empty with a new lock
        self._lock = threading.Lock()
        self._value = None
        self._expires_at = 0.0


_ranking_cache = RankingCache(cfg.CACHE_SECONDS)

if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_ranking_cache.reset_after_fork)


def clear_ranking_cache():
    _ranking_cache.clear()


def _frozen(candidates):
    keys = ("listing_id", "storefront_id", "score", "latest_age_hours")
    return tuple(MappingProxyType({key: c[key] for key in keys}) for c in candidates[:cfg.MAX_CANDIDATES])


def _compute_ranked_candidates():
    events = get_engagement_events(max(cfg.HOT_WINDOW_DAYS, cfg.RISING_WINDOW_DAYS) * 24)
    reach = get_storefront_reach({e["storefront_id"] for e in events}, cfg.RISING_REACH_DAYS)
    return MappingProxyType({
        "hot": _frozen(rank_hot(events)),
        "rising": _frozen(rank_rising(events, reach)),
    })


# ________________________________________________________
# HOT PAGE
# ________________________________________________________

def _cards_by_id(listing_ids):
    """Fresh card data for listings that are visible and in stock right now."""
    if not listing_ids:
        return {}
    listings, _ = browse_public_listings(listing_ids=list(listing_ids), available_only=True,
                                         limit=len(listing_ids))
    return {listing["id"]: listing for listing in listings}


def get_hot_page_data():
    """Returns {"hot": [...], "rising": [...]} in the category card shape."""
    ranked = _ranking_cache.get_or_compute(_compute_ranked_candidates)

    candidate_ids = list(dict.fromkeys(c["listing_id"] for c in ranked["hot"] + ranked["rising"]))
    cards = _cards_by_id(candidate_ids)
    sections = select_sections(ranked["hot"], ranked["rising"], available_ids=set(cards))

    return {
        "hot": [cards[i] for i in sections["hot"] if i in cards],
        "rising": [cards[i] for i in sections["rising"] if i in cards],
    }
