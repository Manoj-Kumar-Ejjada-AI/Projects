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


async def main():
    async with stdio_client(serve_params) as (read,write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # tools = await session.list_tools()

            # print("Available Tools: ")

            # for tool in tools.tools:
            #     print("\n--------------------")

            #     print( tool.name)
            #     # print("\n Description:")
            #     # print(tool.description)
            #     # print("\n Input Schema:")
            #     # print(tool.input_schema)

            # result = await session.call_tool(
            #     "get_customer",
            #     {
            #         "customer_id":1
            #         }
            # )
            
            # print("Result")
            # print(result.content)

            # get_order = await session.call_tool(
            #     "get_order",
            #     {
            #         "order_id": 1
            #     }
            # )
            # print("Order 101 details: ")
            # print(get_order)

            # customers_list = await session.call_tool(
            #     "list_customers"
            # )

            # print("Customers are: ")
            # print(customers_list)

            async def call_tool(session, tool_name, arguments = None):
                if arguments is None:
                    result = await session.call_tool(
                        tool_name
                    )
                else:
                    result = await session.call_tool(
                        tool_name,
                        arguments
                    )
                return result
            print("\n------------------------")
            answer1 = await call_tool(session=session, tool_name="list_customers")
            print("\n------------------------")
            answer2 = await call_tool(session=session, tool_name="get_order", arguments={"order_id":101})
            print("Result by function:")
            print(answer1)
            print("Result by function:")
            print(answer2)


if __name__ == "__main__":
    asyncio.run(main())
