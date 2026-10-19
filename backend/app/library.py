"""Premade answers: match a visitor's question to one of the prepared answers.

1) Fast check: the question is (almost) the same as one of the example questions.
2) Otherwise Qwen decides which prepared answer fits, or "none".
"""

import json
import logging
import re
from pathlib import Path

import httpx

log = logging.getLogger("saha.library")
LIBRARY_FILE = Path("/app/data/answer_library.json")
SKIP_IDS = {"not_sure"}  # used by the screen as a fallback, never matched directly


def load_library() -> list[dict]:
    data = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
    return [entry for entry in data.get("answers", []) if entry.get("id")]


FILLER = re.compile(r"^(please |can you tell me |could you tell me |tell me |i want to know |i would like to know |"
                    r"excuse me |hi |hello |hey )+|( please| thanks| thank you)$")


def _normalize(text: str) -> str:
    text = text.lower().replace("&", " and ").replace("'", "")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    stripped = FILLER.sub("", text).strip()
    return stripped or text


def quick_match(question: str, entries: list[dict]) -> dict | None:
    q = _normalize(question)
    if not q:
        return None
    for entry in entries:
        if entry["id"] in SKIP_IDS:
            continue
        for example in entry.get("questions", []):
            if q == _normalize(example):
                return entry
    return None


ROUTER_PROMPT = """You route a visitor's question at an insurance agency's reception screen to a prepared answer.

Prepared answers:
{catalog}

Rules:
- Choose an id only if that prepared answer fully and directly answers the visitor's question.
- If the question asks for something more specific, different, or combined (prices, a specific situation,
  eligibility, two topics at once, anything not covered), choose "none".
- Greetings, thanks and goodbyes match their prepared answers.
Reply with JSON only: {{"id": "<one id from the list or none>"}}"""


def _catalog(entries: list[dict]) -> str:
    lines = []
    for entry in entries:
        if entry["id"] in SKIP_IDS:
            continue
        examples = "; ".join(entry.get("questions", [])[:8])
        lines.append(f'- {entry["id"]}: answers "{entry["text"][:110]}" (e.g. {examples})')
    return "\n".join(lines)


async def match(question: str, ollama_url: str, model: str) -> dict | None:
    """Return the matching library entry, or None for a live answer."""
    try:
        entries = load_library()
    except (OSError, ValueError) as error:
        log.warning("Answer library not available: %s", error)
        return None

    entry = quick_match(question, entries)
    if entry:
        return entry

    payload = {
        "model": model, "stream": False, "think": False, "format": "json",
        "messages": [
            {"role": "system", "content": ROUTER_PROMPT.format(catalog=_catalog(entries))},
            {"role": "user", "content": question.strip()},
        ],
        "options": {"temperature": 0, "num_predict": 30, "num_ctx": 8192},
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await client.post(f"{ollama_url}/api/chat", json=payload)
            result.raise_for_status()
            choice = json.loads(result.json()["message"]["content"]).get("id", "none")
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        log.warning("Library matching skipped: %s", error)
        return None

    by_id = {entry["id"]: entry for entry in entries if entry["id"] not in SKIP_IDS}
    return by_id.get(str(choice).strip())
