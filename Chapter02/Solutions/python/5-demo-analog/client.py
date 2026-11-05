"""
5-demo-analog / client.py  --  the "office manager"

Starts the contractor (server.py) as a child process and talks to it with
real MCP messages over stdin/stdout. Every message is printed as a "card"
with the analogy next to the raw JSON.

  python client.py             guided tour (press Enter between steps)
  python client.py --free      free play: choose which card to send, break the rules!
  python client.py --auto      guided tour without pauses

Extra options: --hide-json  (only the analogy)   --no-color
"""

import argparse
import itertools
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

OPTIONS = None  # filled in by main()

INITIALIZE_PARAMS = {
    "protocolVersion": "2024-11-05",
    "capabilities": {"sampling": {}},  # "I have an LLM you can borrow"
    "clientInfo": {"name": "OfficeManagerClient", "version": "1.0.0"},
}


# ---------- printing ----------

USE_COLOR = False
CLIENT_COLOR, SERVER_COLOR, NOTE_COLOR, ERROR_COLOR, DIM, BOLD = "36", "33", "35", "31", "2", "1"


def paint(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def show(direction, message, says):
    """Print one message as a card: who -> who, what kind, the analogy, the JSON."""
    if "method" in message:
        kind = "REQUEST" if "id" in message else "NOTIFICATION"
    elif "error" in message:
        kind = "ERROR"
    else:
        kind = "RESPONSE"

    arrow = "CLIENT ----> SERVER" if direction == "out" else "CLIENT <---- SERVER"
    color = CLIENT_COLOR if direction == "out" else SERVER_COLOR
    if kind == "ERROR":
        color = ERROR_COLOR
    elif kind == "NOTIFICATION" and direction == "in":
        color = NOTE_COLOR

    has_ticket = message.get("id") is not None
    label = kind + (f"  ticket #{message['id']}" if has_ticket else "  (no ticket)")
    if "method" in message:
        label += f"  {message['method']}"

    print()
    print(paint(color, f"  {arrow}   {label}"))
    print(paint(BOLD, f'  "{says}"'))
    if not OPTIONS.hide_json:
        for line in json.dumps(message, indent=2).splitlines():
            print(paint(DIM, "    " + line))


def step(number, title, explanation):
    print()
    print(paint(BOLD, "=" * 66))
    print(paint(BOLD, f" STEP {number}: {title}"))
    print(paint(BOLD, "=" * 66))
    for line in textwrap.wrap(explanation, 64):
        print("  " + line)


def pause(prompt="Press Enter to send..."):
    if OPTIONS.auto or not sys.stdin.isatty():
        return
    input(paint(DIM, f"\n  {prompt}"))


# ---------- what each card "says" in the analogy ----------

def response_says(message):
    ticket = message.get("id")
    if "error" in message and ticket is None:
        return f"I couldn't even read your card: {message['error'].get('message')}"
    if "error" in message:
        return f"Sorry, I can't do ticket #{ticket}: {message['error'].get('message')}"
    result = message.get("result") or {}
    if "capabilities" in result:
        return f"Nice to meet you. Here's what I can do. (Answer to ticket #{ticket})"
    if "tools" in result:
        names = ", ".join(t["name"] for t in result["tools"])
        return f"Here's my menu: {names}. (Answer to ticket #{ticket})"
    if "content" in result:
        texts = [c.get("text", "") for c in result["content"] if c.get("type") == "text"]
        prefix = "Problem" if result.get("isError") else "Job done"
        return f"{prefix} (ticket #{ticket}): {' '.join(texts)}"
    return f"Here's the answer to ticket #{ticket}."


def notification_says(message):
    if message.get("method") == "notifications/progress":
        p = message.get("params") or {}
        return (f"Still working: {p.get('message', '')} ({p.get('progress')}/{p.get('total')}). "
                "No ticket number, so nobody replies.")
    return f"FYI: {message.get('method')}. No ticket number, so nobody replies."


# ---------- the fake LLM (zero cost, no API key) ----------

def fake_llm(prompt):
    match = re.search(r"'([^']+)'", prompt)
    product = match.group(1) if match else "this product"
    keywords = re.search(r"Keywords: (.+)\.$", prompt)
    if keywords:
        words = [w.strip() for w in keywords.group(1).split(",")]
        extra = " " + (", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1 else words[0]) + " -"
    else:
        extra = ""
    return f"Meet {product}:{extra} made to be loved and priced to please."


def ask_llm(prompt):
    print(paint(BOLD, f"\n  [client's LLM] The server wants: {prompt}"))
    if not OPTIONS.auto and sys.stdin.isatty():
        typed = input("  You are the LLM now (human in the loop). "
                      "Type the advert, or press Enter for the fake LLM: ").strip()
        if typed:
            return typed, "human"
    return fake_llm(prompt), "fake-llm"


# ---------- the connection ----------

class Connection:
    def __init__(self):
        server = Path(__file__).with_name("server.py")
        self.proc = subprocess.Popen(
            [sys.executable, str(server)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self.ticket_numbers = itertools.count(1)

    def write(self, text):
        self.proc.stdin.write(text + "\n")
        self.proc.stdin.flush()

    def send(self, message, says):
        show("out", message, says)
        self.write(json.dumps(message))

    def receive(self):
        """Next JSON message from the server, or None if it has gone."""
        while True:
            line = self.proc.stdout.readline()
            if not line:
                return None
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                print(paint(ERROR_COLOR, f"\n  Non-protocol output on stdout: {line.strip()}"))

    def request(self, method, params=None, says="", want_progress=False):
        ticket = next(self.ticket_numbers)
        message = {"jsonrpc": "2.0", "id": ticket, "method": method}
        if params is not None:
            message["params"] = dict(params)
        if want_progress:
            message.setdefault("params", {})["_meta"] = {"progressToken": f"job-{ticket}"}
        self.send(message, says)
        return self.wait_for(ticket)

    def notify(self, method, params=None, says=""):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.send(message, says)

    def wait_for(self, ticket):
        """Read messages until the reply with OUR ticket number arrives."""
        while True:
            message = self.receive()
            if message is None:
                print(paint(ERROR_COLOR, "\n  The server closed the pipe."))
                return None
            if "method" in message and "id" in message:
                self.handle_server_request(message)          # the server is asking US
            elif "method" in message:
                show("in", message, notification_says(message))  # FYI, keep waiting
            elif message.get("id") == ticket or message.get("id") is None:
                show("in", message, response_says(message))
                return message
            else:
                show("in", message, f"That answers ticket #{message.get('id')}, not ours. Keep waiting.")

    def handle_server_request(self, message):
        ticket = message["id"]
        method = message["method"]
        if method != "sampling/createMessage":
            show("in", message, "Can you do this for me?")
            self.send({"jsonrpc": "2.0", "id": ticket,
                       "error": {"code": -32601, "message": f"Client does not support {method}"}},
                      "Sorry, I can't help with that.")
            return
        show("in", message,
             f"I need help! Can your LLM write this? (Now the SERVER is asking: ticket #{ticket})")
        try:
            prompt = message["params"]["messages"][0]["content"]["text"]
        except (KeyError, IndexError, TypeError):
            prompt = ""
        text, model = ask_llm(prompt)
        self.send({
            "jsonrpc": "2.0",
            "id": ticket,  # same ticket number, so the server knows which question this answers
            "result": {
                "role": "assistant",
                "content": {"type": "text", "text": text},
                "model": model,
                "stopReason": "endTurn",
            },
        }, f"Here's what our {model} wrote. (Answer to ticket #{ticket})")

    def close(self):
        print(paint(BOLD, "\n  Hanging up: closing the server's stdin. That's how a stdio MCP session ends."))
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            code = self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            code = self.proc.wait()
        print(f"  Server exited with code {code}")


# ---------- guided tour ----------

def guided_tour():
    step(0, "Hire the contractor",
         "The client starts server.py as a child process. From now on they only talk "
         "by writing lines of JSON into each other's pipes (stdin and stdout). The "
         "server's thoughts go to stderr, so they never get mixed up with the messages.")
    pause("Press Enter to start the server...")
    conn = Connection()

    try:
        step(1, "Order before introductions (a mistake, on purpose)",
             "We ask for the menu before doing the handshake. A correct MCP server must "
             "refuse. Watch the error come back with the same ticket number.")
        pause()
        conn.request("tools/list", {}, "What services do you offer?")

        step(2, "Introduce yourselves (initialize)",
             "The client says who it is and what it can do. 'sampling' means: I have an LLM "
             "you may borrow. The server answers with its own capabilities.")
        pause()
        conn.request("initialize", INITIALIZE_PARAMS,
                     "Hi, I'm the office manager. I have an LLM you can borrow. Who are you?")

        step(3, "Say 'let's start' (notifications/initialized)",
             "This is a NOTIFICATION: no ticket number, so the server must NOT reply. "
             "Nothing comes back, and that is correct.")
        pause()
        conn.notify("notifications/initialized", None,
                    "Great, let's start working. (No ticket, no reply expected.)")

        step(4, "Ask for the menu (tools/list)",
             "Same request as step 1, but now the handshake is done, so it works. Each "
             "tool comes with an inputSchema: the order form the client must fill in.")
        pause()
        conn.request("tools/list", {}, "What services do you offer?")

        step(5, "Order a simple job (tools/call)",
             "We fill in the order form for paint_quote. The server really calculates "
             "the price.")
        pause()
        conn.request("tools/call",
                     {"name": "paint_quote", "arguments": {"area_m2": 12, "rate_per_m2": 8.5}},
                     "Please quote 12 m2 at 8.5 per m2.")

        step(6, "Fill in the order form wrongly",
             "The schema says area_m2 must be a number. We send text instead, and the "
             "server answers with an error (-32602, invalid params).")
        pause()
        conn.request("tools/call",
                     {"name": "paint_quote", "arguments": {"area_m2": "twelve", "rate_per_m2": 8.5}},
                     "Please quote 'twelve' m2 at 8.5 per m2.")

        step(7, "A slow job with progress updates (notifications)",
             "We attach a progressToken so the server may send 'still working' notes. "
             "They arrive BEFORE the answer. The client keeps waiting until a message "
             "carries its own ticket number.")
        pause()
        conn.request("tools/call", {"name": "fix_sink", "arguments": {"steps": 3}},
                     "Please fix the sink, and keep me posted.", want_progress=True)

        step(8, "The contractor asks for help (sampling)",
             "The server has no LLM. While doing write_ad it sends a REQUEST the other way: "
             "sampling/createMessage, with its own ticket number (100+). The client asks its "
             "LLM, replies with the same ticket, and only then does the tool finish.")
        pause()
        conn.request("tools/call",
                     {"name": "write_ad",
                      "arguments": {"product": "Cozy Knit Sweater",
                                    "keywords": ["autumn", "cozy", "knitted"]}},
                     "Please write an advert for our sweater.")
    finally:
        step(9, "Hang up", "Closing stdin tells the server we're done.")
        conn.close()

    print(paint(BOLD, "\n  The four rules you just saw:"))
    print("   1. Introduce yourselves first: initialize, then notifications/initialized.")
    print("   2. Requests have a ticket number (id). The reply carries the same number.")
    print("   3. Notifications have no ticket number and never get a reply.")
    print("   4. Either side may send requests. With sampling, the server asks the client.")
    print("\n  Now try:  python client.py --free   and break the rules yourself.\n")


# ---------- free play ----------

def ask(prompt, default):
    text = input(f"  {prompt} [{default}]: ").strip()
    return text or default


def as_number(text):
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return text  # send it as text on purpose, so students can see the error


def free_play():
    if not sys.stdin.isatty():
        print("Free play needs an interactive terminal.")
        return
    conn = Connection()
    menu = [
        ("1", "initialize                (introduce yourselves)"),
        ("2", "notifications/initialized (let's start)"),
        ("3", "tools/list                (what's on the menu?)"),
        ("4", "tools/call paint_quote    (you type the numbers)"),
        ("5", "tools/call fix_sink       (slow job with progress)"),
        ("6", "tools/call write_ad       (server asks your LLM: sampling)"),
        ("7", "tools/call unknown_tool   (order something not on the menu)"),
        ("8", "made-up method            (e.g. pizza/order)"),
        ("9", "type raw JSON yourself"),
        ("0", "hang up"),
    ]
    print(paint(BOLD, "\n  Free play. Try doing things in the wrong order and watch what happens."))
    try:
        while True:
            print()
            for key, label in menu:
                print(f"   {key}. {label}")
            choice = input("\n  Your card: ").strip()
            if choice == "1":
                conn.request("initialize", INITIALIZE_PARAMS, "Hi, I'm the office manager. Who are you?")
            elif choice == "2":
                conn.notify("notifications/initialized", None, "Let's start working.")
            elif choice == "3":
                conn.request("tools/list", {}, "What services do you offer?")
            elif choice == "4":
                area = as_number(ask("area_m2", "12"))
                rate = as_number(ask("rate_per_m2", "8.5"))
                conn.request("tools/call",
                             {"name": "paint_quote", "arguments": {"area_m2": area, "rate_per_m2": rate}},
                             f"Please quote {area} m2 at {rate} per m2.")
            elif choice == "5":
                steps = as_number(ask("steps (1-5)", "3"))
                conn.request("tools/call", {"name": "fix_sink", "arguments": {"steps": steps}},
                             "Please fix the sink, and keep me posted.", want_progress=True)
            elif choice == "6":
                product = ask("product", "Cozy Knit Sweater")
                keywords = [k.strip() for k in ask("keywords, comma separated", "autumn, cozy").split(",")
                            if k.strip()]
                conn.request("tools/call",
                             {"name": "write_ad", "arguments": {"product": product, "keywords": keywords}},
                             f"Please write an advert for {product}.")
            elif choice == "7":
                conn.request("tools/call", {"name": "build_a_house", "arguments": {}},
                             "Please build me a house.")
            elif choice == "8":
                method = ask("method name", "pizza/order")
                conn.request(method, {}, f"Can you do '{method}'?")
            elif choice == "9":
                raw = input("  JSON (one line): ").strip()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    message = None
                if isinstance(message, dict):
                    conn.send(message, "A card you wrote yourself.")
                    if "id" in message and "method" in message:
                        conn.wait_for(message["id"])
                    else:
                        print("  (No ticket number, so no reply is expected.)")
                else:
                    print(paint(DIM, f"\n  CLIENT ----> SERVER   (not valid JSON-RPC)\n    {raw}"))
                    conn.write(raw)
                    conn.wait_for(None)
            elif choice == "0":
                break
            else:
                print("  Pick a number from the menu.")
            if conn.proc.poll() is not None:
                print(paint(ERROR_COLOR, "  The server has stopped."))
                break
    finally:
        conn.close()


def main():
    global OPTIONS, USE_COLOR
    parser = argparse.ArgumentParser(description="MCP contractor analogy demo")
    parser.add_argument("--free", action="store_true", help="free play mode")
    parser.add_argument("--auto", action="store_true", help="guided tour without pauses")
    parser.add_argument("--hide-json", action="store_true", help="show only the analogy text")
    parser.add_argument("--no-color", action="store_true", help="plain text output")
    OPTIONS = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # keep our lines in order with the server's stderr

    USE_COLOR = not OPTIONS.no_color and sys.stdout.isatty() and "NO_COLOR" not in os.environ
    if USE_COLOR and os.name == "nt":
        os.system("")  # turns on colour codes in the Windows console

    if OPTIONS.free:
        free_play()
    else:
        guided_tour()


if __name__ == "__main__":
    main()
