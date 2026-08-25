"""Tiny in-memory sliding-window rate limiter, keyed per caller (e.g. user_id).
Single-process only — resets on restart, doesn't share state across instances.
Swap for a Redis-backed limiter if this needs to survive restarts or scale out.
"""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException

_lock = Lock()
_hits: dict[str, deque] = defaultdict(deque)


def enforce_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """Raise HTTP 429 if `key` has already made max_requests calls in the last window_seconds."""
    now = time.monotonic()
    with _lock:
        hits = _hits[key]
        cutoff = now - window_seconds
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - hits[0])) + 1)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded — max {max_requests} requests per {window_seconds}s. Try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)
