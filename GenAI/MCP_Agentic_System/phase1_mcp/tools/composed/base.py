from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from errors.framework import ErrorCode, StructuredError
from tools.base import Tool, ToolExecutor


ArgumentsBuilder = Callable[
    [dict[str, Any], dict[str, Any]],
    dict[str, Any],
]

ResultBuilder = Callable[
    [dict[str, Any], dict[str, Any]],
    Any,
]

@dataclass(frozen = True)
class ToolStep:
    name: str
    tool: Tool
    build_arguments: ArgumentsBuilder
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


class SequentialComposedTool(ComposedTool):
    """Reusable deterministic implementation for sequential composition."""

    def __init__(
        self,
        steps: tuple[ToolStep, ...],
        result_builder: ResultBuilder | None = None,
    ) -> None:
        if not steps:
            raise ValueError("A composed tool must contain at least one step")

        step_names = [step.name for step in steps]

        if len(step_names) != len(set(step_names)):
            raise ValueError("Composed tool step names must be unique")

        self.steps = steps
        self.result_builder = result_builder

    async def run(
        self,
        executor: ToolExecutor,
        arguments: dict[str, Any],
        deadline: float,
    ):
        """Execute every step in order and stops immediately on the first error."""
        results: dict[str, Any] = {}

        for step in self.steps:
            try:
                step_arguments = step.build_arguments(
                    arguments,
                    results,
                )
            except Exception as exc:
                return None, StructuredError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=(
                        f"Failed to build arguments for composed step "
                        f"'{step.name}'."
                    ),
                    retryable=False,
                    counts_toward_circuit_breaker=False,
                    details={"exception": str(exc)},
                )

            result, error = await self.call_child(
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
                    message="Failed to build composed tool result.",
                    retryable=False,
                    counts_toward_circuit_breaker=False,
                    details={"exception": str(exc)},
                )
            return result, None

        return results, None