"""Lightweight protection for the public deployment: rate limit + result cache."""
from __future__ import annotations
import time
import threading

RATE_MAX = 5            # max live runs ...
RATE_WINDOW = 3600      # ... per this many seconds, per IP
CACHE_TTL = 6 * 3600    # cache a finished report for 6 hours


class RateLimiter:
    def __init__(self, max_calls: int = RATE_MAX, window: int = RATE_WINDOW):
        self.max_calls = max_calls
        self.window = window
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            if len(hits) >= self.max_calls:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True

    def retry_after(self, key: str) -> int:
        now = time.time()
        hits = self._hits.get(key, [])
        if not hits:
            return 0
        return max(0, int(self.window - (now - min(hits))))


class ResultCache:
    def __init__(self, ttl: int = CACHE_TTL):
        self.ttl = ttl
        self._store: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            ts, value = entry
            if time.time() - ts > self.ttl:
                self._store.pop(key, None)
                return None
            return value

    def put(self, key: str, value: dict):
        with self._lock:
            self._store[key] = (time.time(), value)


rate_limiter = RateLimiter()
result_cache = ResultCache()