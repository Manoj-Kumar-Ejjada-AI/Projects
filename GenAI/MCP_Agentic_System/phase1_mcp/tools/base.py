from errors.framework import ErrorCode, StructuredError
import asyncio
from reliability.circuitBreaker import CircuitBreaker
from reliability.retry import RetryPolicy
from ratelimit.limiter import RateLimiter
from observability.tracing import (
    get_tracer,
    record_span_error,
    current_trace_id
)
from opentelemetry.trace import Status, StatusCode
import time
from observability.metrics import MetricsRegistry
from cache.manager import (
    CacheManager,
    build_cache_key
)


class ToolExecutor:
    def __init__(
                self, 
                mcp_client,
                timeout_seconds=10,
                overall_timeout_seconds = 30,
                retry_policy: RetryPolicy|None = None,
                circuit_breaker: CircuitBreaker|None = None,
                rate_limiter: RateLimiter | None = None,
                metrics: MetricsRegistry | None = None,
                cache_manager: CacheManager | None = None,
                ):
        
        self.mcp_client = mcp_client
        self.timeout_seconds = timeout_seconds
        self.overall_timeout_seconds = overall_timeout_seconds
        self.retry_policy = retry_policy
        self.circuit_breaker = circuit_breaker
        self.rate_limiter = rate_limiter

        self.tracer = get_tracer()
        self.metrics = metrics

        self.cache_manager = cache_manager

    def _remaining_time(self, deadline):

        loop = asyncio.get_running_loop()

        return max(
            0,
            deadline - loop.time()
        )

    def record_metrics(
            self,
            tool_name,
            status,
            duration
    ):
        if self.metrics is None:
            return

        self.metrics.calls_total.labels(
            tool = tool_name,
            status = status
        ).inc()

        self.metrics.latency.labels(
            tool = tool_name
        ).observe(duration)


    async def _execute_once(self, 
                            tool_name, 
                            arguments,
                            deadline):


        with self.tracer.start_as_current_span(
            "tool.attempt"
            ) as span:

            span.set_attribute(
                "tool.name",
                tool_name
            )

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

                span.set_attribute(
                    "tool.error_code",
                    error.code
                )

                span.set_status(
                    Status(
                        StatusCode.ERROR,
                        str(error.message)
                    )
                )

                return None, error

            attempt_timeout = min(
                self.timeout_seconds,
                remaining
            )

            span.set_attribute(
                "tool.timeout_seconds",
                attempt_timeout
            )

            try:

                with self.tracer.start_as_current_span(
                    "mcp.call"
                ) as mcp_span:
                    
                    mcp_span.set_attribute(
                        "tool.name",
                        tool_name
                    )

                    async with asyncio.timeout(attempt_timeout):
                        result = await self.mcp_client.call_tool(
                            tool_name, 
                            arguments
                            )

                    mcp_span.set_status(
                        StatusCode.OK
                    )

                    return result, None

            except asyncio.CancelledError:

                span.set_attribute(
                    "tool.cancelled",
                    True
                )

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

                span.set_attribute(
                    "tool.error_code",
                    error.code
                )

                record_span_error(
                    span,
                    exc
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

                span.set_attribute(
                    "tool.error_code",
                    error.code
                )

                record_span_error(
                    span,
                    exc
                )

                return None, error
                
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

                span.set_attribute(
                    "tool.error_code",
                    error.code
                )

                record_span_error(
                    span,
                    exc
                )

                return None, error

    async def _execute_with_policies(
            self,
            tool_name,
            arguments,
            deadline
    ):
        async def operation():

            if self.retry_policy is None:
                return await self._execute_once(
                    tool_name,
                    arguments,
                    deadline
                )

            with self.tracer.start_as_current_span(
                "retry"
            ) as retry_span:
                
                retry_span.set_attribute(
                    "tool.name",
                    tool_name
                )

                return await self.retry_policy.execute(
                    lambda: self._execute_once(
                        tool_name,
                        arguments,
                        deadline
                    )
                )

        if self.circuit_breaker is not None:

            with self.tracer.start_as_current_span(
                "circuit_breaker"
            ) as circuit_breaker_span:

                circuit_breaker_span.set_attribute(
                    "tool.name",
                    tool_name
                )

                return await self.circuit_breaker.execute(
                    operation
                )

        return await operation()


    async def execute(self, tool_name, arguments):

        start = time.perf_counter()
        status = "error"

        with self.tracer.start_as_current_span(
            "tool.execute"
            ) as execute_span:

            execute_span.set_attribute(
                "tool.name",
                tool_name
            )

            trace_id = current_trace_id()

            if trace_id:
                execute_span.set_attribute(
                    "trace.id",
                    trace_id
                )


            if self.rate_limiter is not None:

                with self.tracer.start_as_current_span(
                    "rate_limit"
                ) as rate_span:
                    
                    rate_span.set_attribute(
                        "tool.name",
                        tool_name
                    )

                    allowed, retry_after = await self.rate_limiter.acquire(
                        key=tool_name
                    )

                    rate_span.set_attribute(
                        "ratelimit.allowed",
                        allowed
                    )

                    if retry_after is not None:

                        rate_span.set_attribute(
                            "ratelimit.retry_after",
                            retry_after
                        )

                

                    if not allowed:

                        error = StructuredError(
                            code = ErrorCode.RATE_LIMITED,
                            message= f"Tool '{tool_name}' is rate limited",
                            retryable=True,
                            counts_toward_circuit_breaker=False,
                            details={
                                "retry_after": retry_after
                            }
                        )

                        execute_span.set_attribute(
                            "tool.error_code",
                            error.code
                        )

                        execute_span.set_status(
                            Status(
                                StatusCode.ERROR,
                                error.message
                            )
                        )


                        return None, error



            loop = asyncio.get_running_loop()

            deadline = loop.time() + self.overall_timeout_seconds

            cache_key = None

            if self.cache_manager is not None:

                cache_key = build_cache_key(
                    tool_name,
                    arguments
                )

            

            async def compute():

                return await self._execute_with_policies(
                    tool_name,
                    arguments,
                    deadline
                )


            try:
                async with asyncio.timeout(
                    self.overall_timeout_seconds
                ):
                    if self.cache_manager is not None:
                        result, error = await self.cache_manager.get_or_compute(
                            key = cache_key,
                            compute=compute,
                            tool_name= tool_name
                        )
                    result, error = await compute()

                
                status = "success" if error is None else "error"

                if error is not None:
                
                    execute_span.set_attribute(
                        "tool.error_code",
                        error.code
                    )

                    execute_span.set_status(
                        Status(
                            StatusCode.ERROR,
                            error.message
                        )
                    )

                else:

                    execute_span.set_status(
                        StatusCode.OK
                    )

                return result, error


                
            except asyncio.CancelledError:

                execute_span.set_attribute(
                    "tool.cancelled",
                    True
                )

                raise

            except asyncio.TimeoutError as exc:

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

                status = "error"
                
                execute_span.set_attribute(
                    "tool.error_code",
                    error.code
                )

                record_span_error(
                    execute_span,
                    exc
                )

                return None, error

            finally:

                duration = time.perf_counter() - start

                self.record_metrics(
                    tool_name,
                    status,
                    duration
                )



