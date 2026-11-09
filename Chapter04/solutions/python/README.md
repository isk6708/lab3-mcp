# Running this sample

This sample uses the official MCP Python SDK **v2** (`mcp>=2`) and serves **two transports** from the same server:

| Transport | Endpoint | Use for |
|---|---|---|
| Streamable HTTP (current) | `http://127.0.0.1:3000/mcp` | new clients |
| SSE (legacy) | `http://127.0.0.1:3000/sse` | older clients that only speak SSE |

Both share the same tools and the same cart.

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
uvicorn server:app --port 3000
```

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

### Testing in CLI mode

The inspector you ran is actually a Node.js app and `mcp dev` is a wrapper around it.

You can launch it directly in CLI mode by running the following command:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:3000/mcp --transport http --method tools/list
```

This will list all the tools available in the server: `get_products_by_category`, `add_product_to_cart`, `list_cart` and `get_products`. Each tool has an input schema and an output schema. For example, `add_product_to_cart` looks like this:

```text
{
  "name": "add_product_to_cart",
  "description": "Add product to cart",
  "inputSchema": {
    "type": "object",
    "properties": {
      "product_name": { "title": "Product Name", "type": "string" }
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
`Error executing tool add_product_to_cart: Product [Nope] not found`.

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
