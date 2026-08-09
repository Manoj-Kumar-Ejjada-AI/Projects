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

            tools = await session.list_tools()

            print("Available Tools: ")
            for tool in tools.tools:
                print("-", tool.name)

            result = await session.call_tool(
                "get_customer",
                {
                    "customer_id":1
                    }
            )
            
            print("Result")
            print(result.content)

            get_order = await session.call_tool(
                "get_order",
                {
                    "order_id": 101
                }
            )
            print("Order 101 details: ")
            print(get_order)

            customers_list = await session.call_tool(
                "list_customers"
            )

            print("Customers are: ")
            print(customers_list)


if __name__ == "__main__":
    asyncio.run(main())
