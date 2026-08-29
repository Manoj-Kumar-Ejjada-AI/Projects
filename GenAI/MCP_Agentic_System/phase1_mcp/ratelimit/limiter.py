from enum import Enum
import asyncio
import time

class Bucket(Enum):
    tokens: float
    last_filled: float

class RateLimiter:

    def __init__(self,
                 capacity,
                 refill_rate):

        self.capacity = capacity
        self.refill_rate = refill_rate

        self._buckets: dict[str, Bucket] = {}

        self._lock = asyncio.Lock()

    def _refill(self,
                bucket: Bucket,
                now: float):

        elapsed = (
            now - bucket.last_filled
        )

        bucket.tokens = min(
            self.capacity,
            bucket.tokens +
            elapsed * self.refill_rate
        )

        bucket.last_filled = now

    def acquire(self,
                      key,
                      cost):

        if cost <= 0:
            raise ValueError(
                "cost must be greater than 0"
            )

        bucket = self._buckets.get(key)

        now = time.monotonic()

        if bucket is None:
            bucket = Bucket(
                self.capacity,
                now)
            self._buckets[key] = bucket

        self._refill(
            bucket,
            now
            )

        if cost <= bucket.tokens:
            bucket.tokens -= cost

            return True, 0.0

        missing = cost - bucket.tokens

        retry_after = missing / self.refill_rate

        return False, retry_after

        
