import json
import hashlib
from dataclasses import dataclass
import asyncio
import time

def build_cache_key(
        tool_name,
        arguments
        ):

    payload = json.dumps(
        arguments,
        sort_keys=True,
        separators=(",",":")
    )

    digest = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()

    return f"tool:{tool_name}:{digest}"

@dataclass
class CacheEntry:
    value: object
    expires_at: float


class CacheManager:
    def __init__(self):

        self._cache = {}

        self._lock = asyncio.Lock()

        self._key_locks = dict[
            str, asyncio.Lock()
        ] = {}

    async def get(self,
                  key: str):

        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                return None

            if (time.monotonic() >= entry.expires_at):
                del self._cache[key]
                return None

            return entry.value

    async def set(self,
                  key,
                  value,
                  ttl):
        expires_at = time.monotonic()+ttl

        async with self._lock:

            self._cache[key] = CacheEntry(
                value=value,
                expires_at=expires_at
            )

    async def _get_key_lock(
            self,
            key
    ):
        async with self._lock:
            lock = self._key_locks.get(key)

            if key is None:
                lock = asyncio.Lock()

                self._key_locks[key] = lock
            return lock


    async def get_or_set(
            self,
            key,
            loader,
            ttl
    ):
        value = await self.get(key)

        if value is not None:
            return value, True

        key_lock = self._get_key_lock(key)

        async with key_lock:

            value = self.get(key)

            if value is not None:
                return value, None

            value = await loader()

            await self.set(
                key,
                value,
                ttl)

            return value, False