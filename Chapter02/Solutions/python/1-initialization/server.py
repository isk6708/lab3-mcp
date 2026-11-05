import json
import sys

from utils.messages import initializeResponse

initialized = False
initialize_requested = False

for line in sys.stdin:
    message = line.strip()
    if message == "hello":
        print("hello there")
        sys.stdout.flush()
    elif message.startswith('{"jsonrpc":'):
        json_message = json.loads(message)
        method = json_message.get('method', '')

        match method:
            case "initialize":
                initialize_requested = True
                print(json.dumps(initializeResponse))
                sys.stdout.flush()
            case "notifications/initialized" if initialize_requested:
                initialized = True
                sys.stdout.flush()
            case "tools/list" if initialized:
                response = {
                    "jsonrpc": "2.0",
                    "id": json_message["id"],
                    "result": ["tool1", "tool2"]
                }
                print(json.dumps(response))
                sys.stdout.flush()
            case "tools/list":
                print("Server not initialized. Send initialize, then notifications/initialized before tools/list.")
                sys.stdout.flush()
            case "notifications/initialized":
                print("Server has not received an initialize request.")
                sys.stdout.flush()
            case _:
                print(f"Unknown method: {json_message['method']}")
                sys.stdout.flush()
    elif message == "exit":
        print("Exiting server.")
        sys.stdout.flush()
        sys.exit(0)
    else:
        print(f"Unknown message: {message}")
