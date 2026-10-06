import asyncio

from pydantic import BaseModel

from tools.atomic.base import AtomicMCPTool
from tools.base import Tool, ToolExecutor, ToolLevel, ToolMetadata
from tools.composed.order_customer import OrderCustomerContextTool
from tools.workflow.order_support import OrderSupportWorkflowTool


class FakeMCPToolSpec:
    def __init__(self, name, description, input_schema):
        self.name = name
        self.description = description
        self.input_schema = input_schema


class FakeMCPClient:
    def __init__(self):
        self.calls = []

    async def call_tool(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        if tool_name == "get_order":
            return {
                "customer_id": 1,
                "product": "Laptop",
                "status": "Shipped",
            }
        if tool_name == "get_customer":
            return {
                "id": arguments["customer_id"],
                "name": "Manoj",
                "email": "manoj@customer.com",
            }
        raise AssertionError(f"Unexpected tool: {tool_name}")


def make_hierarchy():
    order_spec = FakeMCPToolSpec(
        "get_order",
        "Return details of an order",
        {"type": "object", "properties": {"order_id": {"type": "integer"}}},
    )
    customer_spec = FakeMCPToolSpec(
        "get_customer",
        "Return customer information",
        {"type": "object", "properties": {"customer_id": {"type": "integer"}}},
    )
    return (
        AtomicMCPTool(order_spec),
        AtomicMCPTool(customer_spec),
    )


def make_executor():
    client = FakeMCPClient()
    executor = ToolExecutor(
        mcp_client=client,
        overall_timeout_seconds=5,
        timeout_seconds=2,
    )
    return executor, client


def test_metadata_levels():
    order_atomic, _ = make_hierarchy()
    composed = OrderCustomerContextTool(order_atomic, make_hierarchy()[1])
    workflow = OrderSupportWorkflowTool(composed)

    assert order_atomic.meta.level is ToolLevel.ATOMIC
    assert composed.meta.level is ToolLevel.COMPOSED
    assert workflow.meta.level is ToolLevel.WORKFLOW


def test_composed_tool_delegates_atomic_calls_to_executor():
    async def _run():
        executor, client = make_executor()
        order_atomic, customer_atomic = make_hierarchy()
        tool = OrderCustomerContextTool(order_atomic, customer_atomic)
        executor.local_tools[tool.meta.name] = tool
        return await executor.execute(tool.meta.name, {"order_id": 101})

    result, error = asyncio.run(_run())
    assert error is None
    assert result["order"]["status"] == "Shipped"
    assert result["customer"]["name"] == "Manoj"


def test_workflow_delegates_to_composed_and_keeps_single_flow():
    async def _run():
        executor, client = make_executor()
        order_atomic, customer_atomic = make_hierarchy()
        composed = OrderCustomerContextTool(order_atomic, customer_atomic)
        workflow = OrderSupportWorkflowTool(composed)
        executor.local_tools[workflow.meta.name] = workflow
        result, error = await executor.execute(
            workflow.meta.name,
            {"order_id": 101},
        )
        return result, error, client

    result, error, client = asyncio.run(_run())
    assert error is None
    assert result["status"] == "completed"
    assert result["context"]["customer"]["id"] == 1
    assert [name for name, _ in client.calls] == ["get_order", "get_customer"]


def test_registry_exposes_local_hierarchy_tools_to_llm():
    from tool_registry import ToolRegistry

    class MCPToolSpec:
        name = "get_order"
        description = "Get order"
        input_schema = {
            "type": "object",
            "properties": {"order_id": {"type": "integer"}},
        }

    order_atomic, customer_atomic = make_hierarchy()
    composed = OrderCustomerContextTool(order_atomic, customer_atomic)
    workflow = OrderSupportWorkflowTool(composed)

    registry = ToolRegistry([MCPToolSpec()])
    registry.register_local_tool(composed)
    registry.register_local_tool(workflow)

    names = [
        entry["function"]["name"]
        for entry in registry.get_llm_tools()
    ]

    assert names == [
        "get_order",
        "order_customer_context",
        "order_support_workflow",
    ]
    assert registry.has_tool("order_customer_context")
    assert registry.get_tool("order_support_workflow") is workflow

    workflow_definition = next(
        entry for entry in registry.get_llm_tools()
        if entry["function"]["name"] == "order_support_workflow"
    )
    assert workflow_definition["function"]["parameters"]["required"] == [
        "order_id"
    ]


class DummyInput(BaseModel):
    value: int


class RecordingTool(Tool):
    meta = ToolMetadata(
        name="recording_tool",
        description="Records the deadline it receives.",
        level=ToolLevel.ATOMIC,
    )
    input_model = DummyInput

    def __init__(self):
        self.deadlines = []

    async def run(self, executor, arguments, deadline):
        self.deadlines.append(deadline)
        return {"value": arguments["value"]}, None


class RecordingComposedTool(Tool):
    meta = ToolMetadata(
        name="recording_composed",
        description="A test composed tool.",
        level=ToolLevel.COMPOSED,
    )
    input_model = DummyInput

    def __init__(self, first, second):
        self.first = first
        self.second = second

    async def run(self, executor, arguments, deadline):
        first_result, first_error = await self.first.run(
            executor, {"value": arguments["value"]}, deadline
        )
        if first_error is not None:
            return None, first_error

        second_result, second_error = await self.second.run(
            executor, {"value": arguments["value"] + 1}, deadline
        )
        if second_error is not None:
            return None, second_error

        return {"first": first_result, "second": second_result}, None


def test_executor_registration_rejects_duplicate_local_tools():
    async def _run():
        executor, _ = make_executor()
        order_atomic, customer_atomic = make_hierarchy()
        tool = OrderCustomerContextTool(order_atomic, customer_atomic)
        executor.register_local_tool(tool)
        try:
            executor.register_local_tool(tool)
        except ValueError as exc:
            return str(exc)
        raise AssertionError("Expected duplicate registration to fail")

    message = asyncio.run(_run())
    assert "already registered" in message


def test_composed_children_receive_the_same_absolute_deadline():
    async def _run():
        executor, _ = make_executor()
        first = RecordingTool()
        second = RecordingTool()
        composed = RecordingComposedTool(first, second)

        executor.register_local_tool(composed)
        result, error = await executor.execute(
            "recording_composed",
            {"value": 10},
        )
        return result, error, first.deadlines, second.deadlines

    result, error, first_deadlines, second_deadlines = asyncio.run(_run())

    assert error is None
    assert result["first"]["value"] == 10
    assert result["second"]["value"] == 11
    assert len(first_deadlines) == 1
    assert len(second_deadlines) == 1
    assert first_deadlines[0] == second_deadlines[0]


def test_sequential_composed_tool_runs_generic_steps_in_order():
    async def _run():
        executor, client = make_executor()
        order_atomic, customer_atomic = make_hierarchy()

        from tools.composed.base import SequentialComposedTool, ToolStep

        composed = SequentialComposedTool(
            steps=(
                ToolStep(
                    name="order",
                    tool=order_atomic,
                    build_arguments=lambda arguments, _results: {
                        "order_id": arguments["value"]
                    },
                ),
                ToolStep(
                    name="customer",
                    tool=customer_atomic,
                    build_arguments=lambda _arguments, results: {
                        "customer_id": results["order"]["customer_id"]
                    },
                ),
            ),
        )

        composed.meta = ToolMetadata(
            name="generic_context",
            description="Generic deterministic composition test.",
            level=ToolLevel.COMPOSED,
        )
        composed.input_model = DummyInput

        executor.register_local_tool(composed)
        return await executor.execute(
            "generic_context",
            {"value": 101},
        ), client.calls

    (result, error), calls = asyncio.run(_run())

    assert error is None
    assert result["order"]["status"] == "Shipped"
    assert result["customer"]["name"] == "Manoj"
    assert [name for name, _ in calls] == ["get_order", "get_customer"]


def test_sequential_composed_tool_stops_after_child_error():
    class FailingTool(Tool):
        meta = ToolMetadata(
            name="failing_child",
            description="Always fails.",
            level=ToolLevel.ATOMIC,
        )
        input_model = DummyInput

        async def run(self, executor, arguments, deadline):
            from errors.framework import ErrorCode, StructuredError

            return None, StructuredError(
                code=ErrorCode.TOOL_EXECUTION_ERROR,
                message="child failed",
                retryable=False,
                counts_toward_circuit_breaker=False,
            )

    class RecordingTool(Tool):
        meta = ToolMetadata(
            name="should_not_run",
            description="Should never be reached.",
            level=ToolLevel.ATOMIC,
        )
        input_model = DummyInput

        def __init__(self):
            self.called = False

        async def run(self, executor, arguments, deadline):
            self.called = True
            return {"ok": True}, None

    async def _run():
        executor, _ = make_executor()
        failing = FailingTool()
        should_not_run = RecordingTool()

        from tools.composed.base import SequentialComposedTool, ToolStep

        composed = SequentialComposedTool(
            steps=(
                ToolStep(
                    name="fail",
                    tool=failing,
                    build_arguments=lambda arguments, _results: arguments,
                ),
                ToolStep(
                    name="never",
                    tool=should_not_run,
                    build_arguments=lambda arguments, _results: arguments,
                ),
            )
        )
        composed.meta = ToolMetadata(
            name="stop_on_error",
            description="Stops when a child fails.",
            level=ToolLevel.COMPOSED,
        )
        composed.input_model = DummyInput

        executor.register_local_tool(composed)
        result, error = await executor.execute(
            "stop_on_error",
            {"value": 1},
        )
        return result, error, should_not_run.called

    result, error, called = asyncio.run(_run())

    assert result is None
    assert error is not None
    assert error.code == "TOOL_EXECUTION_ERROR"
    assert called is False


def test_sequential_composed_tool_rejects_duplicate_step_names():
    from tools.composed.base import SequentialComposedTool, ToolStep

    order_atomic, _ = make_hierarchy()

    try:
        SequentialComposedTool(
            steps=(
                ToolStep(
                    name="same",
                    tool=order_atomic,
                    build_arguments=lambda arguments, _results: arguments,
                ),
                ToolStep(
                    name="same",
                    tool=order_atomic,
                    build_arguments=lambda arguments, _results: arguments,
                ),
            )
        )
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("Expected duplicate step names to fail")


def test_sequential_workflow_tool_runs_generic_steps():
    async def _run():
        executor, client = make_executor()
        order_atomic, customer_atomic = make_hierarchy()

        from tools.workflow.base import SequentialWorkflowTool, WorkflowStep

        workflow = SequentialWorkflowTool(
            steps=(
                WorkflowStep(
                    name="order",
                    tool=order_atomic,
                    build_arguments=lambda arguments, _results: {
                        "order_id": arguments["value"]
                    },
                ),
                WorkflowStep(
                    name="customer",
                    tool=customer_atomic,
                    build_arguments=lambda _arguments, results: {
                        "customer_id": results["order"]["customer_id"]
                    },
                ),
            ),
        )

        workflow.meta = ToolMetadata(
            name="generic_workflow",
            description="Generic deterministic workflow test.",
            level=ToolLevel.WORKFLOW,
        )
        workflow.input_model = DummyInput

        executor.register_local_tool(workflow)
        return await executor.execute(
            "generic_workflow",
            {"value": 101},
        ), client.calls

    (result, error), calls = asyncio.run(_run())

    assert error is None
    assert result["order"]["status"] == "Shipped"
    assert result["customer"]["id"] == 1
    assert [name for name, _ in calls] == ["get_order", "get_customer"]


def test_sequential_workflow_rejects_duplicate_step_names():
    from tools.workflow.base import SequentialWorkflowTool, WorkflowStep

    order_atomic, _ = make_hierarchy()

    try:
        SequentialWorkflowTool(
            steps=(
                WorkflowStep(
                    name="same",
                    tool=order_atomic,
                    build_arguments=lambda arguments, _results: arguments,
                ),
                WorkflowStep(
                    name="same",
                    tool=order_atomic,
                    build_arguments=lambda arguments, _results: arguments,
                ),
            )
        )
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("Expected duplicate workflow step names to fail")
