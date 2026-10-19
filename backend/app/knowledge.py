import json
from pathlib import Path

DATA_DIR = Path("/app/data")


def load_knowledge():
    file_path = DATA_DIR / "insurance_knowledge.json"
    return json.loads(file_path.read_text(encoding="utf-8"))


def load_system_prompt():
    file_path = DATA_DIR / "insurance_system_prompt.txt"
    return file_path.read_text(encoding="utf-8")
