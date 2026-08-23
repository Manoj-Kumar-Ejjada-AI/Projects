from enum import Enum
import time
from errors.framework import ErrorCode, StructuredError
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"



class CircuitBreaker:
    def __init__(self,
                 failure_threshold,
                 recovery_timeout):

        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at = None

    def can_execute(self):

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed_time = (
                time.monotonic() - self.opened_at
                )
            if elapsed_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return True


        return False


    def record_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.opened_at = None

    def record_failure(self):

        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = time.monotonic()

    async def execute(self, operation):

        if not self.can_execute():

            error = StructuredError(
                code = ErrorCode.CIRCUIT_OPEN,
                message= "Circuit Breaker is Open",
                retryable=True
            )

            return None, error
        
        try:
            result, error = await operation()

            if error is None:
                self.record_success()
                return result, None
            
            self.record_failure
            return None, error
        
        except asyncio.CancelledError:
            raise
            



    


    


        
