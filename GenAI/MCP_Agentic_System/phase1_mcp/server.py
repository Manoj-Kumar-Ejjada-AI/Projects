from mcp.server import FastMCP
# from fastmcp import FastMCP

mcp = FastMCP("Customer Server")

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
    "Return details of order"
    orders = {
        101: {
            "customer": "Manoj",
            "product": "Laptop",
            "status": "Shipped"
        },
        102: {
            "customer": "Manoj",
            "product": "Phone",
            "status": "Delivered"
        },
        103: {
            "customer": "Anil",
            "product": "Tab",
            "status": "Processing"
        }
    }

    if order_id is None:
        return {
            "error": "Order not found"
        }
    
    return orders[order_id]

if __name__ == "__main__":
    mcp.run()