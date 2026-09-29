from typing import Any

class ToolRegistry:
    def __init__(self, mcp_tools):
        self.mcp_tools = {
            tool.name: tool 
            for tool in mcp_tools
        }

        self.local_tools: dict[str: Any] = {}

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

    def register_local_tool(self, tool) -> None:
        if tool.meta.name in self.mcp_tools:
            raise ValueError(
                f"local tool '{tool.meta.name}' conflicts with an MCP tool"
            )
        if tool.meta.name in self.local_tools:
            raise ValueError(
                f"local tool '{tool.meta.name}' already registered"
            )
        self.local_tools[tool.meta.name] = tool

    def has_tool(self, tool_name):
        return tool_name in self.mcp_tools

    def get_tool(self, tool_name):
        return self.mcp_tools.get(tool_name)
