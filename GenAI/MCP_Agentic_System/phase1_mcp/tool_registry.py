class ToolRegistry:
    def __init__(self, mcp_tools):
        self.mcp_tools = mcp_tools

    def get_llm_tools(self):
        llm_tools = []
        for tool in self.mcp_tools:
            llm_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema
                }
            })
        return llm_tools
