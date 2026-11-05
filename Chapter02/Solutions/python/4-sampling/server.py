import itertools
import json
import random
import sys
import threading

from utils.messages import initializeResponse, progress_notification

initialized = False
initialize_requested = False
output_lock = threading.Lock()
sampling_request_ids = itertools.count(100)
pending_sampling_requests = set()


def send_response(response):
    with output_lock:
        print(json.dumps(response))
        sys.stdout.flush()


def send_error(request_id, code, message):
    send_response({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    })


def create_sampling_message(product):
    request_id = next(sampling_request_ids)
    pending_sampling_requests.add(request_id)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "sampling/createMessage",
        "params": {
            "messages": [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"New product available: {product['name']} "
                        f"(ID: {product['id']}, Price: {product['price']}). "
                        f"Keywords: {', '.join(product['keywords'])}"
                    ),
                },
            }],
            "systemPrompt": "You are a helpful assistant assisting with product descriptions",
            "includeContext": "thisServer",
            "maxTokens": 300,
        },
    }


def request_product_description(product):
    send_response(create_sampling_message(product))


class ProductStore:
    def __init__(self):
        self.listeners = []

    def add_listener(self, callback):
        self.listeners.append(callback)

    def schedule_product(self):
        timer = threading.Timer(1, self.add_product)
        timer.daemon = True
        timer.start()

    def add_product(self):
        product = {
            "id": str(random.randint(10000, 99999)),
            "name": f"Product {random.randint(1, 100)}",
            "price": round(random.uniform(10.0, 100.0), 2),
            "keywords": [
                f"keyword{random.randint(1, 5)}"
                for _ in range(random.randint(1, 3))
            ],
        }
        for listener in self.listeners:
            listener(product)


store = ProductStore()
store.add_listener(request_product_description)
store.schedule_product()

for line in sys.stdin:
    message = line.strip()
    if message == "exit":
        sys.exit(0)

    if not message.startswith('{"jsonrpc":'):
        continue

    json_message = json.loads(message)
    method = json_message.get("method", "")
    request_id = json_message.get("id")

    match method:
        case "initialize":
            initialize_requested = True
            send_response({**initializeResponse, "id": request_id})
        case "notifications/initialized" if initialize_requested:
            initialized = True
        case "tools/list" if initialized:
            send_response(progress_notification)
            send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "example_tool",
                            "description": "An example tool that does something.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "arg1": {
                                        "type": "string",
                                        "description": "An example argument.",
                                    }
                                },
                                "required": ["arg1"],
                            },
                        }
                    ]
                },
            })
        case "tools/call" if initialized:
            params = json_message.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name != "example_tool":
                send_error(request_id, -32601, f"Unknown tool: {tool_name}")
            elif not isinstance(arguments.get("arg1"), str):
                send_error(request_id, -32602, "example_tool requires a string arg1 argument.")
            else:
                product = {
                    "id": "12345",
                    "name": "Sample Product",
                    "price": 19.99,
                    "keywords": ["sample", "product", "example"],
                }
                request_product_description(product)
                send_response(progress_notification)
                send_response(progress_notification)
                send_response({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Called tool {tool_name} with arguments {arguments}",
                            }
                        ]
                    },
                })
        case "tools/list" | "tools/call":
            send_error(
                request_id,
                -32002,
                "Server not initialized. Send initialize, then notifications/initialized first.",
            )
        case _ if request_id in pending_sampling_requests and "result" in json_message:
            pending_sampling_requests.remove(request_id)
        case _:
            send_error(request_id, -32601, f"Unknown method: {method}")
