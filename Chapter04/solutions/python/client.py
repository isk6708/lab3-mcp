"""
Test client for the Chapter 04 shop server.

Start the server first (terminal 1):
    uvicorn server:app --port 3000 --reload

Then run this (terminal 2):
    python client.py          # uses Streamable HTTP (/mcp)
    python client.py sse      # uses legacy SSE (/sse)
"""

import asyncio
import json
import sys

from mcp import Client, ClientSession
from mcp.client.sse import sse_client

BASE_URL = "http://127.0.0.1:3000"


def show(title, result):
    """Print a tool result nicely."""
    print(f"\n--- {title}")
    if result.is_error:
        print("ERROR:", result.content[0].text)
    else:
        print(json.dumps(result.structured_content, indent=2))


async def demo(session):
    """Same steps for either transport."""
    tools = await session.list_tools()
    print("Tools:", [t.name for t in tools.tools])

    resources = await session.list_resources()
    print("Resources:", [str(r.uri) for r in resources.resources])

    prompts = await session.list_prompts()
    print("Prompts:", [p.name for p in prompts.prompts])

    show("list_categories", await session.call_tool("list_categories", {}))
    show("add 2 x Product 1", await session.call_tool("add_product_to_cart", {"product_name": "Product 1", "quantity": 2}))
    show("add product 3", await session.call_tool("add_product_to_cart", {"product_name": "product 3"}))
    show("add unknown product", await session.call_tool("add_product_to_cart", {"product_name": "Nope"}))
    show("get_cart_total", await session.call_tool("get_cart_total", {}))

    cart = await session.read_resource("shop://cart")
    print("\n--- resource shop://cart")
    print(cart.contents[0].text)

    prompt = await session.get_prompt("shopping_assistant", {"budget": "40"})
    print("\n--- prompt shopping_assistant(budget=40)")
    print(prompt.messages[0].content.text)

    show("clear_cart", await session.call_tool("clear_cart", {}))


async def main():
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        print(f"Connecting over SSE to {BASE_URL}/sse")
        async with sse_client(f"{BASE_URL}/sse") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await demo(session)
    else:
        print(f"Connecting over Streamable HTTP to {BASE_URL}/mcp")
        async with Client(f"{BASE_URL}/mcp") as client:
            await demo(client)


asyncio.run(main())
