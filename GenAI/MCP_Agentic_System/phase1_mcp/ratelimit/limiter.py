from enum import Enum
import asyncio
import time
from redis.asyncio import Redis
from errors.framework import StructuredError, ErrorCode
from dataclasses import dataclass

RATE_LIMIT_SCRIPT = """
local key = KEYS[1]

local capacity = tonumber(ARGV[1])
local refill_per_sec = tonumber(ARGV[2])
local now_ms = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local bucket = redis.call(
                'HMGET',
                key,
                'tokens',
                'last_ms')

local tokens = bucket[1] or capacity
local last_ms = bucket[2] or now_ms

local elapsed = math.max(
                    0,
                    (now_ms - last_ms) / 1000)

tokens = math.min(
                capacity,
                tokens+(elapsed * refill_per_sec))

local allowed = 0
local retry_after_ms = 0

if tokens >= cost then
    tokens = tokens - cost
    allowed = 1

else

local deficit = cost - tokens
local retry_after_ms = math.ceil(
                        (deficit / refill_per_sec)*1000
                        )
end

redis.call(
    'HMSET',
    key,
    'tokens',
    tokens,
    'last_ms',
    now_ms
    )

redis.call(
    'EXPIRE',
    key,
    3600
    )

return {
allowed,
retry_after_ms,
tokens
}


"""

@dataclass(frozen=True)
class Quota:
    capacity: int
    refill_per_min: int 

class RateLimiter:
    def __init__(self,
                 redis_url,
                 default_capacity:int = 60,
                 default_rpm: int = 60):
        
        self.redis_url = redis_url

        self.default_quota = Quota(
            capacity=default_capacity,
            refill_per_min=default_rpm
        )

        self._redis: Redis | None = None
        self._script_sha: str | None = None

    async def connect(self):

        self._redis = Redis.from_url(
            self.redis_url
        )

        await self._script_sha = (
            await self._redis.script_load(
            RATE_LIMIT_SCRIPT
            )
        )

    async def disconnect(self):

        if self._redis is not None:
            await self._redis.close()

            self._redis = None
            self._script_sha = None

    async def acquire(
            self,
            tenant,
            tool,
            cost = 1
    ):
        if self._redis is None:
            raise RuntimeError(
                "RateLimiter is not connected"
            )

        if self._script_sha is None:
            raise RuntimeError(
                "Rate limit script is not loaded"
            )

        quota = self.default_quota

        refill_per_second = (
            quota.refill_per_min/60.0
        )

        key = (
            f"atlas:rl"
            f"{tenant}"
            f"{tool}"
        )

        now_ms = (
            time.monotonic()
        )

        allowed, retry_after_ms, _ = (
            await self._redis.evalsha(
                self._script_sha,
                1,
                key,
                quota.capacity,
                refill_per_second,
                now_ms,
                cost

            )
        )

        if not allowed:
            return StructuredError(
                code=ErrorCode.RATE_LIMITED,
                message=(
                    f"Tool '{tool}' is rate limited."
                ),
                retryable=True,
                counts_toward_circuit_breaker=False,
                details={
                    "tenant": tenant,
                    "retry_after": (
                        float(retry_after_ms) / 1000.0
                    ),
                },
            )
        
        return None

