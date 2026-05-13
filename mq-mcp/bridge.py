import asyncio
import json
import os
import sys
from typing import Any

from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
SERVER_COMMAND = os.getenv("MQ_MCP_SERVER_COMMAND", "uv")
SERVER_ARGS = os.getenv("MQ_MCP_SERVER_ARGS", "run mcp run server.py").split()


SYSTEM_PROMPT = """You are connected to a local Model Context Protocol server named mq-mcp.

Important rules:
- MCP means Model Context Protocol.
- Never call it Mojang Command Protocol.
- Use only the MCP tools listed in the provided tool catalog.
- Do not invent tools.
- If the user asks what tools are available, answer from the actual tool catalog.
- If a task can be done with a listed MCP tool, use the tool.
- If no listed tool can do the task, say that clearly.
- Keep answers concise and practical.
"""


def usage() -> None:
    print(
        """Usage:
  uv run python bridge.py "your prompt"
  uv run python bridge.py --tools
  uv run python bridge.py --help

Examples:
  uv run python bridge.py --tools
  uv run python bridge.py "List the available MCP tools."
  uv run python bridge.py "Read README.md and summarize it."
  uv run python bridge.py "Check local system resources."
"""
    )


def parse_prompt() -> tuple[str, bool]:
    args = sys.argv[1:]

    if not args or args[0] in {"-h", "--help", "help"}:
        usage()
        raise SystemExit(0)

    if args[0] == "--tools":
        return "", True

    return " ".join(args), False


def tool_catalog_text(mcp_tools: Any) -> str:
    lines = ["Available MCP tools:"]
    for tool in mcp_tools.tools:
        description = tool.description or "No description."
        schema = json.dumps(tool.inputSchema or {}, ensure_ascii=False)
        lines.append(f"- {tool.name}: {description}")
        lines.append(f"  input_schema: {schema}")
    return "\n".join(lines)


def to_openai_tools(mcp_tools: Any) -> list[dict[str, Any]]:
    openai_tools: list[dict[str, Any]] = []

    for tool in mcp_tools.tools:
        parameters = tool.inputSchema or {"type": "object", "properties": {}}

        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": parameters,
                },
            }
        )

    return openai_tools


def content_to_text(content: Any) -> str:
    if not content:
        return ""

    parts: list[str] = []
    for item in content:
        if hasattr(item, "text"):
            parts.append(item.text)
        else:
            parts.append(str(item))

    return "\n".join(parts)


async def call_mcp_tool(session: ClientSession, name: str, raw_args: str) -> str:
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return f"Tool argument JSON could not be parsed: {raw_args}"

    print(f"-> MCP tool call: {name}({args})")

    try:
        result = await session.call_tool(name, args)
        return content_to_text(result.content)
    except Exception as exc:
        return f"MCP tool call failed: {exc}"


async def run_bridge() -> None:
    prompt, list_tools_only = parse_prompt()

    server_params = StdioServerParameters(
        command=SERVER_COMMAND,
        args=SERVER_ARGS,
        env=os.environ.copy(),
    )

    print("--- mq-mcp bridge: Model Context Protocol <-> OpenAI ---")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_tools = await session.list_tools()
            catalog = tool_catalog_text(mcp_tools)
            openai_tools = to_openai_tools(mcp_tools)

            if list_tools_only:
                print(catalog)
                return

            print(f"Model: {MODEL}")
            print(f"Prompt: {prompt}\n")
            print(catalog)
            print("")

            messages: list[dict[str, Any]] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "system",
                    "content": (
                        "This is the actual tool catalog from the connected MCP server. "
                        "Use this catalog as ground truth.\n\n"
                        f"{catalog}"
                    ),
                },
                {"role": "user", "content": prompt},
            ]

            client = OpenAI()

            first_response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
            )

            assistant_message = first_response.choices[0].message

            if not assistant_message.tool_calls:
                print(f"ChatGPT: {assistant_message.content}")
                return

            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        tool_call.model_dump(exclude_none=True)
                        for tool_call in assistant_message.tool_calls
                    ],
                }
            )

            for tool_call in assistant_message.tool_calls:
                tool_result = await call_mcp_tool(
                    session=session,
                    name=tool_call.function.name,
                    raw_args=tool_call.function.arguments,
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    }
                )

            final_response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
            )

            print(f"\nChatGPT: {final_response.choices[0].message.content}")


if __name__ == "__main__":
    try:
        asyncio.run(run_bridge())
    except KeyboardInterrupt:
        print("\nAvbrutet.")
    except Exception as exc:
        print(f"\nEtt fel uppstod: {exc}")
        raise
