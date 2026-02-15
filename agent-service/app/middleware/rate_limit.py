import time
from collections import defaultdict

from fastapi import HTTPException, Request


class RateLimiter:
    """In-memory sliding window rate limiter.

    Tracks requests per key (IP or tenant) within a time window.
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        self._requests[key] = [
            t for t in self._requests[key] if t > cutoff
        ]
        # Evict stale keys to prevent unbounded growth
        if not self._requests[key]:
            del self._requests[key]

    def check(self, key: str) -> bool:
        """Returns True if the request is allowed, False if rate limited."""
        now = time.monotonic()
        self._cleanup(key, now)
        if len(self._requests.get(key, [])) >= self.max_requests:
            return False
        self._requests[key].append(now)
        return True


# Shared limiter instances
_webhook_limiter = RateLimiter(max_requests=30, window_seconds=60)


def get_client_ip(request: Request) -> str:
    # Use the direct connection IP — X-Forwarded-For can be spoofed by clients.
    # When deployed behind a trusted reverse proxy (Railway, nginx, etc.),
    # the proxy sets the real client IP as the direct connection.
    return request.client.host if request.client else "unknown"


async def check_webhook_rate_limit(request: Request) -> None:
    """Dependency to enforce rate limiting on webhook endpoints."""
    ip = get_client_ip(request)
    if not _webhook_limiter.check(ip):
        raise HTTPException(status_code=429, detail="Too many requests")
