from errors.framework import ErrorCode, StructuredError

class ToolExecutor:
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client

    async def execute(self, tool_name, arguments):
        try:
            result = await self.mcp_client.call_tool(
                tool_name, 
                arguments
                )
            return result, None
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


