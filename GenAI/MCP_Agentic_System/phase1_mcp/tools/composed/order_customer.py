from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, Field

from tools.atomic.base import AtomicMCPTool
from tools.base import ToolLevel, ToolMetadata
from tools.composed.base import SequentialComposedTool, ToolStep


class OrderCustomerInput(BaseModel):
    order_id: int = Field(..., ge=1, description="Order identifier.")


class OrderCustomerContextTool(SequentialComposedTool):
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
        super().__init__(
            steps=(
                ToolStep(
                    name="get_order",
                    tool=get_order,
                    build_arguments=lambda arguments, _results: {
                        "order_id": arguments["order_id"]
                    },
                ),
                ToolStep(
                    name="get_customer",
                    tool=get_customer,
                    build_arguments=self._build_customer_arguments,
                ),
            ),
            result_builder=self._build_result,
        )

    @staticmethod
    def _build_customer_arguments(
        _arguments: dict[str, Any],
        results: dict[str, Any],
    ) -> dict[str, Any]:
        order_result = results.get("get_order")
        if not isinstance(order_result, dict) or order_result.get("customer_id") is None:
            raise ValueError("get_order did not return a customer_id")
        return {"customer_id": order_result["customer_id"]}

    @staticmethod
    def _build_result(
        _arguments: dict[str, Any],
        results: dict[str, Any],
    ):
        order_result = results["get_order"]

        return {
            "order": order_result,
            "customer": results["get_customer"],
        }
