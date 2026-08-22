from errors.framework import ErrorCode, StructuredError
import asyncio

class ToolExecutor:
    def __init__(self, 
                 mcp_client,
                 timeout_seconds=100,
                 retry_policy = None
                 ):
        self.mcp_client = mcp_client
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy


    async def _execute_once(self, tool_name, arguments):
        try:
            async with asyncio.timeout():
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
                message= "Tool Execution time Exceeded",
                retryable=True,
                details= {
                    "Timeout_seconds": self.timeout_seconds
                }
            )

            return None, error
        
        except Exception as exc:
            error = StructuredError(
                code = ErrorCode.TOOL_EXECUTION_ERROR,
                message= f"Tool '{tool_name}' failed.",
                retryable= False,
                details= {
                    "exception": str(exc)
                }
            )

            return None, error

    async def execute(self, tool_name, arguments):

        if self.retry_policy is None:
            return await self._execute_once(
                tool_name,
                arguments
            )
        return await self.retry_policy.execute(
            lambda: self._execute_once(
                tool_name,
                arguments
            )
        )


