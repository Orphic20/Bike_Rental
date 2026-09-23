"""In-memory caps for the public write paths.

One Render instance is enough for this shop. Keys are per client IP
(X-Forwarded-For on Render). Restarting the service clears the counters.
"""

from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException, Request


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, times: int, seconds: int, name: str) -> None:
        self.times = times
        self.seconds = seconds
        self.name = name
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        key = f"{self.name}:{_client_ip(request)}"
        now = monotonic()
        bucket = self._hits[key]
        cutoff = now - self.seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.times:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Wait a minute and try again.",
                headers={"Retry-After": str(self.seconds)},
            )
        bucket.append(now)


# Generous enough for a real booking plus mobile retries; tight enough to
# stop a script from flooding Cloudinary or creating junk reservations.
limit_bookings = RateLimiter(8, 60, "bookings")
limit_uploads = RateLimiter(12, 60, "uploads")
limit_profile = RateLimiter(60, 60, "profile")
