import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_lock = threading.Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    with _lock:
        bucket = _buckets[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Wait a moment and try again.",
            )
        bucket.append(now)


def reset_rate_limits() -> None:
    with _lock:
        _buckets.clear()
