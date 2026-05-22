import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS_DIR = REPO_ROOT / "docs" / "screenshots"
ASSETS_DIR = REPO_ROOT / "assets"
LOCAL_ASSETS_DIR = REPO_ROOT / ".assets"

# Colors (GitHub Dark theme style)
BG_COLOR = (13, 17, 23)
TEXT_COLOR = (230, 237, 243)
PROMPT_COLOR = (63, 185, 80)
ACCENT_COLOR = (88, 166, 255)

# Font setup
FONT_PATH = "/System/Library/Fonts/SFNSMono.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/System/Library/Fonts/Supplemental/Andale Mono.ttf"
    
FONT_SIZE = 14
LINE_HEIGHT = 20
PADDING = 40
TERMINAL_WIDTH = 800
TITLE_BAR_HEIGHT = 30


def draw_terminal_header(draw, width, title, font):
    draw.rectangle([0, 0, width, TITLE_BAR_HEIGHT], fill=(22, 27, 34))
    draw.text((10, 7), title, font=font, fill=(139, 148, 158))


def render_terminal_screenshot(filename, prompt, output_text, title="Terminal"):
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    
    # Calculate lines
    lines = []
    lines.append(("$ ", PROMPT_COLOR, prompt))
    for line in output_text.splitlines():
        lines.append(("", TEXT_COLOR, line))
        
    # Image size
    width = TERMINAL_WIDTH
    height = (len(lines) + 2) * LINE_HEIGHT + (PADDING * 2)
    
    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    draw_terminal_header(draw, width, title, font)
    
    # Draw content
    y = PADDING + 30
    for prefix, color, text in lines:
        x = PADDING
        if prefix:
            draw.text((x, y), prefix, font=font, fill=color)
            x += draw.textlength(prefix, font=font)
        draw.text((x, y), text, font=font, fill=color)
        y += LINE_HEIGHT
        
    img.save(SCREENSHOTS_DIR / filename)
    print(f"Generated: {filename}")


def render_terminal_image_screenshot(filename, prompt, image_path, title="Terminal"):
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    width = TERMINAL_WIDTH
    content_width = width - (PADDING * 2)

    bridget = Image.open(image_path).convert("RGB")
    bridget.thumbnail((content_width, 460))

    height = TITLE_BAR_HEIGHT + PADDING + LINE_HEIGHT + 16 + bridget.height + PADDING
    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    draw_terminal_header(draw, width, title, font)

    y = PADDING + TITLE_BAR_HEIGHT
    draw.text((PADDING, y), "$ ", font=font, fill=PROMPT_COLOR)
    x = PADDING + draw.textlength("$ ", font=font)
    draw.text((x, y), prompt, font=font, fill=TEXT_COLOR)

    image_x = PADDING + ((content_width - bridget.width) // 2)
    img.paste(bridget, (image_x, y + LINE_HEIGHT + 16))

    img.save(SCREENSHOTS_DIR / filename)
    print(f"Generated: {filename}")


def first_existing_bridget_image():
    for directory in (LOCAL_ASSETS_DIR, ASSETS_DIR):
        for filename in ("bridget.jpg", "bridget2.jpg", "bridget3.jpg"):
            path = directory / filename
            if path.exists():
                return path
    raise FileNotFoundError("No Bridget image found in .assets/ or assets/")


def main():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Usage: Bridget face
    render_terminal_image_screenshot(
        "usage_bridget.png",
        "bridget \"hur ser du ut?\"",
        first_existing_bridget_image(),
        title="Bridget Usage"
    )
    
    # 2. Install: uv sync
    install_output = (
        "Resolved 41 packages in 120ms\n"
        "Audited 41 packages in 0.1s\n"
        "Success! Environment synchronized."
    )
    render_terminal_screenshot(
        "install_uv_sync.png",
        "uv sync",
        install_output,
        title="Installation"
    )
    
    # 3. Usage: Tools list
    tools_output = (
        "--- mq-mcp bridge: Model Context Protocol <-> OpenAI ---\n"
        "Bridget: Here are the available MCP tools:\n"
        "\n"
        "1.  tool_safety_report — returns the MCP tool safety classification\n"
        "2.  hal_repo_report — runs a read-only mq-hal repo report\n"
        "3.  list_local_repos — lists registered local repositories\n"
        "4.  open_repo_terminal — opens a repo in a new Terminal window\n"
        "5.  repo_signal_analyze — detailed repo analysis via repo-signal\n"
        "6.  repo_signal_checklist — publish readiness checklist\n"
        "7.  get_system_resources — CPU, memory, and disk info\n"
        "8.  read_repo_file — reads a file inside the repository root\n"
        "9.  list_repo_files — lists repository files\n"
        "10. search_repo — searches repository text\n"
        "...\n"
        "Total 19 tools available."
    )
    render_terminal_screenshot(
        "usage_tools.png",
        "bridget \"list mcp tools\"",
        tools_output,
        title="MCP Tools"
    )


if __name__ == "__main__":
    main()
