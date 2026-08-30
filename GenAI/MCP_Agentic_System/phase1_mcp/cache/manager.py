import json
from dataclasses import dataclass
import asyncio
import time
from collections import OrderedDict
from redis.asyncio import Redis

@dataclass
class L1Entry:
    value: object
    expires_at: float


class L1Cache:

    def __init__(
            self,
            max_items: int):

        self.max_items = max_items

        self.store = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(
            self,
            key):

        entry = self.store.get(key)

        if entry is None:
            return None

        if entry.expires_at <= time.monotonic():

            self.store.pop(
                key,
                None
            )

            return None
        self.store.move_to_end(
            key
        )

        return entry.value

    async def set(
            self,
            key,
            value,
            ttl_seconds
    ):
        async with self._lock:

            self.store[key] = L1Entry(
                value=value,
                expires_at = (
                    time.monotonic() +
                    ttl_seconds
                )
            )

            self.store.move_to_end(
                key
            )

            while len(self.store) > self.max_items:
                self.store.popitem(last=False)

    async def delete(
            self,
            key
            ):

        async with self._lock:

            self.store.pop(
                key,
                None)
            

class CacheManager:

    def __init__(
            self,
            redis_url: str,
            l1_max_items: int = 1000,
            l1_ttl_seconds: int = 10,
            l2_ttl_secons: int = 30):

        self.l1 = L1Cache(
            l1_max_items
        )

        self.redis_url = redis_url

        self.l1_ttl_seconds = l1_ttl_seconds

        self.l2_ttl_seconds = self.l2_ttl_seconds

    async def connect(self):

        self.redis = Redis.from_url(
            self.redis_url
        )

    async def disconnect(self):

        if self.redis is not None:

            self.redis.close()

            self.redis = None

    async def get(
            self,
            key):

        # L1 cache

        value = await self.l1.get(key)

        if value is not None:
            return value

        # L2 cache

        if self.redis is None:
            return None

        raw = self.redis.get(key)

        if raw is None:
            return None

        value = json.loads(
            value
        )
        
        await self.l1.set(
            key=key,
            value=value,
            ttl_seconds=self.l1_ttl_seconds
        )

        return value

    async def set(self,
                  key,
                  value,
                  ttl = None):

        ttl_l2 = self.l2_ttl_seconds or ttl

        ttl_l1 = min(
            ttl_l2,
            self.l1_ttl_seconds
        )

        await self.l1.set(
            key=key,
            value=value,
            ttl_seconds=ttl_l1
        )

        if self.redis is not None:

            await self.redis.set(
                key,
                json.dumps(
                    value,
                    default=str
                ),
                ex=ttl_l2
            )

    async def get_or_compute(
            self,
            key,
            compute,
            ttl = None,
            STAMPEDE_LOCK_TTL_MS = 5000,
            STAMPEDE_WAIT_MS = 50
    ):

        hit = self.get(key=key)

        if hit is not None:
            return hit

        if self.redis is None:
            raise RuntimeError(
                "CacheManager is not connected"
            )

        lock_key = f"{key}:lock"

        got_lock = self.redis.set(
            lock_key,
            "1",
            nx=True,
            px=STAMPEDE_LOCK_TTL_MS
        )

        if got_lock:

            try:
                value = await compute()

                self.set(
                    key=key,
                    value=value,
                    ttl=ttl
                )

                return value
            
            finally:

                await self.redis.delete(
                    lock_key
                )

        for _ in range(20):
            asyncio.sleep(
                STAMPEDE_WAIT_MS/1000
            )

            hit = await self.get(key)

            if hit is not None:
                return hit

        value = await compute()

        self.set(
            key=key,
            value=value,
            ttl=ttl
        )

        return value
