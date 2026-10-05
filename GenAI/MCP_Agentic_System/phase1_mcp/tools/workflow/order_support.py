from __future__ import annotations
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from errors.framework import ErrorCode, StructuredError
from tools.base import ToolExecutor, ToolLevel, ToolMetadata
from tools.composed.order_customer import OrderCustomerContextTool
from tools.workflow.base import SequentialWorkflowTool, WorkflowStep


class OrderSupportWorkflowInput(BaseModel):
    order_id: int = Field(..., ge=1, description="Order identifier.")


class OrderSupportWorkflowTool(SequentialWorkflowTool):

    meta: ClassVar[ToolMetadata] = ToolMetadata(
        name="order_support_workflow",
        description=(
            "Build a support context for an order by retrieving its order and customer information."
        ),
        level=ToolLevel.WORKFLOW,
        cacheable=True,
        cache_ttl_seconds=30,
        timeout_ms=15_000,
        tags=("support", "order", "workflow"),
    )
    input_model: ClassVar[type[BaseModel]] = OrderSupportWorkflowInput

    def __init__(self, order_customer: OrderCustomerContextTool) -> None:
        super().__init__(
            steps=(
                WorkflowStep(
                    name="order_customer_context",
                    tool=order_customer,
                    build_arguments=lambda arguments, _results: {
                        "order_id": arguments["order_id"]
                    },
                ),
            ),
            result_builder=self._build_result,
        )

    async def run(
        self,
        executor: ToolExecutor,
        arguments: dict,
        deadline: float,
    ):
        order_id = arguments["order_id"]

        if order_id <= 0:
            return None, StructuredError(
                code=ErrorCode.INVALID_TOOL_ARGUMENTS,
                message="order_id must be greater than zero.",
                retryable=False,
                counts_toward_circuit_breaker=False,
            )

        return await super().run(
            executor=executor,
            arguments=arguments,
            deadline=deadline,
        )
    
    @staticmethod
    def _build_result(
        _arguments: dict[str, Any],
        results: dict[str, Any],
    ):
        return {
            "workflow": "order_support_workflow",
            "order_id": _arguments["order_id"],
            "status": "completed",
            "context": results["order_customer_context"],
        }
