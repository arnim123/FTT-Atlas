import time
from collections import defaultdict
from threading import Lock


class SlidingWindowLimiter:
    """Process-local limiter. Enough for a single API instance and for tests."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def allow(self, key: str, *, limit: int, window_seconds: int, now: float | None = None) -> bool:
        moment = time.monotonic() if now is None else now
        with self._lock:
            recent = [stamp for stamp in self._hits[key] if moment - stamp < window_seconds]
            if len(recent) >= limit:
                self._hits[key] = recent
                return False
            recent.append(moment)
            self._hits[key] = recent
            return True

    def consume(self, key: str, *, limit: int, window_seconds: int, now: float | None = None) -> int | None:
        """Record one hit. Return None when it is allowed, or Retry-After seconds when it is not."""
        moment = time.monotonic() if now is None else now
        with self._lock:
            recent = [stamp for stamp in self._hits[key] if moment - stamp < window_seconds]
            if len(recent) >= limit:
                self._hits[key] = recent
                wait = window_seconds - (moment - recent[0])
                return max(1, int(wait + 0.999))
            recent.append(moment)
            self._hits[key] = recent
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


google_login_limiter = SlidingWindowLimiter()
token_limiter = SlidingWindowLimiter()
oauth_register_limiter = SlidingWindowLimiter()
upload_limiter = SlidingWindowLimiter()
