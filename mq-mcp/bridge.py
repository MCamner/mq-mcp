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
from bridget_safety import load_safety_map, needs_approval, tool_class

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

    DOT_COLOR = "\033[38;5;82m"
    RESET_COLOR = "\033[0m"
    FRAMES = ["    ", "•   ", "••  ", "••• ", "••••"]
    INTERVAL = 0.14

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
        # Clear the one-line dot mark so Bridget's answer starts where it began.
        self._stream.write("\r\033[K")
        self._stream.flush()

    def _spin(self) -> None:
        idx = 0
        while not self._stop_event.is_set():
            frame = self.FRAMES[idx % len(self.FRAMES)]
            self._stream.write(f"\r{self.DOT_COLOR}{frame}{self.RESET_COLOR}")
            self._stream.flush()
            idx += 1
            self._stop_event.wait(self.INTERVAL)


DO_MODE = False  # Set True by parse_prompt() when --do is passed.
_SPINNER: "BridgetSpinner | None" = None  # Set by run_bridge so the gate can pause it.

# tool_name -> {"class", "write", "subprocess"} from docs/tool_contracts.json.
# Used by the approval gate to decide which calls need explicit human consent.
_SMAP = load_safety_map()

_APPROVE_WORDS = {"ja", "j", "y", "yes", "ok", "kör", "kor", "approve"}
_DENY_WORDS = {"nej", "n", "no", "stop", "stopp", "avbryt"}
_SHOW_WORDS = {"visa", "full", "detaljer", "varför", "varfor"}
_MODIFY_WORDS = {"ändra", "andra", "byt", "change"}


def _ask_tty(prompt: str) -> str:
    """Read one line from /dev/tty, falling back to stdin/stdout.

    The bridget launcher captures stdout (`out=$(command bridget ... 2>&1)`),
    so a stdout prompt would be invisible and input() would deadlock. Prefer
    /dev/tty so the prompt is always visible; never silently deny on failure.
    Returns "" on EOF/interrupt or when no tty is available.
    """
    tty = None
    try:
        tty = open("/dev/tty", "r+")
    except Exception:
        tty = None

    out = tty or sys.stdout
    reader = tty or sys.stdin
    try:
        out.write(prompt)
        out.flush()
        return (reader.readline() or "").strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    finally:
        if tty:
            tty.close()


def render_gate_card(
    tool_name: str,
    tool_args: dict,
    cls: str,
    assistant_note: str = "",
    *,
    verbose: bool = False,
) -> str:
    """Render the approval card shown before a Class C/D tool runs.

    Facts only: tool name, class, write/subprocess flags from the contract, the
    concrete args, and the assistant's own stated intent (no invented reason).
    """
    meta = _SMAP.get(tool_name, {})
    write = meta.get("write", False)
    subproc = meta.get("subprocess", False)

    line = "─" * 60
    parts = [
        "",
        line,
        "⚠️  Bridget vill köra ett verktyg",
        f"   Verktyg:    {tool_name}",
        f"   Klass:      {cls}",
        f"   Skriver:    {'ja' if write else 'nej'}",
        f"   Subprocess: {'ja' if subproc else 'nej'}",
    ]

    command = tool_args.get("command")
    working_dir = tool_args.get("working_dir")
    if command:
        parts.append(f"   $ {command}")
    if working_dir:
        parts.append(f"   katalog:    {working_dir}")
    if verbose:
        # Full arg dump only on request, to keep the default card compact.
        args_json = json.dumps(tool_args, ensure_ascii=False, indent=2)
        parts.append("   args:")
        parts.extend(f"     {row}" for row in args_json.splitlines())
    if assistant_note:
        parts.append(f"   avsikt:     {assistant_note.strip()}")

    parts.append(line)
    return "\n".join(parts)


def approval_gate(tool_name: str, tool_args: dict, assistant_note: str = "") -> bool:
    """Class-based approval gate. A/B pass; C/D (and unknown) require consent.

    Reads safety class from docs/tool_contracts.json via bridget_safety. For
    gated calls, shows a card and loops on: ja / visa / ändra / nej. `ändra`
    only edits shell_exec's command (other tools' args aren't editable in v0.5).
    Pauses the spinner while waiting so the two don't write the tty at once.
    """
    if not needs_approval(tool_name, _SMAP):
        return True

    cls = tool_class(tool_name, _SMAP)

    if _SPINNER:
        _SPINNER.stop()
    try:
        card = render_gate_card(tool_name, tool_args, cls, assistant_note)
        while True:
            answer = _ask_tty(card + "\nja / visa / ändra / nej: ").lower()
            if answer in _APPROVE_WORDS:
                return True
            if answer in _DENY_WORDS or answer == "":
                return False
            if answer in _SHOW_WORDS:
                card = render_gate_card(
                    tool_name, tool_args, cls, assistant_note, verbose=True
                )
                continue
            if answer in _MODIFY_WORDS:
                if tool_name == "shell_exec":
                    new_cmd = _ask_tty("Nytt kommando: ")
                    if new_cmd:
                        tool_args["command"] = new_cmd
                    card = render_gate_card(tool_name, tool_args, cls, assistant_note)
                else:
                    card = (
                        render_gate_card(tool_name, tool_args, cls, assistant_note)
                        + "\n(ändra stöds bara för shell_exec i v0.5 — svara ja eller nej)"
                    )
                continue
            # Unrecognized input: re-show the choices rather than guessing.
            card = render_gate_card(tool_name, tool_args, cls, assistant_note)
    finally:
        if _SPINNER:
            _SPINNER.start()


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
BRIDGET_ASSET_GLOB = "bridget*.jpg"
_last_bridget_image: Path | None = None
BRIDGET_LOCAL_LINES = [
    "Hej, jag mår bra. Lite kaos i håret, men full signal.",
    "Jag sorterar tankar, terminaler och dramatiska JPEG-vibbar.",
    "Idag ser jag ut som en lokal MCP-brygga med ovanligt bra självförtroende.",
    "Jag är online, pigg och misstänkt nöjd med dagens slump.",
    "Hej Calzone. Jag mår fint och låtsas att jag har kontroll på allt.",
    "Jag gör Bridget-grejer: svarar, blinkar i ASCII och håller koll på verktygen.",
    "Dagens look är: repo-chic, lätt mystisk, 80 kolumner bred.",
    "Jag är här, jag mår bra, och bilden valdes av ödet plus random.choice.",
    "Just nu poserar jag lokalt. Inga moln, bara stil.",
    "Hej! Jag har druckit noll kaffe och ändå kompilerar personligheten.",
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
  uv run python bridge.py --repl
  uv run python bridge.py --tools
  uv run python bridge.py --help

Examples:
  uv run python bridge.py "List the available MCP tools."
  uv run python bridge.py -m o3 "Explain this repo."
  uv run python bridge.py --repl            # interactive session; follow-ups keep context
  uv run python bridge.py --search "What does server.py do?"
  uv run python bridge.py --search-global "How do all my repos relate?"
"""
    )


def parse_prompt() -> tuple[str, bool, bool, str, bool, bool, bool]:
    argv = sys.argv[1:]

    do_mode = "--do" in argv
    if do_mode:
        argv = [a for a in argv if a != "--do"]
        global DO_MODE
        DO_MODE = True

    # --repl runs an interactive loop; the prompt comes from stdin per turn, so
    # the usual "no prompt" error does not apply.
    repl = "--repl" in argv
    if repl:
        argv = [a for a in argv if a != "--repl"]

    if not repl and (not argv or argv[0] in {"-h", "--help", "help"}):
        usage()
        raise SystemExit(0)

    if not repl and argv and argv[0] == "--tools":
        return "", True, do_mode, MODEL, False, False, False

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

    if repl:
        return "", False, do_mode, model, False, False, True

    prompt = " ".join(argv)
    if not prompt:
        print('ERROR: no prompt given. Usage: bridget "your prompt"')
        raise SystemExit(1)

    return prompt, False, do_mode, model, search, search_global, False


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


async def call_mcp_tool(
    session: ClientSession,
    name: str,
    raw_args: Optional[str],
    assistant_note: str = "",
) -> str:
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return f"Tool argument JSON could not be parsed: {raw_args}"

    if not approval_gate(name, args, assistant_note):
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


DO_INSTRUCTIONS = (
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


def build_system_content(catalog: str, ctx: BridgetContext, do_mode: bool) -> str:
    """Assemble the system prompt: persona + recalled context + tool catalog."""
    return (
        SYSTEM_PROMPT.strip()
        + ctx.load()
        + ctx.load_lessons()
        + (DO_INSTRUCTIONS if do_mode else "")
        + "\n\nThis is the actual tool catalog from the connected MCP server. "
        "Use this catalog as ground truth.\n\n"
        + catalog
    )


async def run_turn(
    session: ClientSession,
    client: OpenAI,
    messages: list[ChatCompletionMessageParam],
    model: str,
    openai_tools: list[ChatCompletionToolParam],
    *,
    do_mode: bool,
    spinner: "BridgetSpinner | None",
) -> tuple[str, list[str]]:
    """Run one assistant turn against `messages` (last item = new user input).

    Mutates `messages` in place (appends the assistant reply, any tool calls and
    their results, and the final answer) and returns (answer, called_tools). The
    accumulated `messages` are what give the REPL its follow-up continuity. Runs
    a single round of tool calls — enough for v0.5. Manages the thinking spinner;
    the caller owns the "Bridget: " prefix and output stream.
    """
    if spinner:
        spinner.start()

    first_response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=openai_tools,
        # In --do mode force a tool call so the model acts instead of asking for
        # permission in text.
        tool_choice="required" if do_mode else "auto",
    )

    assistant_message = first_response.choices[0].message

    if not assistant_message.tool_calls:
        if spinner:
            spinner.stop()
        answer = assistant_message.content or ""
        messages.append({"role": "assistant", "content": answer})
        return answer, []

    note = assistant_message.content or ""
    messages.append(
        cast(
            ChatCompletionMessageParam,
            {
                "role": "assistant",
                "content": note,
                "tool_calls": [
                    tool_call.model_dump(exclude_none=True)
                    for tool_call in assistant_message.tool_calls
                ],
            },
        )
    )

    called_tools: list[str] = []
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

        called_tools.append(tool_name)
        tool_result = await call_mcp_tool(
            session=session,
            name=tool_name,
            raw_args=tool_args,
            assistant_note=note,
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

    final_response = client.chat.completions.create(model=model, messages=messages)
    answer = final_response.choices[0].message.content or ""
    messages.append({"role": "assistant", "content": answer})
    if spinner:
        spinner.stop()
    return answer, called_tools


async def run_repl(model: str, do_mode: bool) -> None:
    """Interactive loop: one MCP session, in-memory message history per session.

    Follow-ups work because each user line is appended to the same `messages`
    list, so a short reply (`mq-mcp`, `ja`, `README.md`) carries the prior turn's
    context. State lives only in memory — no session file, no cross-process
    state. Slash commands: /clear resets to the system prompt, /context shows the
    active state, /exit quits.
    """
    if do_mode:
        os.environ["MQ_MCP_ALLOW_SHELL_EXEC"] = "1"

    server_params = StdioServerParameters(
        command=SERVER_COMMAND,
        args=SERVER_ARGS,
        env=os.environ.copy(),
    )

    try:
        tty = open("/dev/tty", "w")
    except Exception:
        tty = None
    spinner = BridgetSpinner(stream=tty)
    global _SPINNER
    turn_spinner = None if do_mode else spinner
    if turn_spinner:
        _SPINNER = spinner

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_tools = await session.list_tools()
            catalog = tool_catalog_text(mcp_tools)
            openai_tools = to_openai_tools(mcp_tools)

            ctx = BridgetContext()
            system_message: ChatCompletionMessageParam = {
                "role": "system",
                "content": build_system_content(catalog, ctx, do_mode),
            }
            messages: list[ChatCompletionMessageParam] = [system_message]
            client = OpenAI()

            print(
                "Bridget REPL — /exit avslutar, /clear nollställer kontext, "
                "/context visar läge."
            )

            while True:
                line = _ask_tty("\n› ").strip()
                if not line:
                    continue

                low = line.lower()
                if low in {"/exit", "/quit"}:
                    break
                if low == "/clear":
                    messages = [system_message]
                    print("Kontext nollställd.")
                    continue
                if low == "/context":
                    turns = sum(1 for m in messages if m.get("role") == "user")
                    print(f"Aktiv session: {turns} fråge-turer i minnet.")
                    continue

                messages.append({"role": "user", "content": line})
                answer, called_tools = await run_turn(
                    session,
                    client,
                    messages,
                    model,
                    openai_tools,
                    do_mode=do_mode,
                    spinner=turn_spinner,
                )

                sys.stdout.write("\nBridget: ")
                sys.stdout.flush()
                scramble_print(answer)
                speak_if_enabled(answer)
                ctx.record(line, called_tools, answer)

    if tty:
        tty.close()


async def run_bridge() -> None:
    prompt, list_tools_only, do_mode, model, search, search_global, repl = parse_prompt()

    if repl:
        await run_repl(model, do_mode)
        return

    # In --do mode, enable the server's shell_exec tool for the child process
    # only. Set before server_params copies the environment. Other clients,
    # which never set this, get shell_exec disabled server-side.
    if do_mode:
        os.environ["MQ_MCP_ALLOW_SHELL_EXEC"] = "1"

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

            mcp_tools = await session.list_tools()
            catalog = tool_catalog_text(mcp_tools)
            openai_tools = to_openai_tools(mcp_tools)

            if list_tools_only:
                spinner.stop()
                print(catalog)
                if tty:
                    tty.close()
                return

            ctx = BridgetContext()
            messages: list[ChatCompletionMessageParam] = [
                {"role": "system", "content": build_system_content(catalog, ctx, do_mode)},
                {"role": "user", "content": prompt},
            ]

            client = OpenAI()

            # The connect-phase spinner has covered startup; run_turn manages its
            # own thinking spinner from here.
            spinner.stop()
            answer, called_tools = await run_turn(
                session,
                client,
                messages,
                model,
                openai_tools,
                do_mode=do_mode,
                spinner=None if do_mode else spinner,
            )

            sys.stdout.write("\nBridget: ")
            sys.stdout.flush()
            scramble_print(answer)
            speak_if_enabled(answer)
            ctx.record(prompt, called_tools, answer)

            if tty:
                tty.close()


if __name__ == "__main__":
    reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
    if reconfigure_stdout:
        reconfigure_stdout(line_buffering=True)

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
