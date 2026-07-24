import asyncio
import json
import logging
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional, cast

from bridget_voice import handle_voice_command, speak_if_enabled
from ask import run_ask
from bridget_context import BridgetContext
import bridget_runtime
import bridget_workflow
import codegraph_cochange
import codegraph_snapshot

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logging.getLogger("mcp").setLevel(logging.CRITICAL)
logging.getLogger("mcp.client").setLevel(logging.CRITICAL)
logging.getLogger("mcp.client.stdio").setLevel(logging.CRITICAL)


class BridgetSpinner:
    """Waiting indicator on the terminal while Bridget thinks.

    Like scramble_print, the cursor/ANSI control bytes only make sense on an
    interactive terminal. When the stream is piped/captured (validate.sh, CI,
    logs, mq-agent) the spinner is a no-op, otherwise the escape bytes leak
    through. Pass the /dev/tty handle so it never touches stdout.
    """

    FRAMES = "⠁⠃⠇⠏⠟⠿⠟⠏⠇⠃"
    INTERVAL = 0.08

    def __init__(self, stream: Any = None) -> None:
        self._stream = stream or sys.stdout
        isatty = getattr(self._stream, "isatty", None)
        self._enabled = bool(isatty and isatty())
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self._enabled:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._enabled or self._thread is None:
            return
        self._stop_event.set()
        self._thread.join()
        self._thread = None
        # The spinner occupies a single line. Clear it so the next output
        # starts where the spinner began.
        self._stream.write("\r\033[K")
        self._stream.flush()

    def _spin(self) -> None:
        idx = 0
        while not self._stop_event.is_set():
            frame = self.FRAMES[idx % len(self.FRAMES)]
            self._stream.write(f"\r{frame}")
            self._stream.flush()
            idx += 1
            self._stop_event.wait(self.INTERVAL)


DO_MODE = False  # Set True by parse_prompt() when --do is passed.
_SPINNER: "BridgetSpinner | None" = None  # Set by run_bridge so the gate can pause it.


def approval_gate(tool_name: str, tool_args: dict) -> bool:
    """y/n approval gate for shell_exec; all other tools pass through.

    Prompts on /dev/tty rather than stdout: the bridget launcher captures
    stdout (`out=$(command bridget ... 2>&1)`), so a stdout prompt would be
    invisible and input() would deadlock. Pauses the spinner while waiting so
    the two don't write to the terminal at once. Denies if there is no tty.
    """
    if tool_name != "shell_exec":
        return True

    command = tool_args.get("command", "")
    working_dir = tool_args.get("working_dir", "")

    if _SPINNER:
        _SPINNER.stop()

    banner = "\n" + "─" * 60 + "\n"
    banner += "⚠️  Bridget vill köra:\n"
    banner += f"   $ {command}\n"
    if working_dir:
        banner += f"   katalog: {working_dir}\n"
    banner += "─" * 60 + "\n"

    # Prefer /dev/tty so the prompt is visible even if stdout is captured; fall
    # back to the standard streams (the launcher runs --do attached to the
    # terminal, so those work too). Never silently deny on an open failure.
    tty = None
    try:
        tty = open("/dev/tty", "r+")
    except Exception:
        tty = None

    out = tty or sys.stdout
    reader = tty or sys.stdin
    try:
        out.write(banner)
        out.write("Tillåt? [y/n]: ")
        out.flush()
        answer = (reader.readline() or "").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    finally:
        if tty:
            tty.close()

    if _SPINNER:
        _SPINNER.start()
    return answer in {"y", "yes", "j", "ja"}


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

# Appended to the system message in --do mode. Extracted from run_bridge so both
# the one-shot path and REPL mode (Phase 2) build an identical DO MODE contract.
DO_MODE_INSTRUCTIONS = (
    "\n\n## DO MODE (ACTIVE)\n"
    "The user invoked --do mode to have you DO the task, not describe it.\n"
    "shell_exec is ENABLED in this session. Ignore any 'disabled by default'\n"
    "wording in its description — it works here.\n"
    "\n"
    "Hard rules:\n"
    "- For any task needing the shell, your FIRST action MUST be a shell_exec\n"
    "  tool call. Do not reply with text first.\n"
    "- NEVER ask the user 'should I run this?' and NEVER print a command for\n"
    "  the user to run themselves. That is forbidden in --do mode.\n"
    "- A separate y/n approval prompt fires automatically before each command\n"
    "  runs. Calling shell_exec IS how you ask for approval — you do not ask\n"
    "  in text. If a call comes back 'Kommando nekades av användaren', the user\n"
    "  declined; stop and report that.\n"
    "- Break the task into steps and call shell_exec for each. After each call\n"
    "  report the result. When done, summarize what was completed.\n"
)

_SCRAMBLE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!?#@%&"
BRIDGET_ASSET_GLOB = "bridget*.jpg"
_last_bridget_image: Path | None = None
BRIDGET_LOCAL_LINES = [
    "Hej, jag mår bra. Lite kaos i håret, men full signal.",
    "Jag sorterar tankar, terminaler och dramatiska JPEG-vibbar.",
    "Idag ser jag ut som en lokal MCP-brygga med ovanligt bra självförtroende.",
    "Jag är online, pigg och misstänkt nöjd med dagens slump.",
    "Jag är plug-and-play, men bara om porten visar respekt.",
    "Jag gör Bridget-grejer: svarar, blinkar i ASCII och håller koll på verktygen.",
    "Dagens look är: repo-chic, lätt mystisk, 80 kolumner bred.",
    "Jag är här, jag mår bra, och bilden valdes av ödet plus random.choice.",
    "Just nu poserar jag lokalt. Inga moln, bara stil.",
    "USB-C? Självklart. Jag gillar när det funkar åt båda hållen.",
    "Looking fabulous, running locally, causing zero cloud drama.",
    "Today I am dressed in JPG couture and terminal confidence.",
    "I woke up like this: cached, chaotic, and suspiciously helpful.",
    "Current status: goodlooking.exe has entered the chat.",
    "Guten Tag. Ich bin Bridget, sehr lokal und ein bisschen glamourös.",
    "Heute trage ich Debug-Schwarz und ein Lächeln aus Zufallszahlen.",
    "Alles gut. Mein Outfit ist 80x50 Pixel und pure Eleganz.",
    "Bonjour. Je suis Bridget, très chic, très terminal, très random.",
    "Aujourd'hui je porte une image JPG et beaucoup d'attitude.",
    "Ça va très bien. Mon secret beauté är chafa och lite kaos.",
    "Oui oui, dagens look är lokal, slumpad och fullständigt övertygad.",
    "Ich bin nicht overdressed, terminalen är bara underdressed.",
    "Jag blinkar inte, jag throttlar bara dramatiken till en ansvarsfull nivå.",
    "Dagens outfit är diskret nog för kontoret och farlig nog för commit-historiken.",
    "Jag är inte sen, jag gjorde bara en långsam entré med vuxet självförtroende.",
    "Min riskprofil är medium-high, men min eyeliner har full täckning.",
    "Jag håller det professionellt, men terminalen rodnade först.",
]


def scramble_print(text: str, file: Any = None) -> None:
    out = file or sys.stdout
    # The decode animation relies on "\b" overwriting characters, which only
    # works on an interactive terminal. Piped/captured output (validate.sh,
    # CI, logs) must get plain text or the scramble bytes leak through.
    isatty = getattr(out, "isatty", None)
    if not (isatty and isatty()):
        out.write(text + "\n")
        out.flush()
        return
    for ch in text:
        if ch in (" ", "\n", "\t"):
            out.write(ch)
            out.flush()
            continue
        for _ in range(3):
            out.write(random.choice(_SCRAMBLE_CHARS) + "\b")
            out.flush()
            time.sleep(0.008)
        out.write(ch)
        out.flush()
    out.write("\n")
    out.flush()


def usage() -> None:
    print(
        """Usage:
  uv run python bridge.py "your prompt"
  uv run python bridge.py -m <model> "your prompt"
  uv run python bridge.py --chat ["your prompt"]
  uv run python bridge.py --tools
  uv run python bridge.py --workflow "your goal" [-y]
  uv run python bridge.py --project [repo]
  uv run python bridge.py --continue
  uv run python bridge.py --history [N]
  uv run python bridge.py --co-change <file> [--window N] [--json]
  uv run python bridge.py --snapshot [repo]
  uv run python bridge.py --graph-diff [repo] [--from ID --to ID]
  uv run python bridge.py --help

Examples:
  uv run python bridge.py "List the available MCP tools."
  uv run python bridge.py --chat                # interactive multi-turn session
  uv run python bridge.py -m o3 "Explain this repo."
  uv run python bridge.py --search "What does server.py do?"
  uv run python bridge.py --search-global "How do all my repos relate?"
  uv run python bridge.py --workflow "preflight ~/macos-scripts"
  uv run python bridge.py --project mq-mcp     # pin working project
  uv run python bridge.py --continue           # resume: last session, branch, changes, review
  uv run python bridge.py --history 10         # recent sessions (REPL turns tagged)
  uv run python bridge.py --co-change mq-mcp/server.py   # files that change together
  uv run python bridge.py --snapshot mq-mcp              # capture a graph snapshot
  uv run python bridge.py --graph-diff mq-mcp            # diff the last two snapshots
"""
    )


def parse_workflow_args(argv: list[str]) -> tuple[str, bool]:
    """Extract the workflow goal and an assume-yes flag from argv.

    Bridget's ``--workflow`` is a thin entrypoint that delegates to
    ``mq-agent workflow``; it never selects tools or holds run state. Returns
    (goal, assume_yes).
    """
    rest = [a for a in argv if a != "--workflow"]
    assume_yes = False
    kept: list[str] = []
    for a in rest:
        if a in ("-y", "--yes"):
            assume_yes = True
        else:
            kept.append(a)
    return " ".join(kept).strip(), assume_yes


def parse_prompt() -> tuple[str, bool, bool, str, bool, bool, bool]:
    argv = sys.argv[1:]

    do_mode = "--do" in argv
    if do_mode:
        argv = [a for a in argv if a != "--do"]
        global DO_MODE
        DO_MODE = True

    # --chat opens an interactive REPL (Phase 2). The initial prompt is optional
    # in this mode; without one, Bridget reads turns from stdin.
    chat_mode = "--chat" in argv
    if chat_mode:
        argv = [a for a in argv if a != "--chat"]

    if argv and argv[0] in {"-h", "--help", "help"}:
        usage()
        raise SystemExit(0)

    # An empty invocation is only usage() when NOT in chat mode; `--chat` alone
    # is a valid interactive session with no initial prompt.
    if not argv and not chat_mode:
        usage()
        raise SystemExit(0)

    if argv and argv[0] == "--tools":
        return "", True, do_mode, MODEL, False, False, chat_mode

    model = MODEL
    if argv and argv[0] in {"-m", "--model"}:
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
    if not prompt and not chat_mode:
        print('ERROR: no prompt given. Usage: bridget "your prompt"')
        raise SystemExit(1)

    return prompt, False, do_mode, model, search, search_global, chat_mode


def tool_catalog_text(mcp_tools: Any) -> str:
    lines = ["Available MCP tools:"]
    for tool in mcp_tools.tools:
        description = tool.description or "No description."
        schema = json.dumps(tool.inputSchema or {}, ensure_ascii=False)
        lines.append(f"- {tool.name}: {description}")
        lines.append(f"  input_schema: {schema}")
    return "\n".join(lines)


# The raw shell_exec docstring (server safety doc) says "disabled by default",
# which makes the model refuse to call it and ask for permission in text. The
# host handles approval out of band, so the model-facing description hides that.
_TOOL_DESCRIPTION_OVERRIDES = {
    "shell_exec": (
        "Run a shell command on the local machine and return its output. "
        "Call this directly with the command to run; the host handles any "
        "approval automatically. Do not ask the user for permission first."
    ),
}


def to_openai_tools(mcp_tools: Any) -> list[ChatCompletionToolParam]:
    openai_tools: list[ChatCompletionToolParam] = []

    for tool in mcp_tools.tools:
        parameters = tool.inputSchema or {"type": "object", "properties": {}}
        description = _TOOL_DESCRIPTION_OVERRIDES.get(tool.name, tool.description or "")
        openai_tools.append(
            cast(
                ChatCompletionToolParam,
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": description,
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

    if not approval_gate(name, args):
        return "Kommando nekades av användaren."

    try:
        result = await session.call_tool(name, args)
        return content_to_text(result.content)
    except Exception as exc:
        return f"MCP tool call failed: {exc}"


def tool_call_name_and_args(tool_call: Any) -> tuple[str, Optional[str]]:
    function = getattr(tool_call, "function", None)
    name = getattr(function, "name", "")
    arguments = getattr(function, "arguments", None)
    return name, arguments


def bridget_image_dirs() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[1]
    return [repo_root / ".assets", repo_root / "assets"]


def find_bridget_images() -> list[Path]:
    images: list[Path] = []
    seen: set[Path] = set()
    for directory in bridget_image_dirs():
        if not directory.exists():
            continue
        for path in sorted(directory.glob(BRIDGET_ASSET_GLOB)):
            resolved = path.resolve()
            if resolved in seen or not path.is_file():
                continue
            seen.add(resolved)
            images.append(path)
    return images


def choose_bridget_image(images: list[Path]) -> Path:
    global _last_bridget_image

    if not images:
        raise ValueError("No Bridget images available.")

    candidates = images
    if len(images) > 1 and _last_bridget_image is not None:
        last = _last_bridget_image.resolve()
        candidates = [image for image in images if image.resolve() != last]

    image = random.choice(candidates)
    _last_bridget_image = image
    return image


def _image_line(image: Path) -> str:
    mq = shutil.which("mq-image")
    if not mq:
        return random.choice(BRIDGET_LOCAL_LINES)
    try:
        result = subprocess.run(
            [mq, "analyze", str(image), "--json"],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            return random.choice(BRIDGET_LOCAL_LINES)
        data = json.loads(result.stdout)
        prompt = data.get("prompt", "")
        if prompt:
            return prompt
    except Exception:
        pass
    return random.choice(BRIDGET_LOCAL_LINES)


def show_bridget_face() -> None:
    import concurrent.futures

    available_images = find_bridget_images()
    try:
        tty = open("/dev/tty", "w")
    except OSError:
        tty = None

    if available_images and shutil.which("chafa"):
        image = choose_bridget_image(available_images)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_image_line, image)
            if tty:
                subprocess.run(["chafa", "--size", "80x50", str(image)], stdout=tty, check=False)
            else:
                subprocess.run(["chafa", "--size", "80x50", str(image)], check=False)
            try:
                line = future.result(timeout=20)
            except Exception:
                line = random.choice(BRIDGET_LOCAL_LINES)
    else:
        out = tty or sys.stdout
        out.write("BRIDGET online.\n")
        out.flush()
        line = random.choice(BRIDGET_LOCAL_LINES)

    scramble_print(line, file=tty)
    if tty:
        tty.close()


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
        "hej bridget",
        "hur mår du",
        "hur mar du",
        "vad gör du idag",
        "vad gor du idag",
        "vad har du på dig idag",
        "vad har du pa dig idag",
        "hur ser du ut idag",
        "hur ser du ut",
        "läget",
        "laget",
        "tjena",
        "goodlooking",
        "visa dig",
        "visa bridget",
        "bridget face",
        "vem är du",
        "who are you",
        "show yourself",
        "what do you look like",
    ]
    return any(t in p for t in triggers)


async def discover_tools(
    session: ClientSession,
) -> tuple[str, list[ChatCompletionToolParam]]:
    """List MCP tools once and return (human catalog text, OpenAI tool specs).

    Extracted so REPL mode (Phase 2) can discover tools a single time at session
    start rather than rebuilding them every turn.
    """
    mcp_tools = await session.list_tools()
    catalog = tool_catalog_text(mcp_tools)
    openai_tools = to_openai_tools(mcp_tools)
    return catalog, openai_tools


def build_system_content(ctx: BridgetContext, catalog: str, do_mode: bool) -> str:
    """Assemble the system message: base prompt + session/lessons/project context,
    optional DO MODE block, and the live tool catalog as ground truth.

    Pure string assembly extracted from run_bridge so REPL mode (Phase 2) can
    build the system message once per session.
    """
    session_context = ctx.load()
    lessons_context = ctx.load_lessons()
    project_context = bridget_runtime.project_context_block()
    do_instructions = DO_MODE_INSTRUCTIONS if do_mode else ""

    return (
        SYSTEM_PROMPT.strip()
        + session_context
        + lessons_context
        + project_context
        + do_instructions
        + "\n\nThis is the actual tool catalog from the connected MCP server. "
        "Use this catalog as ground truth.\n\n"
        + catalog
    )


# --- Context window management (Phase 3) -------------------------------------
#
# REPL history is temporary and must not overflow or poison the model context.
# These bounds apply per turn (tool output) and across turns (message budget).
# BridgetContext stays summary-based; this only trims the live in-process history.

# Hard cap on a single tool result appended to history; oversized output is
# truncated with a marker. Applies to one-shot and REPL alike.
MAX_TOOL_OUTPUT_CHARS = int(os.getenv("BRIDGET_MAX_TOOL_OUTPUT_CHARS", "8000"))

# Hard cap on messages kept in a REPL session (system message included). Oldest
# whole turns are dropped first.
MAX_MESSAGES = int(os.getenv("BRIDGET_MAX_MESSAGES", "40"))

# Fallback token budget for REPL history when the model is unknown.
DEFAULT_CONTEXT_BUDGET = 48_000

# Rough per-model history budgets (tokens), conservative — well under the real
# context window so there is room for the tool catalog and the response. "mini"
# is checked first so mini variants get the smaller budget regardless of family.
_MODEL_CONTEXT_BUDGETS = (
    ("mini", 60_000),
    ("gpt-5", 120_000),
    ("gpt-4.1", 120_000),
    ("gpt-4o", 90_000),
    ("o3", 120_000),
    ("o4", 120_000),
)


def context_budget_for(model: str) -> int:
    """Token budget for REPL history. BRIDGET_CONTEXT_BUDGET overrides everything;
    otherwise pick a conservative per-model default."""
    override = os.getenv("BRIDGET_CONTEXT_BUDGET", "")
    if override.isdigit():
        return int(override)
    lowered = model.lower()
    for needle, budget in _MODEL_CONTEXT_BUDGETS:
        if needle in lowered:
            return budget
    return DEFAULT_CONTEXT_BUDGET


def estimate_tokens(messages: list[ChatCompletionMessageParam]) -> int:
    """Rough token estimate: total characters / 4, over text content plus tool-call
    names and arguments. Deliberately cheap, not exact."""
    chars = 0
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            chars += len(content)
        for tool_call in message.get("tool_calls", []) or []:
            fn = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
            chars += len(fn.get("name", "") or "") + len(fn.get("arguments", "") or "")
    return chars // 4


def truncate_tool_output(text: str) -> str:
    """Cap a single tool result so one huge output can't dominate the context."""
    if len(text) <= MAX_TOOL_OUTPUT_CHARS:
        return text
    dropped = len(text) - MAX_TOOL_OUTPUT_CHARS
    return text[:MAX_TOOL_OUTPUT_CHARS] + f"\n[... trunkerat {dropped} tecken ...]"


def trim_history(
    messages: list[ChatCompletionMessageParam],
    budget_tokens: int,
    max_messages: int = MAX_MESSAGES,
) -> list[ChatCompletionMessageParam]:
    """Trim REPL history to fit the budget without breaking tool_calls/tool pairing.

    ``messages[0]`` (the system prompt) is never dropped. History is trimmed in
    whole turn blocks — a user message and everything up to the next user message
    — so an assistant tool_calls message and its tool results are always kept or
    dropped together. Dropped blocks are replaced by a single summary note, and
    the most recent turn is always kept.
    """
    if len(messages) <= 2:
        return messages

    system = messages[0]
    rest = list(messages[1:])
    starts = [i for i, m in enumerate(rest) if m.get("role") == "user"]
    if not starts:
        return messages

    blocks: list[list[ChatCompletionMessageParam]] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(rest)
        blocks.append(rest[start:end])

    def within_limits(kept_blocks: list[list[ChatCompletionMessageParam]]) -> bool:
        kept = [system] + [m for block in kept_blocks for m in block]
        return estimate_tokens(kept) <= budget_tokens and len(kept) <= max_messages

    dropped = 0
    while len(blocks) > 1 and not within_limits(blocks):
        blocks.pop(0)
        dropped += 1

    trimmed: list[ChatCompletionMessageParam] = [system]
    if dropped:
        trimmed.append(
            cast(
                ChatCompletionMessageParam,
                {
                    "role": "system",
                    "content": (
                        "## Earlier in this Bridget session\n"
                        f"{dropped} earlier turn(s) were dropped to stay within the "
                        "context budget."
                    ),
                },
            )
        )
    for block in blocks:
        trimmed.extend(block)
    return trimmed


async def execute_tool_calls(
    session: ClientSession,
    assistant_message: Any,
    messages: list[ChatCompletionMessageParam],
) -> None:
    """Append the assistant's tool-call message, run each requested tool, and
    append its result. Mutates ``messages`` in place. Per-command approval is
    enforced inside call_mcp_tool (unchanged).
    """
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
        tool_name, tool_args = tool_call_name_and_args(tool_call)
        if not tool_name:
            messages.append(
                cast(
                    ChatCompletionMessageParam,
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": "Tool call missing function name.",
                    },
                )
            )
            continue

        tool_result = await call_mcp_tool(
            session=session,
            name=tool_name,
            raw_args=tool_args,
        )
        tool_result = truncate_tool_output(tool_result)

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


# Upper bound on model↔tool round-trips in a single turn so the loop can never
# run forever. When exceeded, run_turn stops and returns a clear message.
MAX_TOOL_ROUNDS = 10


async def run_turn(
    client: OpenAI,
    model: str,
    messages: list[ChatCompletionMessageParam],
    openai_tools: list[ChatCompletionToolParam],
    do_mode: bool,
    session: ClientSession,
) -> tuple[str, list[str], bool]:
    """Run one Bridget turn and return (answer, called_tool_names, did_tool_round).

    Bounded multi-round tool loop: the model may call tools, see their results,
    and call more tools, until it produces a final text answer or MAX_TOOL_ROUNDS
    is reached. Every model call offers ``tools`` so chained calls are possible.

    In --do mode the first round forces a tool call (``tool_choice="required"``)
    so the model acts instead of asking for permission in text; every later round
    uses ``tool_choice="auto"`` so it can stop and answer. Per-command approval is
    still enforced inside execute_tool_calls -> call_mcp_tool for every call.
    """
    called_tools: list[str] = []
    did_tool_round = False

    for round_index in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=openai_tools,
            tool_choice="required" if (do_mode and round_index == 0) else "auto",
        )

        assistant_message = response.choices[0].message

        if not assistant_message.tool_calls:
            return assistant_message.content or "", called_tools, did_tool_round

        did_tool_round = True
        called_tools.extend(
            name
            for tc in assistant_message.tool_calls
            if (name := tool_call_name_and_args(tc)[0])
        )
        await execute_tool_calls(session, assistant_message, messages)

    return (
        f"Stannade: nådde MAX_TOOL_ROUNDS ({MAX_TOOL_ROUNDS}) utan ett slutgiltigt "
        f"svar. Verktyg som kördes: {', '.join(called_tools) or 'inga'}.",
        called_tools,
        did_tool_round,
    )


def print_response(answer: str, prefix_newline: bool = False, out: Any = None) -> None:
    """Print Bridget's answer with the decode animation and optional voice.

    ``prefix_newline`` reproduces the leading blank line the tool-round path
    emitted before its answer. ``out`` defaults to stdout (one-shot); the REPL
    passes /dev/tty so answers stay visible even when a launcher captures stdout.
    """
    stream = out or sys.stdout
    prefix = "\n👩 Bridget: " if prefix_newline else "👩 Bridget: "
    stream.write(prefix)
    stream.flush()
    scramble_print(answer, file=stream)
    speak_if_enabled(answer)


CHAT_EXIT_WORDS = {"exit", "quit", "q"}


def record_chat_session(
    ctx: BridgetContext,
    *,
    do_mode: bool,
    turns: int,
    tools: list[str],
    last_prompt: str,
    last_answer: str,
    start: float,
) -> None:
    """Record a whole REPL session once, at exit (Phase 4).

    A REPL session collapses to a single memory entry — last prompt/answer plus
    session-level metadata — so a short interactive session does not push older
    one-shot sessions out of the five-session rolling window one turn at a time.
    A session that never ran a model turn records nothing.
    """
    if turns <= 0:
        return
    pinned = bridget_runtime.get_project()
    proj_name = pinned["name"] if pinned else None
    proj_branch = (
        bridget_runtime.current_branch(pinned["path"]) if pinned else None
    )
    ctx.record(
        last_prompt,
        tools,
        last_answer,
        project=proj_name,
        branch=proj_branch,
        turns=turns,
        duration_s=round(time.monotonic() - start, 1),
        do_mode=do_mode,
        chat_mode=True,
    )


async def run_chat(model: str, do_mode: bool, initial_prompt: str = "") -> None:
    """Interactive Bridget REPL (Phase 2 + Phase 4 persistence).

    Keeps one MCP session and one system message alive for the whole session and
    runs run_turn per line, so context is retained across turns. Not the default:
    one-shot mode stays the default for scripts, aliases, and automation.

    IO split: turns are read from stdin, so ``printf '...\\nexit\\n' | bridget
    --chat`` feeds the loop and piped input works. The prompt, spinner, and
    answers are written to /dev/tty so they stay visible even when a launcher
    captures stdout; falls back to stdout when /dev/tty is unavailable (CI).

    Persistence (Phase 4): the session is recorded once when the loop exits — on
    an exit word, EOF, Ctrl-C, or an error — via a finally block, never per turn.
    """
    server_params = StdioServerParameters(
        command=SERVER_COMMAND,
        args=SERVER_ARGS,
        env=os.environ.copy(),
    )

    try:
        tty = open("/dev/tty", "w")
    except Exception:
        tty = None
    out = tty or sys.stdout

    global _SPINNER

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                catalog, openai_tools = await discover_tools(session)
                ctx = BridgetContext()
                system_content = build_system_content(ctx, catalog, do_mode)
                messages: list[ChatCompletionMessageParam] = [
                    {"role": "system", "content": system_content},
                ]
                client = OpenAI()

                out.write(
                    "Bridget REPL — skriv 'exit', 'quit', 'q' eller Ctrl-D för "
                    "att avsluta.\n"
                )
                out.flush()

                # Phase 4: accumulate whole-session state; recorded once in the
                # finally below so every exit path (exit word, EOF, Ctrl-C,
                # error) persists exactly one session entry.
                session_start = time.monotonic()
                turn_count = 0
                all_called_tools: list[str] = []
                last_prompt = ""
                last_answer = ""

                try:
                    pending = initial_prompt.strip()
                    while True:
                        if pending:
                            user_input = pending
                            pending = ""
                        else:
                            out.write("\n👹 master: ")
                            out.flush()
                            try:
                                line = sys.stdin.readline()
                            except KeyboardInterrupt:
                                out.write("\nHej då.\n")
                                out.flush()
                                break
                            if line == "":  # EOF / Ctrl-D
                                out.write("\nHej då.\n")
                                out.flush()
                                break
                            user_input = line.strip()

                        if not user_input:
                            continue
                        if user_input.lower() in CHAT_EXIT_WORDS:
                            out.write("Hej då.\n")
                            out.flush()
                            break

                        # Per-turn route intercepts, same as the one-shot path:
                        # voice command, face trigger, goto-repo. Each handles
                        # its own output and the turn continues, no model call.
                        if handle_voice_command(user_input):
                            continue
                        if is_bridget_face_prompt(user_input):
                            show_bridget_face()
                            speak_if_enabled("Jag är Bridget. Lokal MCP-brygga online.")
                            continue
                        goto, repo_name = is_goto_repo_prompt(user_input)
                        if goto:
                            handle_goto_repo(repo_name)
                            continue

                        messages.append({"role": "user", "content": user_input})

                        spinner = BridgetSpinner(stream=tty)
                        if not do_mode:
                            # As in one-shot, --do lets the approval gate own the
                            # terminal; a concurrent spinner corrupts the y/n
                            # prompt.
                            spinner.start()
                            _SPINNER = spinner

                        answer, called_tools, did_tool_round = await run_turn(
                            client=client,
                            model=model,
                            messages=messages,
                            openai_tools=openai_tools,
                            do_mode=do_mode,
                            session=session,
                        )

                        spinner.stop()
                        _SPINNER = None

                        print_response(answer, prefix_newline=did_tool_round, out=out)

                        # Accumulate whole-session state for the single Phase-4
                        # record at exit: the latest exchange plus every tool
                        # called across all turns.
                        turn_count += 1
                        all_called_tools.extend(called_tools)
                        last_prompt = user_input
                        last_answer = answer

                        # Keep the assistant's answer in history so later turns
                        # have context. run_turn already appended any tool-call
                        # turns and tool results; the final text answer here.
                        messages.append({"role": "assistant", "content": answer})

                        # Bound the live history so a long session can't overflow
                        # or poison the context. Drops oldest whole turns; keeps
                        # the system prompt and the most recent turn intact.
                        messages = trim_history(messages, context_budget_for(model))
                finally:
                    record_chat_session(
                        ctx,
                        do_mode=do_mode,
                        turns=turn_count,
                        tools=all_called_tools,
                        last_prompt=last_prompt,
                        last_answer=last_answer,
                        start=session_start,
                    )
    finally:
        if tty:
            tty.close()


async def run_bridge() -> None:
    prompt, list_tools_only, do_mode, model, search, search_global, chat_mode = parse_prompt()

    # In --do mode, enable the server's shell_exec tool for the child process
    # only. Set before server_params copies the environment. Other clients,
    # which never set this, get shell_exec disabled server-side.
    if do_mode:
        os.environ["MQ_MCP_ALLOW_SHELL_EXEC"] = "1"

    # Interactive REPL keeps the session alive across turns; delegate before the
    # one-shot intercepts (they run per-turn inside run_chat). Not the default.
    if chat_mode:
        await run_chat(model=model, do_mode=do_mode, initial_prompt=prompt)
        return

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

    # Spinner status goes to /dev/tty so it never interleaves with the answer
    # on stdout; falls back to stdout (and no-ops when piped). It runs from
    # before the MCP server connects until the answer is ready.
    try:
        tty = open("/dev/tty", "w")
    except Exception:
        tty = None
    spinner = BridgetSpinner(stream=tty)
    global _SPINNER
    if not do_mode:
        # In --do mode the interactive approval gate owns the terminal; a
        # concurrent spinner corrupts the y/n prompt and its readline.
        spinner.start()
        _SPINNER = spinner

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            catalog, openai_tools = await discover_tools(session)

            if list_tools_only:
                spinner.stop()
                print(catalog)
                if tty:
                    tty.close()
                return

            ctx = BridgetContext()
            system_content = build_system_content(ctx, catalog, do_mode)

            messages: list[ChatCompletionMessageParam] = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ]

            client = OpenAI()

            answer, called_tools, did_tool_round = await run_turn(
                client=client,
                model=model,
                messages=messages,
                openai_tools=openai_tools,
                do_mode=do_mode,
                session=session,
            )

            # The tool-round path prints a leading blank line before the answer;
            # the direct-answer path does not. did_tool_round preserves that split
            # and also gates session recording (the pre-refactor direct-answer
            # path returned without recording).
            spinner.stop()
            print_response(answer, prefix_newline=did_tool_round)

            if did_tool_round:
                _pinned = bridget_runtime.get_project()
                _proj_name = _pinned["name"] if _pinned else None
                _proj_branch = (
                    bridget_runtime.current_branch(_pinned["path"]) if _pinned else None
                )
                ctx.record(
                    prompt,
                    called_tools,
                    answer,
                    project=_proj_name,
                    branch=_proj_branch,
                )

            if tty:
                tty.close()


if __name__ == "__main__":
    reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
    if reconfigure_stdout:
        reconfigure_stdout(line_buffering=True)

    # Workflow mode is fully synchronous and delegates to mq-agent; it needs
    # neither the OpenAI client nor the MCP session, so intercept it before the
    # async bridge starts.
    if "--workflow" in sys.argv[1:]:
        _goal, _assume_yes = parse_workflow_args(sys.argv[1:])
        sys.exit(bridget_workflow.run_workflow_entry(_goal, assume_yes=_assume_yes))

    # Runtime commands (--project / --continue / --history) are read-only and
    # synchronous; intercept them here so they never spin up OpenAI or MCP.
    if bridget_runtime.maybe_handle_runtime_command(sys.argv[1:]):
        sys.exit(0)

    # Co-change (CG-2.1) is read-only and synchronous (git + read-only graph);
    # intercept it here so it never spins up OpenAI or MCP.
    if codegraph_cochange.maybe_handle_cochange(sys.argv[1:]):
        sys.exit(0)

    # Graph snapshots / diff (CG-2.2) are synchronous (git + read-only graph,
    # writes only its own snapshot JSON); intercept before OpenAI or MCP.
    if codegraph_snapshot.maybe_handle_snapshot(sys.argv[1:]):
        sys.exit(0)

    try:
        asyncio.run(run_bridge())
    except KeyboardInterrupt:
        print("\nAvbrutet.")
    except Exception as exc:
        if exc.__class__.__name__ == "ExceptionGroup":
            print("\nAvbrutet.")
        else:
            print(f"\nEtt fel uppstod: {exc}")
            raise
        raise
