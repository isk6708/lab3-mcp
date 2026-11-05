# 5-demo-analog: MCP explained with a contractor

This folder is an extra teaching demo, not part of the book. It runs the whole of
Chapter 2 (handshake, tools, notifications, sampling) as one simulation. Every
message is printed as a "card" that shows the analogy next to the real JSON.

It needs only Python 3.10 or later: no packages, no API key, no internet.

## The analogy

| Analogy | MCP |
|---|---|
| Office manager | Client (the AI app) |
| Contractor | Server (offers tools) |
| Introductions | `initialize` request and its response (capabilities) |
| "Let's start" | `notifications/initialized` (notification, no reply) |
| "What services do you offer?" | `tools/list` |
| Order form | a tool's `inputSchema` |
| Placing an order | `tools/call` |
| Ticket number | `id` (the reply always carries the same one) |
| "Still working on it!" | `notifications/progress` (no ticket, no reply) |
| Contractor asks for your copywriter | `sampling/createMessage` (the server asks the client's LLM) |
| Hanging up | closing the server's stdin |

## Run it

```sh
python client.py             # guided tour: press Enter between steps
python client.py --free      # free play: choose which card to send
python client.py --auto      # guided tour without pauses
python client.py --hide-json # show only the analogy, not the JSON
```

Lines starting with `(server thinks)` are the server's log. They go to stderr,
so they never mix with protocol messages on stdout. Real MCP servers follow the
same rule.

In the sampling step you can type the advert yourself. You become the LLM:
this is "human in the loop". Press Enter to let the fake LLM answer instead.

## Things to try in free play

1. Ask for the menu (3) before introducing yourselves (1). Why is it refused?
2. Send "let's start" (2) before the introduction (1). Why does nothing come back?
3. Type `abc` as the area in paint_quote (4). Which error code comes back?
4. Run fix_sink (5) with 5 steps. Which messages have no ticket number?
5. Send a raw card (9): `{"jsonrpc":"2.0","method":"tools/list"}`. Why is there no reply?
6. Send broken JSON (9): `{"oops`. What ticket number does the error have?

## Exercises

1. Add a tool `measure_room` (length and width in, area out). You must change
   two places in server.py: the `TOOLS` menu and the `tools/call` routing.
2. Make `fix_sink` refuse more than 3 steps with a clear error message.
3. Remove `"sampling": {}` from `INITIALIZE_PARAMS` in client.py and run
   write_ad again. What happens, and why?
