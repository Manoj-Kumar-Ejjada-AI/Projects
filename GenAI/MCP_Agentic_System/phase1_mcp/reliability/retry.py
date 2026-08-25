import asyncio
from errors.framework import ErrorCode, StructuredError
import random
from typing import Awaitable, Callable

Operation = Callable[
    [],
    Awaitable[
        tuple[object|None, StructuredError|None]
    ]
]

class RetryPolicy:
    def __init__(self,
                 max_attempts = 3,
                 base_delay = 0.5,
                 max_delay = 10.0
                 ):

        if max_attempts < 1:
            raise ValueError(
                "max_attemps must be greater than or equal to 1"
            )
        if base_delay < 0:
            raise ValueError(
                "base_delay must be greater than 0"
            )
        if max_delay<base_delay:
            raise ValueError(
                "max_delay must be greater than base_delay"
            )
        
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay

    def _get_delay(self,
                   error: StructuredError,
                   attempt):

        retry_after = error.details.get(
            "retry_after"
        )

        if retry_after is not None:
            return min(retry_after,
                       self.max_delay)

        exponential_delay = min(
            self.max_delay,
            self.base_delay * 2 ** (attempt-1)
        )
        return random.uniform(
            0, 
            exponential_delay
        )



    async def execute(self,
                    operation: Operation):
        
        last_error = None

        for attempt in range(1, self.max_attempts+1):

            try:

                result, error = await operation()

            except asyncio.CancelledError:
                raise

            if error is None:
                return result, None

            last_error = error

            if not error.retryable:
                return None, error

            
            if attempt >= self.max_attempts:
                break

            delay = self._get_delay(
                error,
                attempt
            )

            await asyncio.sleep(delay)
        return None, last_error



