from mcp import ClientSession
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

class MCPClient:
    def __init__(self, server_params):
        self.server_params = server_params
        self.session = None


    async def __aenter__(self):
        self.exit_stack = AsyncExitStack()
        self.read, self.write = await self.exit_stack.enter_async_context(stdio_client(self.server_params))
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.read, self.write))
        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.exit_stack:
            await self.exit_stack.aclose()

    async def list_tools(self):
        return await self.session.list_tools()

    async def call_tool(self, tool_name, arguments = None):
        if arguments == None:
            arguments = {}

        result = await self.session.call_tool(
                                            tool_name,
                                            arguments
                                            )

        if result.is_error:
            raise RuntimeError(f"Error in executing tool {tool_name}")

        result = [content.text for content in result.content if content.type == "text"]

        return "\n".join(result)