from __future__ import annotations
from mcp.server.mcpserver import MCPServer
# from fastmcp import FastMCP
import asyncio

import argparse
import os
from typing import Literal

Transport = Literal["stdio", "streamable-http"]

# mcp = MCPServer("Customer Server")

def build_server() -> MCPServer:
    mcp = MCPServer("Customer Server")

    @mcp.tool()
    def get_customer(customer_id: int) -> dict:
        """get customer information by customer id"""

        customers = {
            1: {
                "id" : 1,
                "name": "Manoj",
                "email": "manoj@customer.com"
            },
            2: {
                "id": 2,
                "name": "Anil",
                "email": "Anil@customer.com"
            },
            3: {
                "id": 3,
                "name": "Kishore",
                "email": "kishore@customer.com"
            }
        }

        customer = customers[customer_id]

        if customer is None:
            return {
                "error": "Customer is not found"
            }

        return customer


    @mcp.tool()
    def list_customers() -> list:
        """Return all customers"""

        return [
            {
                "id": 1,
                "name": "Manoj",
                "email": "manoj@customer.com"
            },
            {
                "id": 2,
                "name": "Anil",
                "email": "anil@customer.com"
            },
            {
                "id": 3,
                "name": "Kishore",
                "email": "kishore@customer.com"
            }
        ]

    @mcp.tool()
    def get_order(order_id: int) -> dict:
        """Return details of order by order id"""
        orders = {
            101: {
                "customer_id": 1,
                "product": "Laptop",
                "status": "Shipped"
            },
            102: {
                "customer_id": 1,
                "product": "Phone",
                "status": "Delivered"
            },
            103: {
                "customer_id": 2,
                "product": "Tab",
                "status": "Processing"
            },
            104: {
                "customer_id": 3,
                "product": "Tab",
                "status": "rate_test"
            },
            105: {
                "customer_id": 3,
                "product": "Tab",
                "status": "circuit_test"
            },
            106: {
                "customer_id": 3,
                "product": "Tab",
                "status": "Processing"
            }
        }

        order = orders.get(order_id)

        if order is None:
            return {
                "error": "Order not found"
            }
        
        return order
        # raise ConnectionError("Simulated downstream database failure")

    @mcp.tool()
    async def slow_tool(delay: float = 0.0):
        "Execute slow tool and get response"
        await asyncio.sleep(delay)
        return {"status": "completed"}

    return mcp

mcp = build_server()


def run_server(
    transport: Transport = "stdio",
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    streamable_http_path: str = "/mcp",
    stateless_http: bool = True,
    max_request_body_size: int = 4 * 1024 * 1024,
) -> None:
    """Run the MCP server using the selected transport.

    stdio remains the default for local development.
    Streamable HTTP is configured in stateless mode for remote deployments.
    """
    if transport == "stdio":
        mcp.run(transport="stdio")
        return

    if transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=host,
            port=port,
            streamable_http_path=streamable_http_path,
            stateless_http=stateless_http,
            max_request_body_size=max_request_body_size,
        )
        return

    raise ValueError(
        f"Unsupported transport {transport!r}; "
        "expected 'stdio' or 'streamable-http'"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the production MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="MCP transport to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="HTTP bind host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8080")),
        help="HTTP port (default: 8080)",
    )
    parser.add_argument(
        "--path",
        dest="streamable_http_path",
        default=os.getenv("MCP_STREAMABLE_HTTP_PATH", "/mcp"),
        help="Streamable HTTP endpoint path (default: /mcp)",
    )
    parser.add_argument(
        "--stateful-http",
        action="store_true",
        help="Use stateful Streamable HTTP sessions instead of stateless mode",
    )
    parser.add_argument(
        "--max-request-body-size",
        type=int,
        default=int(os.getenv("MCP_MAX_REQUEST_BODY_SIZE", str(4 * 1024 * 1024))),
        help="Maximum Streamable HTTP request body size in bytes",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stateless_http = not args.stateful_http

    run_server(
        transport=args.transport,
        host=args.host,
        port=args.port,
        streamable_http_path=args.streamable_http_path,
        stateless_http=stateless_http,
        max_request_body_size=args.max_request_body_size,
    )

if __name__ == "__main__":
    main()