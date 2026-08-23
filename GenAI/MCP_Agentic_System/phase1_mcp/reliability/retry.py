import asyncio
from errors.framework import ErrorCode, StructuredError
import random

class RetryPolicy:
    def __init__(self,
                 max_attempts,
                 base_delay):
        self.max_attempts = max_attempts
        self.base_delay = base_delay

    async def execute(self, operation):
        last_error = None

        for attempt in range(1, self.max_attempts+1):

            try:

                result, error = await operation()

                if error is None:
                    return result, None
    
                if not error.retryable:
                    return None, error

            except asyncio.CancelledError:
                raise

            except Exception as e:
                last_error = e

            
            if attempt >= self.max_attempts:
                break

            backoff = self.base_delay * (
                2 ** (attempt-1)
            )

            delay = random.uniform(
                0,
                backoff
            )

            await asyncio.sleep(delay)
        return None, last_error



