
from typing import Any

from tools.composed.base import ComposedTool
from tools.base import Tool, ToolExecutor


class WorkflowTool(Tool):

    async def call_composed(
        self,
        executor: ToolExecutor,
        composed_tool: ComposedTool,
        arguments: dict[str, Any],
        deadline: float,
    ):
        return await composed_tool.run(
            executor=executor,
            arguments=arguments,
            deadline=deadline,
        )
