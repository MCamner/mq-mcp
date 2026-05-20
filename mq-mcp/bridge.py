import asyncio
import json
import logging
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional, cast

from bridget_voice import handle_voice_command, speak_if_enabled
from ask import run_ask

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logging.getLogger("mcp").setLevel(logging.WARNING)

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
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
  uv run python bridge.py --search-global "How do all my repos relate?"
"""
    )


def parse_prompt() -> tuple[str, bool, str, bool, bool]:
    argv = sys.argv[1:]

    if not argv or argv[0] in {"-h", "--help", "help"}:
        usage()
        raise SystemExit(0)

    if argv[0] == "--tools":
        return "", True, MODEL, False, False

    model = MODEL
    if argv[0] in {"-m", "--model"}:
        if len(argv) < 2:
            print("ERROR: -m requires a model name, e.g. -m gpt-4.1")
            raise SystemExit(1)
        model = argv[1]
        argv = argv[2:]

    search = False
    search_global = False
    if argv and argv[0] == "--search":
        search = True
        argv = argv[1:]
    elif argv and argv[0] == "--search-global":
        search = True
        search_global = True
        argv = argv[1:]

    prompt = " ".join(argv)
    if not prompt:
        print('ERROR: no prompt given. Usage: bridget "your prompt"')
        raise SystemExit(1)

    return prompt, False, model, search, search_global


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


def show_bridget_face() -> None:
    assets = Path(__file__).resolve().parents[1] / "assets"
    images = [
        assets / "bridget.jpg",
        assets / "bridget2.jpg",
        assets / "bridget3.jpg",
    ]
    available_images = [path for path in images if path.exists()]

    if available_images and shutil.which("chafa"):
        image = random.choice(available_images)
        subprocess.run(["chafa", "--size", "60x30", str(image)], check=False)
    else:
        print("BRIDGET online.")


def known_local_repos() -> dict[str, str]:
    """Read repo registry from MQ_MCP_LOCAL_REPOS (same logic as server.py)."""
    from pathlib import Path as _Path
    mcp_root = _Path(__file__).resolve().parents[1]
    repos: dict[str, str] = {"mq-mcp": str(mcp_root)}
    raw = os.getenv("MQ_MCP_LOCAL_REPOS", "")
    for item in raw.split(","):
        item = item.strip()
        if item:
            p = _Path(item).expanduser().resolve()
            repos[p.name] = str(p)
    return repos


def is_goto_repo_prompt(prompt: str) -> tuple[bool, str]:
    """Return (True, repo_name) if prompt is a go-to-repo command, else (False, '')."""
    p = prompt.strip().lower()
    prefixes = ["gå till ", "go to ", "öppna repo ", "open repo ", "cd "]
    for prefix in prefixes:
        if p.startswith(prefix):
            name = prompt.strip()[len(prefix):].strip().rstrip("!.").strip()
            return True, name
    return False, ""


def handle_goto_repo(name: str) -> None:
    """Print CD:<path> signal so the bridget() shell wrapper can cd there."""
    repos = known_local_repos()

    match = next((k for k in repos if k.lower() == name.lower()), None)
    if not match:
        available = ", ".join(sorted(repos.keys()))
        print(f"Unknown repo: '{name}'\nAvailable: {available}")
        return

    path = repos[match]
    # Shell wrapper reads this prefix and runs cd itself.
    # A subprocess cannot cd in the parent shell directly.
    print(f"CD:{path}")




def is_bridget_face_prompt(prompt: str) -> bool:
    p = prompt.strip().lower()
    triggers = [
        "hur ser du ut",
        "visa dig",
        "visa bridget",
        "bridget face",
        "vem är du",
        "who are you",
        "show yourself",
        "what do you look like",
    ]
    return any(t in p for t in triggers)


async def run_bridge() -> None:
    prompt, list_tools_only, model, search, search_global = parse_prompt()

    if handle_voice_command(prompt):
        return

    if is_bridget_face_prompt(prompt):
        show_bridget_face()
        speak_if_enabled("Jag är Bridget. Lokal MCP-brygga online.")
        return

    goto, repo_name = is_goto_repo_prompt(prompt)
    if goto:
        handle_goto_repo(repo_name)
        return

    if search:
        run_ask(prompt, model, global_only=search_global)
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
                answer = assistant_message.content or ""
                sys.stdout.write("Bridget: ")
                sys.stdout.flush()
                scramble_print(answer)
                speak_if_enabled(answer)
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

            answer = final_response.choices[0].message.content or ""
            sys.stdout.write("\nBridget: ")
            sys.stdout.flush()
            scramble_print(answer)
            speak_if_enabled(answer)


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
