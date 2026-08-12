import asyncio

# MCP relies entirely on asynchronous programming. 
# Because the client has to wait for the server to spin up, process data, and send it back,
# it uses asyncio so your program doesn't freeze while waiting for those responses.

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ClientSession: This is the brain of the client. 
# It handles the actual MCP rules—formatting messages correctly, keeping track of request IDs, and managing the connection state.

# StdioServerParameters: A configuration object. It tells your client how to start the server.

# stdio_client: A tool that actually starts the server process on your computer and 
# creates the communication pipes between your client and that server.

serve_params = StdioServerParameters(
    command="python",
    args=["server.py"]
)

async def cal_tool_by_name(session, tool_name, arguments = None):

    if arguments == None:
        arguments = {}

    result = await session.call_tool(
        tool_name,
        arguments
        )
    return result

async def get_available_tools(session):
    tools_available = await session.list_tools()

    print("Available tools are:")
    for tool in tools_available.tools:
        print("Tool name:\n",tool.name)
        print("Description:\n", tool.description)
        print("Input Schema:\n", tool.input_schema)

async def get_tool_args(session, tool_name):
    tools_available = await session.list_tools()
    list_of_args = []
    for tool in tools_available.tools:
        if tool.name == tool_name:
            for each_key in tool.input_schema["properties"].keys():
                list_of_args.append(each_key)
    return list_of_args


async def main():
    async with stdio_client(serve_params) as (read,write):
        async with ClientSession(read, write) as session:
            await session.initialize()
                                        
                
            await get_available_tools(session)
            user_input = input("Enter tool name:")
            _args = await get_tool_args(session, user_input) 
            user_args = None
            for each_arg in (_args):
                user_args = {}
                print("Enter", each_arg,":")
                arg = int(input())
                user_args[each_arg] = arg

            result1 = await cal_tool_by_name(session=session, tool_name=user_input, arguments=user_args) 
            print("\n-------------")
            print("Result is \n",result1)


if __name__ == "__main__":
    asyncio.run(main())
