from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from contextlib import AsyncExitStack

class MCPClient:
    def __init__(self, server_params):
        """Accept stdio parameters or a Streamable HTTP URL.

        A string value means a Streamable HTTP endpoint, 
        while StdioServerParameters use the subprocess transport.
        """
        self.server_params = server_params
        self.session = None
        self.exit_stack = None


    async def __aenter__(self):
        self.exit_stack = AsyncExitStack()
        try:
            if isinstance(self.server_params, str):
                self.read, self.write = await self.exit_stack.enter_async_context(
                    streamable_http_client(self.server_params)
                )
            else:
                self.read, self.write = await self.exit_stack.enter_async_context(
                    stdio_client(self.server_params)
                )
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.read, self.write)
                )
            await self.session.initialize()
            return self
        except:
            await self.exit_stack.aclose()
            self.exit_stack = None
            self.session = None
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.exit_stack:
            await self.exit_stack.aclose()

    async def list_tools(self):
        return await self.session.list_tools()

    async def call_tool(self, tool_name, arguments = None):
        if arguments is None:
            arguments = {}

        result = await self.session.call_tool(
                                            tool_name,
                                            arguments
                                            )

        if result.is_error:
            raise RuntimeError(f"Error in executing tool {tool_name}")

        text_content = [
            content.text 
            for content in result.content 
            if content.type == "text"
            ]

        return "\n".join(text_content)