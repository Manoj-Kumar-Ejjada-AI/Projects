from openai import AsyncOpenAI

import asyncio
from config import OPENAI_API_KEY, base_url

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json

server_params = StdioServerParameters(
    command="python",
    args=["server.py"]
)

async def call_tool(session, tool_name, arguments = None):
    if arguments == None:
        arguments = {}
    result = await session.call_tool(
        tool_name,
        arguments
    )
    return result

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
            messages=[
                    {
                        "role": "user",
                        "content": "what is the status of order 101"
                    }
                ]
            llm_response = await llm.chat.completions.create(
                model="gemini-3.6-flash",
                messages=messages,
                tools = openai_tools
            )

            # print(llm_response)
            message = llm_response.choices[0].message
            if message.tool_calls:
                messages.append(message)
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    print("Tool Name: ", tool_name)
                    print("arguments: ",arguments)
                    result = await call_tool(
                                        session=session,
                                        tool_name=tool_name,
                                        arguments=arguments)
                    # print(result)
                    result = str(result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                        })
                    
                llm_response = await llm.chat.completions.create(
                    model="gemini-3.6-flash",
                    messages=messages,
                    tools=openai_tools
                )
                print(llm_response.choices[0].message)



if __name__ == "__main__":
    asyncio.run(main())
