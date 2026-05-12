import random
import requests
import os
import psutil
import shutil
import subprocess
import pandas as pd
import guitarpro
from PIL import Image
from mcp.server.fastmcp import FastMCP

# Initiera servern
mcp = FastMCP("mq-mcp")

# Definiera tillåten bas-katalog (Repo-roten)
REPO_ROOT = "/Users/mansys/mq-mcp/mq-mcp"

# --- SYSTEM & FILER ---

@mcp.tool()
def get_system_resources() -> str:
    """CPU, minne och disk-info."""
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    gb = 1024**3
    return f"CPU: {cpu}%, Minne: {memory.percent}%, Disk: {disk.free // gb}GB ledigt"

@mcp.tool()
def read_repo_file(relative_path: str) -> str:
    """Läser innehållet i en fil inom repo-katalogen."""
    try:
        safe_path = os.path.normpath(os.path.join(REPO_ROOT, relative_path))
        if not safe_path.startswith(REPO_ROOT): return "Åtkomst nekad."
        with open(safe_path, 'r', encoding='utf-8') as f:
            return f.read(10000)
    except Exception as e: return f"Fel: {str(e)}"

# --- NYTT VERKTYG: SCRIPT KONTROLL ---

@mcp.tool()
def run_mqlaunch() -> str:
    """Startar och kör skriptet mqlaunch.sh i projektmappen."""
    script_path = os.path.join(REPO_ROOT, "mqlaunch.sh")
    
    if not os.path.exists(script_path):
        return f"Fel: Hittade inte mqlaunch.sh på {script_path}"
        
    try:
        # Kör skriptet och fånga output
        process = subprocess.run([script_path], capture_output=True, text=True, check=True)
        return f"mqlaunch.sh kördes framgångsrikt!\n\nOutput:\n{process.stdout}"
    except subprocess.CalledProcessError as e:
        return f"mqlaunch.sh misslyckades med felkod {e.returncode}.\n\nError:\n{e.stderr}"
    except Exception as e:
        return f"Ett oväntat fel uppstod: {str(e)}"

# --- MUSIK & APP-KONTROLL ---

@mcp.tool()
def analyze_guitar_pro(relative_path: str) -> str:
    """Analyserar en Guitar Pro-fil (GP3, GP4, GP5)."""
    try:
        safe_path = os.path.normpath(os.path.join(REPO_ROOT, relative_path))
        song = guitarpro.parse(safe_path)
        return f"Titel: {song.title}, Artist: {song.artist}, Tempo: {song.tempo} BPM"
    except Exception as e: return f"Fel: {str(e)}"

@mcp.tool()
def open_in_app(relative_path: str) -> str:
    """Öppnar en fil i dess standardprogram (t.ex. GP8 eller Photoshop)."""
    try:
        safe_path = os.path.normpath(os.path.join(REPO_ROOT, relative_path))
        subprocess.run(["open", safe_path], check=True)
        return f"Öppnar '{relative_path}'..."
    except Exception as e: return f"Fel: {str(e)}"

# --- CSV & BILD ---

@mcp.tool()
def analyze_csv(relative_path: str) -> str:
    """Analyserar en CSV-fil."""
    try:
        safe_path = os.path.normpath(os.path.join(REPO_ROOT, relative_path))
        df = pd.read_csv(safe_path)
        return f"Rader: {len(df)}, Kolumner: {list(df.columns)}\n{df.describe().to_string()}"
    except Exception as e: return f"Fel: {str(e)}"

@mcp.tool()
def edit_image(relative_path: str, action: str, value: int | None = None) -> str:
    """Redigerar en bild (resize, rotate, grayscale)."""
    try:
        safe_path = os.path.normpath(os.path.join(REPO_ROOT, relative_path))
        with Image.open(safe_path) as img:
            if action == "rotate": img = img.rotate(value or 90, expand=True)
            elif action == "grayscale": img = img.convert("L")
            img.save(safe_path)
            return f"Bilden har uppdaterats ({action})."
    except Exception as e: return f"Fel: {str(e)}"

if __name__ == "__main__":
    mcp.run()
