"""Small in-process sliding-window rate limiter.

Suitable for the single-process prototype. A distributed deployment must move
this to Redis; that is recorded in docs/KNOWN_LIMITATIONS.md.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = max(1, limit)
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._events.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)

    def retry_after_seconds(self, key: str) -> int:
        with self._lock:
            bucket = self._events.get(key)
            if not bucket:
                return 0
            return max(1, int(self.window_seconds - (time.monotonic() - bucket[0])))
