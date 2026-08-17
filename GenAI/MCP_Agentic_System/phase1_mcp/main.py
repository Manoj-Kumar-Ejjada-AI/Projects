from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters

from openai import AsyncOpenAI
from config import OPENAI_API_KEY, base_url
import asyncio

from agent import Agent
from mcp_client import MCPClient
from tool_registry import ToolRegistry

async def main():
    llm = AsyncOpenAI(
            api_key = OPENAI_API_KEY,
            base_url = base_url
        )

    model = "gemini-3.6-flash"

    server_params = StdioServerParameters(
        command="python",
        args=["server.py"]
    )
    async with MCPClient(server_params) as mcp_client:

        mcp_tools = await mcp_client.list_tools()

        tool_registry = ToolRegistry(mcp_tools.tools)

        agent = Agent(llm, model, mcp_client, tool_registry)

        user_message = input("Enter your query: ")

        response =await agent.run(user_message)

        print(response)

if __name__=="__main__":
    asyncio.run(main())