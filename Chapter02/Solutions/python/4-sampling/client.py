import json
import queue
import subprocess
import sys
import threading
from pathlib import Path

from utils.messages import initialize_message, initialized_message, list_tools_message

message_queue = queue.Queue()
write_lock = threading.Lock()

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
    with write_lock:
        proc.stdin.write(message)
        proc.stdin.flush()


def call_llm(message):
    return f"LLM: {message}"


def handle_sampling_message(message):
    print("[CLIENT] Calling LLM to complete request", message)
    content = message["params"]["messages"][0]["content"]["text"]
    sampling_response = {
        "jsonrpc": "2.0",
        "id": message["id"],
        "result": {
            "content": {
                "type": "text",
                "text": call_llm(content),
            }
        },
    }
    send_message(serialize_message(sampling_response))


def listen_to_stdout():
    for response in proc.stdout:
        try:
            parsed_response = json.loads(response)
        except json.JSONDecodeError:
            print("[THREAD] Non-JSON response received:", response.strip())
            continue

        if parsed_response.get("method") == "sampling/createMessage":
            handle_sampling_message(parsed_response)
        else:
            message_queue.put(parsed_response)


def read_response(request_id):
    while True:
        response = message_queue.get()
        if response.get("id") == request_id:
            return response

        print_response(json.dumps(response), prefix="[SERVER] notification: \n")


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
    if proc.poll() is None:
        send_message("exit\n")
    exit_code = proc.wait()
    print(f"Child exited with code {exit_code}")


listener_thread = threading.Thread(target=listen_to_stdout, daemon=True)
listener_thread.start()


def main():
    try:
        connect()
        tools = list_tools()
        print("Tools available:", tools)

        tool_call_response = call_tool(tools[0]["name"], {"arg1": "hello"})
        for content in tool_call_response:
            print_response(content["text"], prefix="[SERVER] tool response: \n")
    finally:
        close_server()


main()
