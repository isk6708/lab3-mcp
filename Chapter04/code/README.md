# Run sample

Uses the official MCP Python SDK **v2** (`MCPServer`). The server speaks **both** transports.

## Set up virtual environment

```sh
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
```

## Install dependencies

```bash
pip install "mcp[cli]>=2" uvicorn
```

## Run the server

```sh
uvicorn server:app --port 3000
```

| Transport | URL | Use for |
|---|---|---|
| Streamable HTTP | `http://127.0.0.1:3000/mcp` | current clients (recommended) |
| SSE (legacy) | `http://127.0.0.1:3000/sse` | older clients that only speak SSE |

Health check: `http://127.0.0.1:3000/health`

Quick SSE check (should print an `endpoint` event with a `session_id`):

```bash
curl -N http://127.0.0.1:3000/sse
```

## Test the server

```bash
mcp dev server.py
```
