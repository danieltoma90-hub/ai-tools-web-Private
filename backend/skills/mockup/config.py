import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"

load_dotenv(ROOT / ".env")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"
MANDATORY_FILTERS = {"Data", "Gestiunea"}


def ensure_dirs():
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
