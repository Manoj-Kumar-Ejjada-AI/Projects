from openai import AsyncOpenAI

import asyncio
from config import OPENAI_API_KEY, base_url

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["server.py"]
)

async def main():
    llm = AsyncOpenAI(
        api_key = OPENAI_API_KEY,
        base_url = base_url
    )
    async with stdio_client(server_params) as (read,write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()

            openai_tools = []

            for tool in tools.tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.input_schema
                        }
                    }
                )

            llm_response = await llm.chat.completions.create(
                model="gemini-3.6-flash",
                messages=[
                    {
                        "role": "user",
                        "content": "what is the status of order 101"
                    }
                ],
                tools = openai_tools
            )

            print(llm_response)

if __name__ == "__main__":
    asyncio.run(main())
