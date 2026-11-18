"""The login limiter must actually stop repeated attempts from one source."""

from __future__ import annotations

from app.core.ratelimit import SlidingWindowLimiter


def test_limiter_allows_up_to_the_limit_then_blocks() -> None:
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert [limiter.allow("1.2.3.4") for _ in range(3)] == [True, True, True]
    assert limiter.allow("1.2.3.4") is False


def test_limiter_is_per_key() -> None:
    limiter = SlidingWindowLimiter(limit=1)
    assert limiter.allow("first") is True
    assert limiter.allow("second") is True
    assert limiter.allow("first") is False


def test_retry_after_is_reported_and_reset_clears_the_bucket() -> None:
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
    limiter.allow("client")
    assert limiter.retry_after_seconds("client") >= 1
    limiter.reset("client")
    assert limiter.allow("client") is True
