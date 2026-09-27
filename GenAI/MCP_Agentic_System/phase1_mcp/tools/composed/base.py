from typing import Any

from tools.atomic.base import AtomicMCPTool
from tools.base import Tool, ToolExecutor


class ComposedTool(Tool):

    async def call_atomic(
        self,
        executor: ToolExecutor,
        atomic_tool: AtomicMCPTool,
        arguments: dict[str, Any],
        deadline: float,
    ):
        return await atomic_tool.run(
            executor=executor,
            arguments=arguments,
            deadline=deadline,
        )
