from typing import Any

from tools.base import Tool, ToolExecutor


class ComposedTool(Tool):

    async def call_child(
        self,
        executor: ToolExecutor,
        child_tool: Tool,
        arguments: dict[str, Any],
        deadline: float,
    ):
        return await child_tool.run(
            executor=executor,
            arguments=arguments,
            deadline=deadline,
        )
