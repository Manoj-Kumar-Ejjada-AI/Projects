
from typing import Any

from tools.base import Tool, ToolExecutor


class WorkflowTool(Tool):

    async def call_step(
        self,
        executor: ToolExecutor,
        step_tool: Tool,
        arguments: dict[str, Any],
        deadline: float,
    ):
        return await step_tool.run(
            executor=executor,
            arguments=arguments,
            deadline=deadline,
        )
