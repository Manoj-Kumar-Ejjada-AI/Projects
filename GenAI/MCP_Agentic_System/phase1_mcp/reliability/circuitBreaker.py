from enum import Enum
import time
from errors.framework import ErrorCode, StructuredError
import asyncio
from typing import Callable, Awaitable

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

Operation = Callable[
    [],
    Awaitable[
        tuple[object | None, StructuredError|None]
    ]
]

class CircuitBreaker:
    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 30.0):

        if failure_threshold < 1:
            raise ValueError(
                "failure_threshold must be >=1"
                )
        if recovery_timeout <= 0:
            raise ValueError(
                "recovery_timeout must be >0"
            )

        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at: float|None = None
        self.half_open_probe = False
        self._lock = asyncio.Lock()


    async def _before_call(self):

        async with self._lock:

            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:

                assert self.opened_at is not None

                elapsed_time = (
                    time.monotonic() -
                    self.opened_at
                )

                if elapsed_time < self.recovery_timeout:
                    return False

                self.state = CircuitState.HALF_OPEN

                self.half_open_probe = True

                return True

            if self.state == CircuitState.HALF_OPEN:

                if self.half_open_probe:
                    return False

                self.half_open_probe = True
                return True
            



    async def record_success(self):
        async with self._lock:

            self.failure_count = 0
            self.state = CircuitState.CLOSED
            self.opened_at = None
            self.half_open_probe = False

    async def record_failure(self):

        async with self._lock:

            self.failure_count += 1
            self.half_open_probe = False

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.opened_at = time.monotonic

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = time.monotonic()

    async def execute(self, operation):

        allowed = await self._before_call()


        if not allowed:

            error = StructuredError(
                code = ErrorCode.CIRCUIT_OPEN,
                message= ("Circuit Breaker is Open;"
                        "Tool execution is temporarily blocked"),
                retryable=True,
                counts_toward_circuit_breaker=False
            )

            return None, error
        
        try:
            result, error = await operation()

        except asyncio.CancelledError:
            async with self._lock:
                self.half_open_probe = False
            raise


        if error is None:
            await self.record_success()
            return result, None
        if error.counts_toward_circuit_breaker:
            
            await self.record_failure
            return None, error
        else:

            await self.record_success

        return None, error
        
            



    


    


        
