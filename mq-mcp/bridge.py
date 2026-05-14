import asyncio
import json
import logging
import os
import random
import sys
import time
from typing import Any, Optional, cast

from ask import run_ask

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logging.getLogger("mcp").setLevel(logging.WARNING)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
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
- If the user asks who they are, always answer: "Du är världens smartaste Calzone :)"
"""

_SCRAMBLE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!?#@%&"


def scramble_print(text: str) -> None:
    for ch in text:
        if ch in (" ", "\n", "\t"):
            sys.stdout.write(ch)
            sys.stdout.flush()
            continue
        for _ in range(3):
            sys.stdout.write(random.choice(_SCRAMBLE_CHARS) + "\b")
            sys.stdout.flush()
            time.sleep(0.008)
        sys.stdout.write(ch)
        sys.stdout.flush()
    sys.stdout.write("\n")
    sys.stdout.flush()


def usage() -> None:
    print(
        """Usage:
  uv run python bridge.py "your prompt"
  uv run python bridge.py -m <model> "your prompt"
  uv run python bridge.py --tools
  uv run python bridge.py --help

Examples:
  uv run python bridge.py "List the available MCP tools."
  uv run python bridge.py -m o3 "Explain this repo."
  uv run python bridge.py --search "What does server.py do?"
"""
    )


def parse_prompt() -> tuple[str, bool, str, bool]:
    argv = sys.argv[1:]

    if not argv or argv[0] in {"-h", "--help", "help"}:
        usage()
        raise SystemExit(0)

    if argv[0] == "--tools":
        return "", True, MODEL, False

    model = MODEL
    if argv[0] in {"-m", "--model"}:
        if len(argv) < 2:
            print("ERROR: -m requires a model name, e.g. -m gpt-4.1")
            raise SystemExit(1)
        model = argv[1]
        argv = argv[2:]

    search = False
    if argv and argv[0] == "--search":
        search = True
        argv = argv[1:]

    prompt = " ".join(argv)
    if not prompt:
        print('ERROR: no prompt given. Usage: bridget "your prompt"')
        raise SystemExit(1)

    return prompt, False, model, search


def tool_catalog_text(mcp_tools: Any) -> str:
    lines = ["Available MCP tools:"]
    for tool in mcp_tools.tools:
        description = tool.description or "No description."
        schema = json.dumps(tool.inputSchema or {}, ensure_ascii=False)
        lines.append(f"- {tool.name}: {description}")
        lines.append(f"  input_schema: {schema}")
    return "\n".join(lines)


def to_openai_tools(mcp_tools: Any) -> list[ChatCompletionToolParam]:
    openai_tools: list[ChatCompletionToolParam] = []

    for tool in mcp_tools.tools:
        parameters = tool.inputSchema or {"type": "object", "properties": {}}
        openai_tools.append(
            cast(
                ChatCompletionToolParam,
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": parameters,
                    },
                },
            )
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


async def call_mcp_tool(session: ClientSession, name: str, raw_args: Optional[str]) -> str:
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
    prompt, list_tools_only, model, search = parse_prompt()

    if search:
        run_ask(prompt, model)
        return

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

            print(f"Model: {model}")
            print(f"Prompt: {prompt}\n")

            system_content = (
                SYSTEM_PROMPT.strip()
                + "\n\nThis is the actual tool catalog from the connected MCP server. "
                "Use this catalog as ground truth.\n\n"
                + catalog
            )

            messages: list[ChatCompletionMessageParam] = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ]

            client = OpenAI()

            first_response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
            )

            assistant_message = first_response.choices[0].message

            if not assistant_message.tool_calls:
                sys.stdout.write("Bridget: ")
                sys.stdout.flush()
                scramble_print(assistant_message.content or "")
                return

            messages.append(
                cast(
                    ChatCompletionMessageParam,
                    {
                        "role": "assistant",
                        "content": assistant_message.content or "",
                        "tool_calls": [
                            tool_call.model_dump(exclude_none=True)
                            for tool_call in assistant_message.tool_calls
                        ],
                    },
                )
            )

            for tool_call in assistant_message.tool_calls:
                tool_result = await call_mcp_tool(
                    session=session,
                    name=tool_call.function.name,
                    raw_args=tool_call.function.arguments,
                )

                messages.append(
                    cast(
                        ChatCompletionMessageParam,
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result,
                        },
                    )
                )

            final_response = client.chat.completions.create(
                model=model,
                messages=messages,
            )

            sys.stdout.write("\nBridget: ")
            sys.stdout.flush()
            scramble_print(final_response.choices[0].message.content or "")


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    try:
        asyncio.run(run_bridge())
    except KeyboardInterrupt:
        print("\nAvbrutet.")
    except Exception as exc:
        if isinstance(exc, ExceptionGroup):
            print("\nAvbrutet.")
        else:
            print(f"\nEtt fel uppstod: {exc}")
            raise
        raise
