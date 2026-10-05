"""Textual terminal UI for Bridget chat."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from typing import Any


def _tool_names(openai_tools: list[Any], limit: int = 10) -> str:
    names: list[str] = []
    for tool in openai_tools[:limit]:
        function = tool.get("function", {}) if isinstance(tool, dict) else {}
        name = function.get("name")
        if name:
            names.append(str(name))
    suffix = "" if len(openai_tools) <= limit else f" +{len(openai_tools) - limit}"
    return ", ".join(names) + suffix if names else "inga"


async def run_chat_tui(
    *,
    bridge_module: Any,
    model: str,
    do_mode: bool,
    initial_prompt: str = "",
) -> None:
    """Run Bridget chat inside a Textual full-screen terminal UI.

    The bridge module is injected by bridge.py so this module can stay a thin
    presentation layer over the existing chat engine instead of importing a
    second copy of bridge.py.
    """
    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Footer, Header, Input, RichLog, Static
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Textual saknas. Kör `uv sync` i mq-mcp eller installera dependencyn "
            "och starta sedan `bridget --chat --tui` igen."
        ) from exc

    class BridgetTuiApp(App[None]):
        CSS = """
        Screen {
            background: #0b0f10;
            color: #e7d7a7;
        }

        #body {
            height: 1fr;
        }

        #chat {
            width: 1fr;
            height: 1fr;
            border: solid #d79921;
            padding: 0 1;
            background: #111719;
        }

        #side {
            width: 34;
            height: 1fr;
            border: solid #458588;
            padding: 0 1;
            background: #0f1517;
        }

        #prompt {
            height: 3;
            background: #0b0f10;
        }

        #prompt-top, #prompt-bottom {
            height: 1;
            border-top: solid #d79921;
        }

        #prompt-row {
            height: 1;
            padding: 0 1;
        }

        #prompt-prefix {
            width: 3;
            color: #fabd2f;
            text-style: bold;
        }

        #input {
            width: 1fr;
            height: 1;
            border: none;
            background: #0b0f10;
            color: #e7d7a7;
        }

        .status-title {
            color: #d79921;
            text-style: bold;
            margin-top: 1;
        }

        .status-line {
            color: #a89984;
        }
        """

        BINDINGS = [
            Binding("ctrl+c", "quit", "Avsluta"),
            Binding("ctrl+l", "clear_chat", "Rensa"),
        ]

        def __init__(self, *, session: Any, catalog: str, openai_tools: list[Any]) -> None:
            super().__init__()
            self.client = bridge_module.OpenAI()
            self.session = session
            self.messages: list[Any] = []
            self.ctx = bridge_module.BridgetContext()
            self.openai_tools = openai_tools
            self.chat_name = os.getenv("BRIDGET_CHAT_NAME", "master")
            system_content = bridge_module.build_system_content(self.ctx, catalog, do_mode)
            system_content += bridge_module.chat_identity_context(self.chat_name)
            self.messages = [{"role": "system", "content": system_content}]
            self.session_start = time.monotonic()
            self.turn_count = 0
            self.all_called_tools: list[str] = []
            self.last_prompt = ""
            self.last_answer = ""

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id="body"):
                yield RichLog(id="chat", wrap=True, highlight=True, markup=True)
                with Vertical(id="side"):
                    yield Static("BRIDGET", classes="status-title")
                    yield Static(f"model: {model}", id="model", classes="status-line")
                    yield Static("mcp: ansluter", id="mcp", classes="status-line")
                    yield Static("turns: 0", id="turns", classes="status-line")
                    yield Static("tools: laddar", id="tools", classes="status-line")
                    yield Static("", id="last-tools", classes="status-line")
            with Vertical(id="prompt"):
                yield Static("", id="prompt-top")
                with Horizontal(id="prompt-row"):
                    yield Static(">", id="prompt-prefix")
                    yield Input(
                        placeholder="Skriv till Bridget... (/exit avslutar)",
                        id="input",
                    )
                yield Static("", id="prompt-bottom")
            yield Footer()

        async def on_mount(self) -> None:
            self.title = "Bridget Chat"
            self.query_one("#chat", RichLog).write(
                "[bold #d79921]Bridget TUI[/] — /exit avslutar, Ctrl+L rensar."
            )
            self.query_one("#mcp", Static).update("mcp: ansluten")
            self.query_one("#tools", Static).update(
                f"tools: {_tool_names(self.openai_tools)}"
            )
            self.query_one("#input", Input).focus()
            if initial_prompt.strip():
                await self._submit_turn(initial_prompt.strip())

        async def on_input_submitted(self, event: Input.Submitted) -> None:
            text = event.value.strip()
            event.input.value = ""
            if not text:
                return
            if text.lower() in bridge_module.CHAT_EXIT_WORDS or text == "/exit":
                self.exit()
                return
            await self._submit_turn(text)

        async def _submit_turn(self, text: str) -> None:
            chat = self.query_one("#chat", RichLog)
            input_widget = self.query_one("#input", Input)
            input_widget.disabled = True
            chat.write(f"[bold #fabd2f]{self.chat_name}:[/] {text}")

            if bridge_module.handle_voice_command(text):
                input_widget.disabled = False
                input_widget.focus()
                return
            if bridge_module.is_bridget_face_prompt(text):
                try:
                    images = bridge_module.find_bridget_images()
                    if not images:
                        chat.write("[yellow]Ingen Bridget-bild finns i .assets/ eller assets/.[/]")
                    elif not shutil.which("chafa"):
                        chat.write("[yellow]chafa saknas. Installera med `brew install chafa`.[/]")
                    else:
                        from rich.text import Text

                        image = bridge_module.choose_bridget_image(images)
                        width = max(20, min(64, chat.content_size.width - 2))
                        height = max(8, min(28, chat.content_size.height - 2))
                        result = await asyncio.to_thread(
                            subprocess.run,
                            ["chafa", "--format=symbols", "--colors=full",
                             "--size", f"{width}x{height}", str(image)],
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        chat.write(Text.from_ansi(result.stdout))
                        line = await asyncio.to_thread(bridge_module._image_line, image)
                        chat.write(f"[bold #d79921]▚█▞ Bridget:[/] {line}")
                except (OSError, subprocess.CalledProcessError) as exc:
                    chat.write(f"[red]Kunde inte visa Bridget-bilden:[/] {exc}")
                finally:
                    input_widget.disabled = False
                    input_widget.focus()
                return
            goto, repo_name = bridge_module.is_goto_repo_prompt(text)
            if goto:
                chat.write(
                    f"[#83a598]goto:[/] {repo_name} stöds i plain chat, "
                    "inte inne i TUI än."
                )
                input_widget.disabled = False
                input_widget.focus()
                return

            self.messages.append({"role": "user", "content": text})
            self.query_one("#mcp", Static).update("mcp: tänker")
            try:
                answer, called_tools, did_tool_round = await bridge_module.run_turn(
                    client=self.client,
                    model=model,
                    messages=self.messages,
                    openai_tools=self.openai_tools,
                    do_mode=do_mode,
                    session=self.session,
                )
            except Exception as exc:
                chat.write(f"[red]Fel:[/] {exc}")
                self.query_one("#mcp", Static).update("mcp: fel")
            else:
                prefix = "\n" if did_tool_round else ""
                chat.write(f"{prefix}[bold #d79921]▚█▞ Bridget:[/] {answer}")
                bridge_module.speak_if_enabled(answer)
                self.turn_count += 1
                self.all_called_tools.extend(called_tools)
                self.last_prompt = text
                self.last_answer = answer
                self.messages.append({"role": "assistant", "content": answer})
                self.messages = bridge_module.trim_history(
                    self.messages,
                    bridge_module.context_budget_for(model),
                )
                self.query_one("#turns", Static).update(f"turns: {self.turn_count}")
                self.query_one("#last-tools", Static).update(
                    "last: "
                    + (", ".join(called_tools) if called_tools else "inga verktyg")
                )
                self.query_one("#mcp", Static).update("mcp: ansluten")
            finally:
                input_widget.disabled = False
                input_widget.focus()

        def action_clear_chat(self) -> None:
            self.query_one("#chat", RichLog).clear()

    server_params = bridge_module.StdioServerParameters(
        command=bridge_module.SERVER_COMMAND,
        args=bridge_module.SERVER_ARGS,
        env=os.environ.copy(),
    )
    async with bridge_module.stdio_client(server_params) as (read, write):
        async with bridge_module.ClientSession(read, write) as session:
            await session.initialize()
            catalog, openai_tools = await bridge_module.discover_tools(session)
            app = BridgetTuiApp(
                session=session, catalog=catalog, openai_tools=openai_tools
            )
            try:
                await app.run_async()
            finally:
                bridge_module.record_chat_session(
                    app.ctx,
                    do_mode=do_mode,
                    turns=app.turn_count,
                    tools=app.all_called_tools,
                    last_prompt=app.last_prompt,
                    last_answer=app.last_answer,
                    start=app.session_start,
                )
