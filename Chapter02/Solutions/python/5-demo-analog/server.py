"""
5-demo-analog / server.py  --  the "contractor"

A small MCP server that speaks JSON-RPC 2.0 over stdio.

  stdout -> protocol messages ONLY (one JSON object per line)
  stderr -> the contractor's thoughts (logging)

Real MCP servers follow the same rule: never print logs to stdout,
because the client would try to read them as protocol messages.

You normally don't run this file yourself; client.py starts it.
"""

import json
import sys
import time

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "ContractorServer", "version": "1.0.0"}

# The contractor's menu of services (what tools/list returns).
TOOLS = [
    {
        "name": "paint_quote",
        "description": "Quote the price to paint a wall.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "area_m2": {"type": "number", "description": "Wall area in square metres"},
                "rate_per_m2": {"type": "number", "description": "Price per square metre"},
            },
            "required": ["area_m2", "rate_per_m2"],
        },
    },
    {
        "name": "fix_sink",
        "description": "A slow job that reports progress while it runs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "steps": {"type": "integer", "description": "How many steps the job takes (1-5)"},
            },
            "required": [],
        },
    },
    {
        "name": "write_ad",
        "description": "Write an advert for a product. The contractor has no copywriter, "
                       "so it asks the client's LLM for help (sampling).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "product": {"type": "string", "description": "Product name"},
                "keywords": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["product"],
        },
    },
]

JOB_STEPS = [
    "Turning off the water",
    "Removing the old pipe",
    "Fitting the new pipe",
    "Tightening the joints",
    "Testing for leaks",
]

initialize_requested = False
initialized = False
client_capabilities = {}
next_server_request_id = 100  # the server's own ticket numbers, far away from the client's


# ---------- sending and receiving ----------

def think(text):
    """The contractor talking to himself. Goes to stderr, never mixes with protocol."""
    print(f"      (server thinks) {text}", file=sys.stderr, flush=True)


def send(message):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()  # without flush the client would wait forever


def reply(request_id, result):
    send({"jsonrpc": "2.0", "id": request_id, "result": result})


def reply_error(request_id, code, message):
    send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def text_content(text):
    return {"content": [{"type": "text", "text": text}]}


def read_message():
    """Read the next JSON message from stdin. Returns None when the client hangs up."""
    while True:
        line = sys.stdin.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            think(f"That wasn't valid JSON: {line[:60]!r}")
            reply_error(None, -32700, "Parse error: message is not valid JSON")
            continue
        if not isinstance(message, dict):
            think("That was JSON, but not a JSON-RPC object.")
            reply_error(None, -32600, "Invalid request: expected a JSON object")
            continue
        return message


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ---------- the tools ----------

def tool_paint_quote(request_id, args):
    area = args.get("area_m2")
    rate = args.get("rate_per_m2")
    if not (is_number(area) and is_number(rate)):
        think("The order form is missing numbers. Sending it back.")
        reply_error(request_id, -32602, "paint_quote needs numbers for area_m2 and rate_per_m2")
        return
    total = round(area * rate, 2)
    think(f"{area} m2 x {rate} per m2 = {total}. Easy job.")
    reply(request_id, text_content(f"Painting {area} m2 at {rate} per m2 will cost {total}."))


def tool_fix_sink(request_id, args, progress_token):
    steps = args.get("steps", 3)
    if not isinstance(steps, int) or isinstance(steps, bool) or not 1 <= steps <= 5:
        reply_error(request_id, -32602, "fix_sink needs steps to be a whole number from 1 to 5")
        return
    if progress_token is None:
        think("The client didn't give me a progress token, so I'll work quietly.")
    for i in range(steps):
        time.sleep(0.7)  # pretend this takes a while
        think(f"Step {i + 1}/{steps}: {JOB_STEPS[i]}...")
        if progress_token is not None:
            send({
                "jsonrpc": "2.0",
                "method": "notifications/progress",  # no "id": it's a notification
                "params": {
                    "progressToken": progress_token,  # tells the client which job this is about
                    "progress": i + 1,
                    "total": steps,
                    "message": JOB_STEPS[i],
                },
            })
    reply(request_id, text_content(f"Sink fixed in {steps} steps. No more leaks."))


def tool_write_ad(request_id, args):
    global next_server_request_id
    product = args.get("product")
    keywords = args.get("keywords", [])
    if not isinstance(product, str) or not product.strip():
        reply_error(request_id, -32602, "write_ad needs a product name")
        return
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        reply_error(request_id, -32602, "write_ad keywords must be a list of strings")
        return
    if "sampling" not in client_capabilities:
        think("This client never said it has an LLM, so I can't ask it for help.")
        reply_error(request_id, -32603, "write_ad needs a client that supports sampling")
        return

    think("I'm a contractor, not a copywriter. Asking the client's LLM for help...")
    sampling_id = next_server_request_id
    next_server_request_id += 1
    prompt = f"Write a one-sentence advert for '{product}'."
    if keywords:
        prompt += f" Keywords: {', '.join(keywords)}."

    # Now the SERVER sends a request to the CLIENT.
    send({
        "jsonrpc": "2.0",
        "id": sampling_id,
        "method": "sampling/createMessage",
        "params": {
            "messages": [{"role": "user", "content": {"type": "text", "text": prompt}}],
            "systemPrompt": "You write short, friendly product adverts.",
            "includeContext": "thisServer",
            "maxTokens": 100,
        },
    })

    # Wait for the client's answer to OUR ticket number.
    while True:
        message = read_message()
        if message is None:
            think("The client hung up while I was waiting for the advert.")
            raise SystemExit(0)
        if message.get("id") == sampling_id and "method" not in message:
            break
        think("Got another message while waiting for the copywriter; ignoring it in this demo.")

    if "error" in message:
        think("The client said no. I'll report that back.")
        reply(request_id, {
            "content": [{"type": "text",
                         "text": f"The client refused to write the advert: {message['error'].get('message')}"}],
            "isError": True,
        })
        return

    result = message.get("result", {})
    advert = result.get("content", {}).get("text", "")
    model = result.get("model", "an unknown model")
    think(f"Got the advert back (written by {model}). Passing it on.")
    reply(request_id, text_content(f"Advert for {product} (written by {model}): {advert}"))


# ---------- routing ----------

def handle(message):
    global initialize_requested, initialized, client_capabilities
    method = message.get("method")
    request_id = message.get("id")
    is_notification = "id" not in message

    if method is None:
        think("That's a reply to a question I never asked. Ignoring it.")
        return

    if method == "initialize":
        if is_notification:
            think("An introduction without a ticket number? I can't reply to that.")
            return
        initialize_requested = True
        params = message.get("params") or {}
        client_capabilities = params.get("capabilities") or {}
        client_name = (params.get("clientInfo") or {}).get("name", "someone")
        think(f"Nice to meet you, {client_name}. Here's what I can do.")
        reply(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        })
        return

    if method == "notifications/initialized":
        if not initialize_requested:
            think("'Let's start'? We haven't even been introduced. Ignoring that.")
            return
        initialized = True
        think("Handshake done. Ready to take orders. (Notifications get no reply.)")
        return

    if is_notification:
        think(f"Noted '{method}'. It's a notification, so no reply.")
        return

    if method == "ping":
        reply(request_id, {})
        return

    if method in ("tools/list", "tools/call") and not initialized:
        think("Taking orders before the introductions? No.")
        reply_error(request_id, -32002,
                    "Not initialized: send initialize, then notifications/initialized first")
        return

    if method == "tools/list":
        think(f"Handing over my menu: {', '.join(t['name'] for t in TOOLS)}.")
        reply(request_id, {"tools": TOOLS})
        return

    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            reply_error(request_id, -32602, "arguments must be a JSON object")
            return
        progress_token = (params.get("_meta") or {}).get("progressToken")
        think(f"Order received: {name}")
        if name == "paint_quote":
            tool_paint_quote(request_id, args)
        elif name == "fix_sink":
            tool_fix_sink(request_id, args, progress_token)
        elif name == "write_ad":
            tool_write_ad(request_id, args)
        else:
            think("I don't offer that service.")
            reply_error(request_id, -32602, f"Unknown tool: {name}")
        return

    think(f"I don't know how to '{method}'.")
    reply_error(request_id, -32601, f"Method not found: {method}")


def main():
    think("The contractor has arrived and is waiting for an introduction.")
    while True:
        message = read_message()
        if message is None:
            think("The client hung up (stdin closed). Going home.")
            return
        handle(message)


if __name__ == "__main__":
    main()
