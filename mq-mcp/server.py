import random
import requests
from mcp.server.fastmcp import FastMCP

# Initiera servern med ett tydligt namn
mcp = FastMCP("mq-mcp")

# --- Tools ---
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers and return the sum. Use this for all basic math additions."""
    # Senior-tips: Validering direkt i verktyget förhindrar felaktiga LLM-anrop
    if not isinstance(a, int) or not isinstance(b, int):
        raise ValueError("Båda parametrar (a och b) måste vara heltal.")
    return a + b

@mcp.tool()
def joke(topic: str | None = None) -> str:
    """Fetch a random Chuck Norris joke. Optional topic refines the joke."""
    try:
        if topic:
            res = requests.get("https://api.chucknorris.io/jokes/search", params={"query": topic}, timeout=5)
            data = res.json()
            results = data.get("result", [])
            if results:
                return random.choice(results).get("value")
        
        res = requests.get("https://api.chucknorris.io/jokes/random", timeout=5)
        return res.json().get("value", "Kunde inte hitta ett skämt just nu.")
    except Exception as e:
        return f"Ett fel uppstod vid hämtning av skämt: {str(e)}"

# --- Resources ---
@mcp.resource("reference://readme")
def readme() -> str:
    """Statisk resurs som ger instruktioner om serverns förmågor."""
    return (
        "Reference MCP Server\n\n"
        "Verktyg som stöds:\n"
        "- add(a, b): Addera heltal.\n"
        "- joke(topic): Hämta skämt.\n"
        "Använd dessa för att verifiera korrekt verktygsval och parameteröverföring."
    )

# --- Prompts ---
@mcp.prompt(name="math_add_prompt", description="Recipe for using add/joke reliably.")
def math_add_prompt() -> str:
    """Returnerar den fullständiga instruktionsmallen från källmaterialet."""
    return (
        "You are using the Reference MCP server.\n\n"
        "When the user asks to add numbers:\n"
        "1) Call the add tool with integers a and b.\n"
        "2) Confirm inputs before executing.\n"
        "3) Reply with just the numeric result.\n\n"
        "If the user asks for a joke:\n"
        "1) If they provide a topic, call joke with that topic. Otherwise call joke with no topic.\n"
        "2) Reply with the joke text only."
    )

if __name__ == "__main__":
    mcp.run()
