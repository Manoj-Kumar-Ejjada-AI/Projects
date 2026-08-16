from mcp import ClientSession

class MCPClient:
    def __init__(self, session):
        self.session = session

    async def list_tools(self):
        return await self.session.list_tools()

    async def call_tool(self, tool_name, arguments = None):
        if arguments == None:
            arguments = {}

        return await self.session.call_tool(
                                            tool_name,
                                            arguments
                                            )