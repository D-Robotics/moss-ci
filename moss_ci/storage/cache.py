from __future__ import annotations
import time


class CacheManager:
    def __init__(self, backend: str = "memory", redis_url: str = ""):
        self.backend = backend
        self._store: dict[str, tuple[float, any]] = {}  # (expiry, value)
        if backend == "redis" and redis_url:
            self._redis = None  # Lazy init redis

    def get(self, key: str):
        if self.backend == "memory":
            entry = self._store.get(key)
            if entry is None:
                return None
            expiry, value = entry
            # expiry == 0 means "never expires". Any other value (past or
            # future) is compared against now, so ttl<=0 set in the past
            # (e.g. ttl=-1) is treated as already expired.
            if expiry != 0 and time.time() > expiry:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value, ttl: int = 300):
        if self.backend == "memory":
            # ttl > 0  -> expires at now + ttl
            # ttl == 0 -> never expires (sentinel expiry 0)
            # ttl < 0  -> already expired (past timestamp), so get() misses
            if ttl > 0:
                expiry = time.time() + ttl
            elif ttl == 0:
                expiry = 0
            else:
                expiry = time.time() + ttl  # in the past
            self._store[key] = (expiry, value)
