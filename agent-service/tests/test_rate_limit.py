import pytest

from app.middleware.rate_limit import RateLimiter


def test_allows_under_limit():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.check("ip1") is True
    assert limiter.check("ip1") is True
    assert limiter.check("ip1") is True


def test_blocks_over_limit():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.check("ip1") is True
    assert limiter.check("ip1") is True
    assert limiter.check("ip1") is False


def test_separate_keys():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.check("ip1") is True
    assert limiter.check("ip2") is True
    # ip1 is now at limit
    assert limiter.check("ip1") is False
    # ip2 is also at limit
    assert limiter.check("ip2") is False


def test_window_expiry():
    """Requests outside the window are cleaned up."""
    import time
    from unittest.mock import patch

    limiter = RateLimiter(max_requests=1, window_seconds=1)
    assert limiter.check("ip1") is True
    assert limiter.check("ip1") is False

    # Simulate time passing beyond the window
    original_timestamps = limiter._requests["ip1"]
    # Shift all timestamps back by 2 seconds
    limiter._requests["ip1"] = [t - 2 for t in original_timestamps]

    assert limiter.check("ip1") is True
