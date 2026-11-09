"""
Chapter 04 solution - shop MCP server mounted in a Starlette (ASGI) app.

Uses the official MCP Python SDK v2 (pip install "mcp[cli]>=2"):
  - FastMCP class is now MCPServer  (from mcp.server import MCPServer)
  - Serves BOTH transports from the same server:
      Streamable HTTP (current) -> http://127.0.0.1:3000/mcp
      SSE (legacy, old clients) -> http://127.0.0.1:3000/sse

Run:   uvicorn server:app --port 3000
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import List

from pydantic import BaseModel
from starlette.applications import Starlette

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("My App")


class Product(BaseModel):
    id: int
    name: str
    price: float
    description: str
    category: str


class CartItem(BaseModel):
    cart_id: int
    product_id: int
    quantity: int


products = [
    {
        "id": 1,
        "name": "Product 1",
        "price": 10.0,
        "description": "Description of Product 1",
        "category": "Category 1",
    },
    {
        "id": 2,
        "name": "Product 2",
        "price": 20.0,
        "description": "Description of Product 2",
        "category": "Category 2",
    },
    {
        "id": 3,
        "name": "Product 3",
        "price": 30.0,
        "description": "Description of Product 3",
        "category": "Category 3",
    },
]

cart: List[CartItem] = []


# get products by category
@mcp.tool()
def get_products_by_category(category: str) -> List[Product]:
    """Get products by category"""
    return [Product(**p) for p in products if p["category"] == category]


# add product to cart
@mcp.tool()
def add_product_to_cart(product_name: str) -> CartItem:
    """Add product to cart"""
    product = next((p for p in products if p["name"] == product_name), None)
    if not product:
        # ToolError -> result with isError: true and this message shown to the client
        raise ToolError(f"Product [{product_name}] not found")
    cart_item = CartItem(cart_id=1, product_id=product["id"], quantity=1)
    cart.append(cart_item)
    return cart_item


# list cart
@mcp.tool()
def list_cart() -> List[CartItem]:
    """List all cart items"""
    return cart


# all products
@mcp.tool()
def get_products() -> List[Product]:
    """Get all products"""
    return [Product(**p) for p in products]


# The host app's lifespan must start the Streamable HTTP session manager
# (the MCP server's own lifespan does not run inside another app).
# SSE needs no session manager.
@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        yield


# Build both transport apps from the same MCP server (same tools).
streamable_app = mcp.streamable_http_app()  # route: /mcp
sse_app = mcp.sse_app()                     # routes: /sse and /messages/

# Combine their routes into one Starlette app.
# (Two Mount("/") entries would not work: the first one catches every path.)
app = Starlette(
    routes=[
        *streamable_app.routes,
        *sse_app.routes,
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    # Alternative to uvicorn, serving both transports
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3000)
