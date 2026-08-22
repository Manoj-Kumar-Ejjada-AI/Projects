import asyncio
from errors.framework import ErrorCode, StructuredError

class Retry:
    def __init__(self,
                 max_attempts,
                 base_delay):
        self.max_attempts = max_attempts
        self.base_delay = base_delay

    async def execute(self, operation):
        last_error = None

        for attempt in range(1, self.max_attempts+1):

            result, error = await operation()

            if error is None:
                return result, None

            if not error.retryable:
                return None, error

            last_error = error
            
            if attempt >= self.max_attempts:
                break

            delay = self.base_delay * (
                2 ** (attempt-1)
            )

            asyncio.sleep(delay)
        return None, last_error



