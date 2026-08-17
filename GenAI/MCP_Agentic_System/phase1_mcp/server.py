from mcp.server.mcpserver import MCPServer
# from fastmcp import FastMCP

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
        }
    }

    order = orders.get(order_id)

    if order is None:
        return {
            "error": "Order not found"
        }
    
    return order

if __name__ == "__main__":
    mcp.run()