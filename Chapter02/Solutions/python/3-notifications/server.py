import json
import sys

from utils.messages import initializeResponse, progress_notification

initialized = False
initialize_requested = False


def send_response(response):
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


def send_progress():
    send_response(progress_notification)


for line in sys.stdin:
    message = line.strip()
    if message == "exit":
        print("Exiting server.")
        sys.stdout.flush()
        sys.exit(0)

    if not message.startswith('{"jsonrpc":'):
        print(f"Unknown message: {message}")
        sys.stdout.flush()
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
        case "notifications/initialized":
            print("Server has not received an initialize request.")
            sys.stdout.flush()
        case "tools/list" if initialized:
            send_progress()
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
                send_progress()
                send_progress()
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
        case _:
            send_error(request_id, -32601, f"Unknown method: {method}")
