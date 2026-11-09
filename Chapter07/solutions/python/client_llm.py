# client_llm.py - lets an LLM (GitHub Models) decide which MCP tool to call
# (MCP Python SDK v2)
# Changes from the original:
#   - tool.inputSchema -> tool.input_schema (renamed in v2)
#   - tool schema for the LLM now includes "required" (and drops a stray "type"
#     key inside "function")
#   - model id "gpt-4o" -> "openai/gpt-4o": the models.github.ai endpoint needs
#     the publisher prefix. Override with the MODEL_NAME environment variable.
#   - friendly message if GITHUB_TOKEN isn't set
#   - starts the server with sys.executable (no mcp CLI needed)
#   - reads GITHUB_TOKEN / MODEL_NAME / MODEL_ENDPOINT from a .env file
#     next to this script (copy .env.example to .env and fill in your token)
# Run: python client_llm.py
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from openai import OpenAI

# llm
import os
import json

SERVER = str(Path(__file__).with_name("server.py"))
ENV_FILE = Path(__file__).with_name(".env")


def load_env_file(path: Path) -> None:
    """Load KEY=value lines from .env into os.environ.

    Uses python-dotenv if installed (pip install python-dotenv); otherwise a
    small built-in parser. Variables already set in the shell win over .env.
    """
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(path, override=False)
        return
    except ImportError:
        pass
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]      # strip surrounding quotes
        os.environ.setdefault(key, value)


load_env_file(ENV_FILE)

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command=sys.executable,  # Executable (same Python / venv as this client)
    args=[SERVER],  # Optional command line arguments
    env=None,  # Optional environment variables
)

def call_llm(prompt, functions):
    token = os.environ["GITHUB_TOKEN"]
    endpoint = os.environ.get("MODEL_ENDPOINT", "https://models.github.ai/inference")

    model_name = os.environ.get("MODEL_NAME", "openai/gpt-4o")

    client = OpenAI(
        base_url=endpoint,
        api_key=token,
    )

    print("CALLING LLM")
    response = client.chat.completions.create(
        messages=[
            {
            "role": "system",
            "content": "You are a helpful assistant.",
            },
            {
            "role": "user",
            "content": prompt,
            },
        ],
        model=model_name,
        tools = functions,
        # Optional parameters
        temperature=1.,
        max_tokens=1000,
        top_p=1.    
    )

    # .content if we want just see the text response 
    response_message = response.choices[0].message
    
    functions_to_call = []

    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            # print("TOOL: ", tool_call)
            name = tool_call.function.name
            print("TOOL NAME: ", name)
            args = json.loads(tool_call.function.arguments)
            functions_to_call.append({ "name": name, "args": args })
    elif response_message.content:
        # The LLM answered directly without needing a tool
        print("LLM: ", response_message.content)

    return functions_to_call

def convert_to_llm_tool(tool):
    tool_schema = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": tool.input_schema.get("properties", {}),
                "required": tool.input_schema.get("required", []),
            }
        }
    }

    return tool_schema

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read, write
        ) as session:
            # Initialize the connection
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("LISTING TOOLS")

            functions = []

            for tool in tools.tools:
                print("Tool: ", tool.name)
                # print("Tool", tool.input_schema["properties"])
                functions.append(convert_to_llm_tool(tool))
            
            while True:
                print("Waiting for input... (type 'quit' to exit)")
                prompt = input("Enter prompt: ")
                if prompt == "quit":
                    break
            
                # ask LLM what tools to all, if any
                functions_to_call = call_llm(prompt, functions)

                # call suggested functions
                for f in functions_to_call:
                    result = await session.call_tool(f["name"], arguments=f["args"])
                    for item in result.content:
                        print("TOOLS result: ", item.text if hasattr(item, "text") else item)


if __name__ == "__main__":
    import asyncio

    if not os.environ.get("GITHUB_TOKEN"):
        sys.exit("GITHUB_TOKEN is not set. Copy .env.example to .env and put your "
                 "GitHub token (with 'Models: read' access) in it - see README.md")

    asyncio.run(run())
