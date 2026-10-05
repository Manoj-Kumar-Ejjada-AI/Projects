from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

from tools.base import Tool, ToolExecutor


ArgumentsBuilder = Callable[
    [dict[str, Any], dict[str, Any]],
    dict[str, Any],
]
ResultBuilder = Callable[
    [dict[str, Any], dict[str, Any]],
    Any,
]

@dataclass(frozen=True)
class WorkflowStep:
    
    name: str
    tool: Tool
    build_arguments: ArgumentsBuilder

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

class SequentialWorkflowTool(WorkflowTool):
    """Reusable implementation for deterministic sequential workflows.

    Workflows differ from composed tools in intent: they represent a larger
    business procedure. The execution mechanics remain deliberately simple:
    fixed step order, shared deadline, fail-fast error propagation.
    """

    def __init__(
        self,
        steps: tuple[WorkflowStep, ...],
        result_builder: ResultBuilder | None = None,
    ) -> None:
        if not steps:
            raise ValueError("A workflow must contain at least one step")

        step_names = [step.name for step in steps]
        if len(step_names) != len(set(step_names)):
            raise ValueError("Workflow step names must be unique")

        self.steps = steps
        self.result_builder = result_builder

    async def run(
        self,
        executor: ToolExecutor,
        arguments: dict[str, Any],
        deadline: float,
    ):
        """Execute workflow steps in order and stop at the first error."""
        results: dict[str, Any] = {}

        for step in self.steps:
            try:
                step_arguments = step.build_arguments(
                    arguments,
                    results,
                )
            except Exception as exc:
                from errors.framework import ErrorCode, StructuredError

                return None, StructuredError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=(
                        f"Failed to build arguments for workflow step "
                        f"'{step.name}'."
                    ),
                    retryable=False,
                    counts_toward_circuit_breaker=False,
                    details={"exception": str(exc)},
                )

            result, error = await self.call_step(
                executor,
                step.tool,
                step_arguments,
                deadline,
            )

            if error is not None:
                return None, error

            results[step.name] = result

        if self.result_builder is not None:
            try:
                result = self.result_builder(arguments, results)
            except Exception as exc:
                from errors.framework import ErrorCode, StructuredError

                return None, StructuredError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message="Failed to build workflow result.",
                    retryable=False,
                    counts_toward_circuit_breaker=False,
                    details={"exception": str(exc)},
                )
            return result, None

        return results, None