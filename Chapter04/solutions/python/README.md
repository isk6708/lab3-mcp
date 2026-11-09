# Running this sample

This sample uses the official MCP Python SDK **v2** (`mcp>=2`) and serves **two transports** from the same server:

| Transport | Endpoint | Use for |
|---|---|---|
| Streamable HTTP (current) | `http://127.0.0.1:3000/mcp` | new clients |
| SSE (legacy) | `http://127.0.0.1:3000/sse` | older clients that only speak SSE |

Both share the same tools and the same cart.

## What's in this server

| File | What it is |
|---|---|
| `server.py` | The shop MCP server (run this) |
| `client.py` | A test script that calls every feature over `/mcp` or `/sse` |
| `server_v1.py` | The original book version (SDK v1), kept for reference only. It won't run on `mcp>=2` |

The server shows all three MCP building blocks:

**Tools** (actions the model can call)

| Tool | Arguments | What it does |
|---|---|---|
| `get_products` | none | All products |
| `get_products_by_category` | `category` | Products in one category (case-insensitive) |
| `list_categories` | none | All category names *(new)* |
| `get_product` | `product_id` | One product by id *(new)* |
| `add_product_to_cart` | `product_name`, `quantity` (optional, default 1) | Adds to the cart; adding the same product again increases its quantity |
| `list_cart` | none | Cart items (ids and quantities) |
| `remove_product_from_cart` | `product_name`, `quantity` (optional) | Removes some, or all if no quantity *(new)* |
| `clear_cart` | none | Empties the cart *(new)* |
| `get_cart_total` | none | Cart with names, line totals and grand total *(new)* |

**Resources** (read-only data a client can load by URI)

| URI | Content |
|---|---|
| `shop://products` | The full catalogue |
| `shop://products/{product_id}` | One product (a resource *template*), e.g. `shop://products/2` |
| `shop://cart` | The cart with totals |

**Prompts** (reusable templates)

| Prompt | Arguments | Purpose |
|---|---|---|
| `shopping_assistant` | `budget` (default `50`) | Tells the model to help the customer shop within a budget |

The data lives in memory, so the cart resets whenever the server restarts.

> Coming from older tutorials? In SDK v2 the `FastMCP` class is now `MCPServer`
> (`from mcp.server import MCPServer`), and `mcp.server.fastmcp` no longer exists.
> SSE (`/sse`) has been superseded by Streamable HTTP (`/mcp`), but this sample keeps it for older clients.

You're recommended to install `uv` but it's not a must, see [instructions](https://docs.astral.sh/uv/#highlights)

## -0- Create a virtual environment

```bash
python -m venv venv
```

## -1- Activate the virtual environment

Windows:

```bash
venv\Scripts\activate
```

macOS / Linux:

```bash
source venv/bin/activate
```

## -2- Install the dependencies

```bash
pip install "mcp[cli]>=2" uvicorn
```

## -3- Run the sample

```bash
uvicorn server:app --port 3000 --reload
```

`--reload` restarts the server automatically whenever you save `server.py`.

> **Make sure you run `server:app`** (the file `server.py`, variable `app`). Running a different app on port 3000
> (for example `uvicorn main:app`) gives `404` for `/mcp` and `/sse`.

The server now listens on both `http://127.0.0.1:3000/mcp` and `http://127.0.0.1:3000/sse`.

## -4- Test the sample

With the server running in one terminal, open another terminal and send an `initialize` request:

```bash
curl -X POST http://127.0.0.1:3000/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-06-18\",\"capabilities\":{},\"clientInfo\":{\"name\":\"curl\",\"version\":\"1\"}}}"
```

You should see a response similar to:

```text
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"capabilities":{"prompts":{"listChanged":false},"resources":{"listChanged":false,"subscribe":false},"tools":{"listChanged":false}},"protocolVersion":"2025-06-18","serverInfo":{"name":"My App","version":""}}}
```

That shows the server's name and capabilities. Great, that means our Streamable HTTP server is responding.

Now check the legacy SSE endpoint:

```bash
curl http://127.0.0.1:3000/sse
```

You should see something like this (press Ctrl+C to stop):

```text
event: endpoint
data: /messages/?session_id=bb803cee4dd34ad4b79b77cb9352293d
```

That `session_id` shows the SSE server is responding and carrying out a handshake.

> On Windows PowerShell, type `curl.exe` instead of `curl`, because plain `curl` runs a different command (`Invoke-WebRequest`).

There's also a plain web route that isn't MCP:

```bash
curl http://127.0.0.1:3000/health
```

```text
{"status":"ok","cart_lines":0}
```

### Quick test with client.py

The fastest way to check everything works. With the server running, open a second terminal (activate the same virtual environment) and run:

```bash
python client.py        # over Streamable HTTP (/mcp)
python client.py sse    # over legacy SSE (/sse)
```

It lists the tools, resources and prompts, then adds products, triggers a "not found" error, shows the cart total,
reads the `shop://cart` resource, fills in the `shopping_assistant` prompt and clears the cart. You should see output starting with:

```text
Connecting over Streamable HTTP to http://127.0.0.1:3000/mcp
Tools: ['get_products', 'get_products_by_category', 'list_categories', 'get_product', 'add_product_to_cart', 'list_cart', 'remove_product_from_cart', 'clear_cart', 'get_cart_total']
Resources: ['shop://products', 'shop://cart']
Prompts: ['shopping_assistant']
```

and, further down, the cart total:

```text
--- get_cart_total
{
  "items": [
    { "product_id": 1, "name": "Product 1", "unit_price": 10.0, "quantity": 2, "line_total": 20.0 },
    { "product_id": 3, "name": "Product 3", "unit_price": 30.0, "quantity": 1, "line_total": 30.0 }
  ],
  "item_count": 3,
  "total": 50.0
}
```

### Testing in the Inspector UI

Option A: let `mcp dev` start its own copy of the server over **stdio** (no uvicorn needed; needs Node.js and `uv`):

```bash
mcp dev server.py
```

Option B: test the server you started with uvicorn. Open the Inspector on its own:

```bash
npx @modelcontextprotocol/inspector
```

Then in the browser choose **Streamable HTTP** with `http://127.0.0.1:3000/mcp`, or **SSE** with `http://127.0.0.1:3000/sse`, and click **Connect**.
Use the **Tools**, **Resources** and **Prompts** tabs to try everything.

> Option A and Option B are separate server processes, so they don't share a cart.

### Testing in CLI mode

The inspector you ran is actually a Node.js app and `mcp dev` is a wrapper around it.

You can launch it directly in CLI mode by running the following command:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/mcp --transport http --method tools/list
```

This will list all the tools available in the server (see the table above). Each tool has an input schema and an output schema. For example, `add_product_to_cart` looks like this:

```text
{
  "name": "add_product_to_cart",
  "description": "Add product to cart. Adding the same product again increases its quantity.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "product_name": {
        "description": "Exact product name, e.g. 'Product 1' (case-insensitive)",
        "title": "Product Name", "type": "string"
      },
      "quantity": {
        "default": 1, "description": "How many to add (default 1)",
        "maximum": 100, "minimum": 1, "title": "Quantity", "type": "integer"
      }
    },
    "required": ["product_name"],
    "title": "add_product_to_cartArguments"
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "cart_id":    { "title": "Cart Id",    "type": "integer" },
      "product_id": { "title": "Product Id", "type": "integer" },
      "quantity":   { "title": "Quantity",   "type": "integer" }
    },
    "required": ["cart_id", "product_id", "quantity"],
    "title": "CartItem"
  }
}
```

To use the SSE endpoint instead, swap the URL and transport:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/sse --transport sse --method tools/list
```

To invoke a tool type:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/mcp --transport http --method tools/call --tool-name list_cart
```

You should see the following output:

```text
{
  "content": [],
  "structuredContent": {
    "result": []
  },
  "isError": false
}
```

Which is to be expected since we haven't added any products to the cart yet.

To add a product to the cart, run the following command:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/mcp --transport http --method tools/call --tool-name add_product_to_cart --tool-arg product_name="Product 1"
```

You should see an output similar to:

```text
{
  "content": [
    {
      "type": "text",
      "text": "{\n  \"cart_id\": 1,\n  \"product_id\": 1,\n  \"quantity\": 1\n}"
    }
  ],
  "structuredContent": {
    "cart_id": 1,
    "product_id": 1,
    "quantity": 1
  },
  "isError": false
}
```

What you're seeing is a response from the server that contains the ID of the product you just added to the cart. You can now list the cart items again by running the following command:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/mcp --transport http --method tools/call --tool-name list_cart
```

and you should now see:

```text
{
  "content": [
    {
      "type": "text",
      "text": "{\n  \"cart_id\": 1,\n  \"product_id\": 1,\n  \"quantity\": 1\n}"
    }
  ],
  "structuredContent": {
    "result": [
      {
        "cart_id": 1,
        "product_id": 1,
        "quantity": 1
      }
    ]
  },
  "isError": false
}
```

Try adding a product that doesn't exist:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/mcp --transport http --method tools/call --tool-name add_product_to_cart --tool-arg product_name="Nope"
```

The tool raises a `ToolError`, so you get `"isError": true` and the message
`Error executing tool add_product_to_cart: Product [Nope] not found. Available: Product 1, Product 2, Product 3`.

Add several at once with the optional `quantity` argument:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/mcp --transport http --method tools/call --tool-name add_product_to_cart --tool-arg product_name="Product 2" --tool-arg quantity=3
```

See the cart with names and totals:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/mcp --transport http --method tools/call --tool-name get_cart_total
```

Read a resource and get a prompt:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/mcp --transport http --method resources/list
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/mcp --transport http --method resources/read --uri shop://cart
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/mcp --transport http --method prompts/get --prompt-name shopping_assistant --prompt-args budget=40
```

### Testing with the Python client

SDK v2 ships a first-class `Client`. Save this as `client.py` and run `python client.py` while the server is running:

```python
import asyncio
from mcp import Client


async def main():
    async with Client("http://127.0.0.1:3000/mcp") as client:
        tools = await client.list_tools()
        print([t.name for t in tools.tools])

        result = await client.call_tool("add_product_to_cart", {"product_name": "Product 1"})
        print(result.structured_content)

        result = await client.call_tool("list_cart", {})
        print(result.structured_content)


asyncio.run(main())
```

To talk to the legacy SSE endpoint from Python, use `sse_client`:

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client


async def main():
    async with sse_client("http://127.0.0.1:3000/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("list_cart", {})
            print(result.structured_content)


asyncio.run(main())
```

## Use it from an AI client

Any MCP client that supports Streamable HTTP can use this server while it runs. For example, in VS Code
add this to `.vscode/mcp.json`, then start it from the MCP view and ask Copilot Chat in Agent mode
something like *"What's in Category 2? Add two of them to my cart and show the total."*

```json
{
  "servers": {
    "shop": {
      "type": "http",
      "url": "http://127.0.0.1:3000/mcp"
    }
  }
}
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `404` on `/sse` or `/mcp` | Another app is on port 3000 (e.g. `uvicorn main:app`). Stop it and run `uvicorn server:app --port 3000` |
| `cannot import name 'MCPServer'` | Your environment has SDK v1. Run `pip install -U "mcp[cli]>=2"` |
| `No module named 'mcp.server.fastmcp'` | You're running `server_v1.py` (or old tutorial code) on SDK v2. Use `server.py` |
| `421 Misdirected Request` | You called the server through a host name other than `127.0.0.1`/`localhost`. See "transport security" in the SDK docs |
| `mcp dev` fails straight away | Install Node.js (for `npx`) and `uv` (`pip install uv`) |
| Cart is empty after a change | The cart is in memory; `--reload` restarts the server and clears it |

