class ToolRegistry:
    def __init__(self, mcp_tools):
        self.mcp_tools = {
            tool.name: tool 
            for tool in mcp_tools
        }

    def get_llm_tools(self):
        llm_tools = []
        for tool in self.mcp_tools.values():
            llm_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema
                }
            })
        return llm_tools

    def has_tool(self, tool_name):
        return tool_name in self.mcp_tools

    def get_tool(self, tool_name):
        return self.mcp_tools.get(tool_name)
