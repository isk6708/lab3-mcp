import json
import subprocess
import sys
from pathlib import Path

from utils.messages import initialize_message, initialized_message, list_tools_message

proc = subprocess.Popen(
    [sys.executable, Path(__file__).with_name("server.py")],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)


def serialize_message(message):
    return json.dumps(message) + "\n"


def print_response(response, prefix=""):
    try:
        parsed = json.loads(response)
        print(prefix, json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        print(prefix, response.strip())


def send_message(message):
    print_response(message, prefix="[CLIENT]: ")
    proc.stdin.write(message)
    proc.stdin.flush()


def read_response(request_id):
    while True:
        response = proc.stdout.readline()
        if not response:
            raise RuntimeError("The server closed before responding.")

        parsed_response = json.loads(response)
        if parsed_response.get("id") == request_id:
            return parsed_response

        print_response(response, prefix="[SERVER] notification: \n")


def connect():
    print("Connecting to the server...")
    send_message(serialize_message(initialize_message))
    response = read_response(initialize_message["id"])
    print_response(json.dumps(response), prefix="[SERVER]: \n")
    send_message(serialize_message(initialized_message))


def list_tools():
    send_message(serialize_message(list_tools_message))
    response = read_response(list_tools_message["id"])
    return response["result"]["tools"]


def call_tool(tool_name, arguments):
    tool_message = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }
    send_message(serialize_message(tool_message))
    response = read_response(tool_message["id"])
    return response["result"]["content"]


def close_server():
    send_message("exit\n")
    exit_code = proc.wait()
    print(f"Child exited with code {exit_code}")


def main():
    connect()
    tools = list_tools()
    print("Tools available:", tools)

    tool_call_response = call_tool(tools[0]["name"], {"arg1": "hello"})
    for content in tool_call_response:
        print_response(content["text"], prefix="[SERVER] tool response: \n")

    close_server()


main()
