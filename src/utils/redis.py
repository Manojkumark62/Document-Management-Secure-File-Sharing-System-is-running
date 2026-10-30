import json
import logging
import os
import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)
redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

def get_cached_json(key: str):
    try:
        value = redis_client.get(key)
        return json.loads(value) if value is not None else None
    except (RedisError, ValueError):
        logger.exception("Redis cache read failed")
        return None

def set_cached_json(key: str, value, ttl: int = 60):
    try:
        redis_client.set(key, json.dumps(value), ex=ttl)
    except (RedisError, TypeError, ValueError):
        logger.exception("Redis cache write failed")


def invalidate_document_list_cache():
    try:
        for key in redis_client.scan_iter(match="document-list:*", count=100):
            redis_client.delete(key)
    except RedisError:
        logger.exception("Redis cache invalidation failed")