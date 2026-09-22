"""Redis cache utilities with predictable key patterns.

Cache keys follow the conventions:
    matches:list:{filters_hash}
    match:{id}
    match:{id}:summary
    match:{id}:prediction
    match:{id}:research
    league:{id}
    team:{id}
    predictions:list:{filters_hash}
    prediction:{id}

TTLs are configurable via environment variables.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from core.config import get_settings
from db.redis_client import RedisClient, redis_client

logger = logging.getLogger(__name__)

# ── TTLs (seconds) ────────────────────────────────────────────────────── #
TTL_MATCHES_LIST = 1800
TTL_MATCH_DETAIL = 1800
TTL_MATCH_SUMMARY = 300
TTL_PREDICTION = 300
TTL_RESEARCH = 600
TTL_LEAGUE = 86400
TTL_TEAM = 86400
TTL_SEARCH = 1800
TTL_PREDICTIONS_LIST = 600


def _hash_params(params: dict[str, Any]) -> str:
    """Create a deterministic hash from query params for cache keys."""
    raw = json.dumps(params, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def cache_matches_list_key(**params: Any) -> str:
    return f"matches:list:{_hash_params({k: v for k, v in params.items() if v is not None})}"


def cache_match_key(match_id: str) -> str:
    return f"match:{match_id}"


def cache_match_summary_key(match_id: str) -> str:
    return f"match:{match_id}:summary"


def cache_match_prediction_key(match_id: str) -> str:
    return f"match:{match_id}:prediction"


def cache_match_research_key(match_id: str) -> str:
    return f"match:{match_id}:research"


def cache_league_key(league_id: str) -> str:
    return f"league:{league_id}"


def cache_league_standings_key(league_id: str, season: str | None = None) -> str:
    suffix = f":{season}" if season else ""
    return f"league:{league_id}:standings{suffix}"


def cache_league_matches_key(league_id: str, **params: Any) -> str:
    return f"league:{league_id}:matches:{_hash_params({k: v for k, v in params.items() if v is not None})}"


def cache_team_key(team_id: str) -> str:
    return f"team:{team_id}"


def cache_team_matches_key(team_id: str, **params: Any) -> str:
    return f"team:{team_id}:matches:{_hash_params({k: v for k, v in params.items() if v is not None})}"


def cache_team_form_key(team_id: str) -> str:
    return f"team:{team_id}:form"


def cache_team_statistics_key(team_id: str) -> str:
    return f"team:{team_id}:statistics"


def cache_team_injuries_key(team_id: str) -> str:
    return f"team:{team_id}:injuries"


def cache_predictions_list_key(**params: Any) -> str:
    return f"predictions:list:{_hash_params({k: v for k, v in params.items() if v is not None})}"


def cache_prediction_key(prediction_id: str) -> str:
    return f"prediction:{prediction_id}"


def cache_search_key(**params: Any) -> str:
    return f"search:{_hash_params({k: v for k, v in params.items() if v is not None})}"


async def invalidate_cache_keys(*keys: str) -> int:
    """Delete multiple cache keys and return count deleted."""
    if not keys:
        return 0
    try:
        return await redis_client.client.delete(*keys)
    except Exception as exc:
        logger.warning("Cache invalidation failed", extra={"keys": keys, "error": str(exc)})
        return 0


async def get_cached(key: str) -> Any:
    """Retrieve and deserialize a cached JSON value."""
    try:
        raw = await redis_client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


async def set_cached(key: str, value: Any, ttl: int | None = None) -> None:
    """Serialize and store a value in the cache."""
    try:
        await redis_client.set(key, json.dumps(value), ttl=ttl)
    except Exception:
        pass
