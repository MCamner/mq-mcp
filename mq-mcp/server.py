import random
import requests
import os
import psutil
import shutil
from mcp.server.fastmcp import FastMCP

# Initiera servern
mcp = FastMCP("mq-mcp")

# Definiera tillåten bas-katalog (Repo-roten)
REPO_ROOT = "/Users/mansys/mq-mcp"

# --- Tools ---

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    if not isinstance(a, int) or not isinstance(b, int):
        raise ValueError("Båda parametrar måste vara heltal.")
    return a + b

@mcp.tool()
def joke(topic: str | None = None) -> str:
    """Fetch a random Chuck Norris joke."""
    try:
        if topic:
            res = requests.get("https://api.chucknorris.io/jokes/search", params={"query": topic}, timeout=5)
            data = res.json()
            results = data.get("result", [])
            if results:
                return random.choice(results).get("value")
        
        res = requests.get("https://api.chucknorris.io/jokes/random", timeout=5)
        return res.json().get("value", "Kunde inte hitta ett skämt.")
    except Exception as e:
        return f"Fel vid hämtning av skämt: {str(e)}"

@mcp.tool()
def read_repo_file(relative_path: str) -> str:
    """Läser innehållet i en fil inom repo-katalogen. Ange en relativ sökväg."""
    try:
        # Säkerställ att sökvägen är säker och inom repo
        safe_path = os.path.normpath(os.path.join(REPO_ROOT, relative_path))
        if not safe_path.startswith(REPO_ROOT):
            return "Åtkomst nekad: Du kan bara läsa filer inom repo-katalogen."
        
        if not os.path.isfile(safe_path):
            return f"Filen hittades inte: {relative_path}"
            
        with open(safe_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Begränsa storleken för att inte spränga kontexten
            if len(content) > 10000:
                return content[:10000] + "\n... [Innehåll trunkerat]"
            return content
    except Exception as e:
        return f"Fel vid läsning av fil: {str(e)}"

@mcp.tool()
def get_system_resources() -> str:
    """Hämtar aktuell CPU-användning, minne och ledigt diskutrymme på maskinen."""
    try:
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = shutil.disk_usage("/")
        gb = 1024**3
        
        return (
            f"CPU: {cpu}%\n"
            f"Minne: {memory.percent}% använt ({memory.available // (1024**2)}MB ledigt)\n"
            f"Disk: {disk.free // gb}GB ledigt av {disk.total // gb}GB"
        )
    except Exception as e:
        return f"Fel vid hämtning av systeminfo: {str(e)}"

@mcp.tool()
def fetch_web_content(url: str) -> str:
    """Hämtar råtext från en webbadress för att läsa dokumentation eller nyheter."""
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        # Enkel trunkering av HTML för att få ut text (i en riktig app används t.ex. BeautifulSoup)
        content = res.text
        if len(content) > 15000:
            return content[:15000] + "\n... [Innehåll trunkerat]"
        return content
    except Exception as e:
        return f"Fel vid hämtning av webbinnehåll: {str(e)}"

# --- Resources ---
@mcp.resource("reference://readme")
def readme() -> str:
    """Instruktioner om serverns förmågor."""
    return "Fungerar nu som en avancerad system-assistent med fil-, system- och webb-åtkomst."

if __name__ == "__main__":
    mcp.run()
