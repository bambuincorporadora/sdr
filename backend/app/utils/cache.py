from __future__ import annotations

from functools import lru_cache

from redis.asyncio import Redis

from app.config import get_settings


@lru_cache
def _redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)  # type: ignore[arg-type]


def get_redis_client() -> Redis:
    return _redis_client()


async def set_if_absent(key: str, value: str, ttl_seconds: int) -> bool:
    """
    Set key if it does not exist. Returns True if inserted, False if key existed.
    """
    client = get_redis_client()
    result = await client.set(key, value, ex=ttl_seconds, nx=True)
    return bool(result)


async def delete_key(key: str) -> None:
    client = get_redis_client()
    await client.delete(key)
