import logging
import math
import threading
import time

from redis.exceptions import RedisError

from src.utils.errors import RateLimitExceeded
from src.utils.redis import redis_client

logger = logging.getLogger(__name__)

_INCREMENT_WITH_EXPIRY = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""

LOGIN_ATTEMPT_LIMIT = 5
LOGIN_WINDOW_SECONDS = 60

_fallback_lock = threading.Lock()
_fallback_attempts: dict[str, tuple[float, int]] = {}
_last_fallback_cleanup = 0.0
_redis_failure_logged = False


def _enforce_in_memory_rate_limit(client_ip: str) -> None:
    global _last_fallback_cleanup

    now = time.monotonic()
    with _fallback_lock:
        if now - _last_fallback_cleanup >= LOGIN_WINDOW_SECONDS:
            expired_ips = [
                ip
                for ip, (window_started, _) in _fallback_attempts.items()
                if now - window_started >= LOGIN_WINDOW_SECONDS
            ]
            for ip in expired_ips:
                del _fallback_attempts[ip]
            _last_fallback_cleanup = now

        window_started, attempts = _fallback_attempts.get(client_ip, (now, 0))
        if now - window_started >= LOGIN_WINDOW_SECONDS:
            window_started, attempts = now, 0

        attempts += 1
        _fallback_attempts[client_ip] = (window_started, attempts)

    if attempts > LOGIN_ATTEMPT_LIMIT:
        retry_after = max(1, math.ceil(LOGIN_WINDOW_SECONDS - (now - window_started)))
        raise RateLimitExceeded(retry_after)


def enforce_login_rate_limit(client_ip: str) -> None:
    global _redis_failure_logged

    key = f"login-rate-limit:{client_ip}"
    try:
        attempts, ttl = redis_client.eval(
            _INCREMENT_WITH_EXPIRY,
            1,
            key,
            LOGIN_WINDOW_SECONDS,
        )
        attempts = int(attempts)
        ttl = int(ttl)
    except RedisError as exc:
        if not _redis_failure_logged:
            logger.warning(
                "Redis unavailable; using process-local login rate limiting: %s",
                exc,
            )
            _redis_failure_logged = True
        _enforce_in_memory_rate_limit(client_ip)
        return

    _redis_failure_logged = False

    if attempts > LOGIN_ATTEMPT_LIMIT:
        raise RateLimitExceeded(max(1, ttl))
