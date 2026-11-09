"""
Chapter 04 solution - shop MCP server mounted in a Starlette (ASGI) app.

Uses the official MCP Python SDK v2 (pip install "mcp[cli]>=2"):
  - FastMCP class is now MCPServer  (from mcp.server import MCPServer)
  - Serves BOTH transports from the same server:
      Streamable HTTP (current) -> http://127.0.0.1:3000/mcp
      SSE (legacy, old clients) -> http://127.0.0.1:3000/sse

Shows all three MCP building blocks:
  - Tools     : actions the model can call (browse products, manage the cart)
  - Resources : read-only data the client can load (catalogue, cart)
  - Prompts   : reusable prompt templates (shopping assistant)

Run:   uvicorn server:app --port 3000 --reload
Test:  python client.py          (in a second terminal)
       mcp dev server.py         (Inspector UI over stdio)
"""

import json
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

mcp = MCPServer(
    "My App",
    instructions=(
        "A demo shop. Use get_products or list_categories to browse, "
        "add_product_to_cart to buy, and get_cart_total to check out."
    ),
)


# ---------------------------------------------------------------------------
# Models (Pydantic models become the tools' input/output JSON schemas)
# ---------------------------------------------------------------------------

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


class CartLine(BaseModel):
    product_id: int
    name: str
    unit_price: float
    quantity: int
    line_total: float


class CartSummary(BaseModel):
    items: List[CartLine]
    item_count: int
    total: float


# ---------------------------------------------------------------------------
# In-memory data (resets every time the server restarts)
# ---------------------------------------------------------------------------

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

CART_ID = 1  # single shared cart for this demo
cart: List[CartItem] = []

# Hints that tell clients a tool only reads data (safe to call freely)
READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_product(name: str) -> dict:
    """Find a product by name, ignoring case and extra spaces."""
    wanted = name.strip().lower()
    product = next((p for p in products if p["name"].lower() == wanted), None)
    if not product:
        names = ", ".join(p["name"] for p in products)
        # ToolError -> result with isError: true and this message shown to the client
        raise ToolError(f"Product [{name}] not found. Available: {names}")
    return product


def _cart_summary() -> CartSummary:
    lines = []
    for item in cart:
        p = next(p for p in products if p["id"] == item.product_id)
        lines.append(
            CartLine(
                product_id=p["id"],
                name=p["name"],
                unit_price=p["price"],
                quantity=item.quantity,
                line_total=round(p["price"] * item.quantity, 2),
            )
        )
    return CartSummary(
        items=lines,
        item_count=sum(line.quantity for line in lines),
        total=round(sum(line.line_total for line in lines), 2),
    )


# ---------------------------------------------------------------------------
# Tools - browsing (original tools, same names and arguments)
# ---------------------------------------------------------------------------

# all products
@mcp.tool(annotations=READ_ONLY)
def get_products() -> List[Product]:
    """Get all products"""
    return [Product(**p) for p in products]


# get products by category
@mcp.tool(annotations=READ_ONLY)
def get_products_by_category(
    category: Annotated[str, Field(description="Category name, e.g. 'Category 1' (case-insensitive)")],
) -> List[Product]:
    """Get products by category"""
    wanted = category.strip().lower()
    return [Product(**p) for p in products if p["category"].lower() == wanted]


# NEW: list categories so the model knows what to ask for
@mcp.tool(annotations=READ_ONLY)
def list_categories() -> List[str]:
    """List all product categories"""
    return sorted({p["category"] for p in products})


# NEW: look up one product by id
@mcp.tool(annotations=READ_ONLY)
def get_product(
    product_id: Annotated[int, Field(description="Product id, e.g. 1")],
) -> Product:
    """Get a single product by its id"""
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        raise ToolError(f"Product with id [{product_id}] not found")
    return Product(**product)


# ---------------------------------------------------------------------------
# Tools - cart
# ---------------------------------------------------------------------------

# add product to cart (original tool; quantity is new and optional)
@mcp.tool()
def add_product_to_cart(
    product_name: Annotated[str, Field(description="Exact product name, e.g. 'Product 1' (case-insensitive)")],
    quantity: Annotated[int, Field(ge=1, le=100, description="How many to add (default 1)")] = 1,
) -> CartItem:
    """Add product to cart. Adding the same product again increases its quantity."""
    product = _find_product(product_name)
    existing = next((i for i in cart if i.product_id == product["id"]), None)
    if existing:
        existing.quantity += quantity
        return existing
    cart_item = CartItem(cart_id=CART_ID, product_id=product["id"], quantity=quantity)
    cart.append(cart_item)
    return cart_item


# list cart (original tool)
@mcp.tool(annotations=READ_ONLY)
def list_cart() -> List[CartItem]:
    """List all cart items"""
    return cart


# NEW: remove some or all of a product from the cart
@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def remove_product_from_cart(
    product_name: Annotated[str, Field(description="Product name to remove (case-insensitive)")],
    quantity: Annotated[
        Optional[int], Field(ge=1, description="How many to remove; leave empty to remove all")
    ] = None,
) -> List[CartItem]:
    """Remove a product from the cart and return the updated cart"""
    product = _find_product(product_name)
    item = next((i for i in cart if i.product_id == product["id"]), None)
    if not item:
        raise ToolError(f"Product [{product['name']}] is not in the cart")
    if quantity is None or quantity >= item.quantity:
        cart.remove(item)
    else:
        item.quantity -= quantity
    return cart


# NEW: empty the cart
@mcp.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True))
def clear_cart() -> str:
    """Remove everything from the cart"""
    count = len(cart)
    cart.clear()
    return f"Cart cleared ({count} line(s) removed)"


# NEW: cart with product names, line totals and grand total
@mcp.tool(annotations=READ_ONLY)
def get_cart_total() -> CartSummary:
    """Show the cart with product names, line totals and the grand total"""
    return _cart_summary()


# ---------------------------------------------------------------------------
# Resources - read-only data addressed by URI
# ---------------------------------------------------------------------------

@mcp.resource("shop://products", mime_type="application/json")
def products_resource() -> str:
    """The full product catalogue"""
    return json.dumps(products, indent=2)


@mcp.resource("shop://products/{product_id}", mime_type="application/json")
def product_resource(product_id: int) -> str:
    """One product from the catalogue (resource template)"""
    product = next((p for p in products if p["id"] == int(product_id)), None)
    if not product:
        raise ValueError(f"Product with id [{product_id}] not found")
    return json.dumps(product, indent=2)


@mcp.resource("shop://cart", mime_type="application/json")
def cart_resource() -> str:
    """Current cart with totals"""
    return _cart_summary().model_dump_json(indent=2)


# ---------------------------------------------------------------------------
# Prompts - reusable templates the user can pick in a client
# ---------------------------------------------------------------------------

@mcp.prompt()
def shopping_assistant(budget: str = "50") -> str:
    """Help the user pick products within a budget"""
    return (
        f"You are a helpful shop assistant. The customer's budget is {budget}. "
        "Use get_products or list_categories to see what's available, suggest items "
        "that fit the budget, add the ones they agree to with add_product_to_cart, "
        "and finish by showing get_cart_total."
    )


# ---------------------------------------------------------------------------
# Web app: plain route + both MCP transports
# ---------------------------------------------------------------------------

# Optional: a normal (non-MCP) route living in the same app
async def health(request):
    return JSONResponse({"status": "ok", "cart_lines": len(cart)})


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
        Route("/health", health),
        *streamable_app.routes,
        *sse_app.routes,
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    # Alternative to uvicorn, serving both transports
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3000)
