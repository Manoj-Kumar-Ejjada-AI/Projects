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

from cache.manager import CacheManager
from reliability.circuitBreaker import CircuitBreaker
from ratelimit.limiter import RateLimiter

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

        cache_manager = CacheManager(
            redis_url="redis://localhost:6379",
            metrics=metrics_registry
        )

        rate_limiter = RateLimiter(
                redis_url="redis://localhost:6379/0",
                )

        try:

            await cache_manager.connect()

            await rate_limiter.connect()

            start_http_server(
                8000,
                registry=metrics_registry.registry
            )

            

            await rate_limiter.connect()

            circuit_breaker = CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=30,
            )


            tool_executor = ToolExecutor(
                mcp_client=mcp_client,
                metrics=metrics_registry,
                cache_manager=cache_manager,
                circuit_breaker=circuit_breaker,
                rate_limiter=rate_limiter
                )

            agent = Agent(llm, model, tool_executor, tool_registry)

            while True:

                user_message = input("Enter your query: ")

                if user_message.lower() == "exit":
                    break

                response = await agent.run(user_message)

                print(response)

        finally:
            await cache_manager.disconnect()
            await rate_limiter.disconnect() 


if __name__=="__main__":
    asyncio.run(main())