from typing import ClassVar

from pydantic import BaseModel, Field

from errors.framework import ErrorCode, StructuredError
from tools.base import ToolExecutor, ToolLevel, ToolMetadata
from tools.composed.order_customer import OrderCustomerContextTool
from tools.workflow.base import WorkflowTool


class OrderSupportWorkflowInput(BaseModel):
    order_id: int = Field(..., ge=1, description="Order identifier.")


class OrderSupportWorkflowTool(WorkflowTool):

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
        self.order_customer = order_customer

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

        context, error = await self.call_step(
            executor,
            self.order_customer,
            {"order_id": order_id},
            deadline,
        )
        if error is not None:
            return None, error

        return {
            "workflow": "order_support_workflow",
            "order_id": order_id,
            "status": "completed",
            "context": context,
        }, None
