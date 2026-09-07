from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters

from openai import AsyncOpenAI
from config import OPENAI_API_KEY, base_url
import asyncio

from agent import Agent
from mcp_client import MCPClient
from tool_registry import ToolRegistry
from tools.base import ToolExecutor

from observability.tracing import init_tracing
from observability.metrics import MetricsRegistry
from prometheus_client import start_http_server

async def main():

    init_tracing(
        "mcp-agentic-system",
        # "http://localhost:4317"
    )

    llm = AsyncOpenAI(
            api_key = OPENAI_API_KEY,
            base_url = base_url
        )

    # model = "gemini-3.6-flash"
    model = "gemma-4-31b-it"

    server_params = StdioServerParameters(
        command="python",
        args=["server.py"]
    )
    async with MCPClient(server_params) as mcp_client:

        mcp_tools = await mcp_client.list_tools()

        tool_registry = ToolRegistry(mcp_tools.tools)

        metrics_registry = MetricsRegistry()

        start_http_server(
            8000,
            registry=metrics_registry.registry
        )


        tool_executor = ToolExecutor(
            mcp_client=mcp_client,
            metrics=metrics_registry
            )

        agent = Agent(llm, model, tool_executor, tool_registry)

        user_message = input("Enter your query: ")

        response = await agent.run(user_message)

        print(response)

if __name__=="__main__":
    asyncio.run(main())