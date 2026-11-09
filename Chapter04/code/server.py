"""
Chapter 04 - MCP server mounted in a Starlette (ASGI) app.

Uses the official MCP Python SDK v2 (pip install "mcp[cli]>=2"):
  - FastMCP class is now MCPServer  (from mcp.server import MCPServer)
  - Serves BOTH transports from the same server:
      Streamable HTTP (current) -> http://127.0.0.1:3000/mcp
      SSE (legacy, old clients) -> http://127.0.0.1:3000/sse

Run:   uvicorn server:app --port 3000
Test:  mcp dev server.py
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp.server import MCPServer


mcp = MCPServer("My App")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers and return the sum."""
    return a + b


# Optional: a normal (non-MCP) route living in the same app
async def health(request):
    return JSONResponse({"status": "ok"})


# The host app's lifespan must start the Streamable HTTP session manager
# (the MCP server's own lifespan won't run inside another app).
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
