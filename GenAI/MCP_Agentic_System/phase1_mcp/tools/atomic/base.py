from typing import Any

from tools.base import Tool, ToolExecutor, ToolLevel, ToolMetadata


class AtomicMCPTool(Tool):

    def __init__(self, mcp_tool) -> None:
        self.meta = ToolMetadata(
            name=mcp_tool.name,
            description=mcp_tool.description or "",
            level=ToolLevel.ATOMIC,
        )
        self._input_schema = mcp_tool.input_schema

    @property
    def input_schema(self) -> dict[str, Any]:
        return self._input_schema

    async def run(
        self,
        executor: ToolExecutor,
        arguments: dict[str, Any],
        deadline: float,
    ):
        return await executor._execute_with_deadline(
            self.meta.name,
            arguments,
            deadline,
        )
