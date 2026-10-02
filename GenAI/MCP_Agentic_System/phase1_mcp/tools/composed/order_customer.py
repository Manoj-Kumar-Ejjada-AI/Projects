from typing import ClassVar

from pydantic import BaseModel, Field

from errors.framework import ErrorCode, StructuredError
from tools.atomic.base import AtomicMCPTool
from tools.base import ToolExecutor, ToolLevel, ToolMetadata
from tools.composed.base import ComposedTool


class OrderCustomerInput(BaseModel):
    order_id: int = Field(..., ge=1, description="Order identifier.")


class OrderCustomerContextTool(ComposedTool):
    """Deterministically execute Atomic get_order -> Atomic get_customer."""

    meta: ClassVar[ToolMetadata] = ToolMetadata(
        name="order_customer_context",
        description=(
            "Retrieve an order and its associated customer as one deterministic operation."
        ),
        level=ToolLevel.COMPOSED,
        cacheable=True,
        cache_ttl_seconds=60,
        timeout_ms=10_000,
        tags=("order", "customer", "composed"),
    )
    input_model: ClassVar[type[BaseModel]] = OrderCustomerInput

    def __init__(
        self,
        get_order: AtomicMCPTool,
        get_customer: AtomicMCPTool,
    ) -> None:
        self.get_order = get_order
        self.get_customer = get_customer

    async def run(
        self,
        executor: ToolExecutor,
        arguments: dict,
        deadline: float,
    ):
        order_result, error = await self.call_child(
            executor,
            self.get_order,
            {"order_id": arguments["order_id"]},
            deadline,
        )
        if error is not None:
            return None, error

        customer_id = (
            order_result.get("customer_id")
            if isinstance(order_result, dict)
            else None
        )
        if customer_id is None:
            return None, StructuredError(
                code=ErrorCode.INTERNAL_ERROR,
                message="get_order did not return a customer_id.",
                retryable=False,
                counts_toward_circuit_breaker=False,
            )

        customer_result, error = await self.call_child(
            executor,
            self.get_customer,
            {"customer_id": customer_id},
            deadline,
        )
        if error is not None:
            return None, error

        return {
            "order": order_result,
            "customer": customer_result,
        }, None
