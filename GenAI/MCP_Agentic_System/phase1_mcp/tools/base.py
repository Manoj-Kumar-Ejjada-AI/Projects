from errors.framework import ErrorCode, StructuredError
import asyncio
from reliability.circuitBreaker import CircuitBreaker
from reliability.retry import RetryPolicy

class ToolExecutor:
    def __init__(self, 
                 mcp_client,
                 timeout_seconds=10,
                 overall_timeout_seconds = 30,
                 retry_policy: RetryPolicy|None = None,
                 circuit_breaker: CircuitBreaker|None = None
                 ):
        self.mcp_client = mcp_client
        self.timeout_seconds = timeout_seconds
        self.overall_timeout_seconds = overall_timeout_seconds
        self.retry_policy = retry_policy
        self.circuit_breaker = circuit_breaker

    def _remaining_time(self, deadline):

        loop = asyncio.get_running_loop()

        return max(
            0,
            deadline - loop.time()
        )


    async def _execute_once(self, 
                            tool_name, 
                            arguments,
                            deadline):

        remaining = self._remaining_time(
            deadline
        )

        if remaining <= 0:
            error = StructuredError(
                code=ErrorCode.EXECUTION_DEADLINE_EXCEEDED,
                message=(
                f"Overall execution budget for "
                f"tool '{tool_name}' has expired."
                ),
                retryable=False,
                counts_toward_circuit_breaker=False

            )
            return None, error

        attempt_timeout = min(
            self.timeout_seconds,
            remaining
        )

        try:
            async with asyncio.timeout(attempt_timeout):
                result = await self.mcp_client.call_tool(
                    tool_name, 
                    arguments
                    )
                return result, None

        except asyncio.CancelledError:
            raise
        
        except TimeoutError:
            error = StructuredError(
                code = ErrorCode.TOOL_TIMEOUT,
                message=(
                f"Tool '{tool_name}' exceeded "
                f"its {attempt_timeout:.2f}s "
                "attempt timeout."
                ),
                retryable=True,
                details= {
                    "Timeout_seconds": attempt_timeout
                }
            )

            return None, error

        except (ConnectionError, OSError,) as exc:
            error = StructuredError(
                code= ErrorCode.TOOL_EXECUTION_ERROR,
                message=(
                    f"Tool '{tool_name}' encountered a transient connection failure"
                ),
                retryable=True,
                counts_toward_circuit_breaker= True,
                details={
                    "exception": str(exc)
                }
            )
        
        except Exception as exc:
            error = StructuredError(
                code = ErrorCode.TOOL_EXECUTION_ERROR,
                message= f"Tool '{tool_name}' failed.",
                retryable= False,
                counts_toward_circuit_breaker=False,
                details= {
                    "exception": str(exc)
                }
            )

            return None, error

    async def execute(self, tool_name, arguments):

        loop = asyncio.get_running_loop()

        deadline = loop.time() + self.overall_timeout_seconds

        async def operation():

            if self.retry_policy is None:
                return await self._execute_once(
                    tool_name,
                    arguments,
                    deadline
                )
            return await self.retry_policy.execute(
                lambda: self._execute_once(
                    tool_name,
                    arguments,
                    deadline
                )
            )
        try:
            async with asyncio.timeout(
                self.overall_timeout_seconds
            ):
                if self.circuit_breaker is not None:
                    return await (self.circuit_breaker.execute(
                        operation 
                        )
                    )
                return await operation()
            
        except asyncio.CancelledError:
            raise

        except asyncio.TimeoutError:
            error = StructuredError(
                code=ErrorCode.EXECUTION_DEADLINE_EXCEEDED,
                message=(
                f"Overall execution budget for "
                f"tool '{tool_name}' was exceeded."
                ),
                retryable=True,
                counts_toward_circuit_breaker=True,
                details={
                    "overall_timeout": self.overall_timeout_seconds
                }
            )



