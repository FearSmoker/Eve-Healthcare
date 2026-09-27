from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger("eve_healthcare")

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
            retry_on_timeout=False,
        )
    return _redis_client


# fetch value from redis cache, returns None on miss or connection error
def cache_get(key: str) -> Optional[Any]:
    if not settings.CACHE_ENABLED:
        return None
    try:
        raw = _get_redis().get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except (RedisError, OSError, json.JSONDecodeError) as e:
        logger.debug(f"Cache GET miss/error for key={key!r}: {e}")
        return None


# serialize and save value to redis with ttl
def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    if not settings.CACHE_ENABLED:
        return
    try:
        serialised = json.dumps(value, default=str)
        _get_redis().set(key, serialised, ex=ttl)
    except (RedisError, OSError, TypeError) as e:
        logger.debug(f"Cache SET failed for key={key!r}: {e}")


# remove specific keys from cache
def cache_delete(*keys: str) -> None:
    if not settings.CACHE_ENABLED or not keys:
        return
    try:
        _get_redis().delete(*keys)
    except (RedisError, OSError) as e:
        logger.debug(f"Cache DEL failed for keys={keys}: {e}")


# delete keys matching pattern using non-blocking scan
def cache_delete_pattern(pattern: str) -> None:
    if not settings.CACHE_ENABLED:
        return
    try:
        r = _get_redis()
        cursor = 0
        while True:
            cursor, batch = r.scan(cursor=cursor, match=pattern, count=100)
            if batch:
                r.delete(*batch)
            if cursor == 0:
                break
    except (RedisError, OSError) as e:
        logger.debug(f"Cache DEL pattern={pattern!r} failed: {e}")


# ping redis for health check
def is_redis_available() -> bool:
    if not settings.CACHE_ENABLED:
        return False
    try:
        return _get_redis().ping()
    except (RedisError, OSError):
        return False
