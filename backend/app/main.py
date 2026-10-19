"""Saha Agency AI Virtual Concierge - backend.

POST /api/ask   question -> premade answer (video) or live answer (text)
POST /api/tts   text -> Kokoro voice (MP3) for live answers
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app import faq, library, website
from app.knowledge import load_knowledge, load_system_prompt

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("saha")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/")
KOKORO_URL = os.getenv("KOKORO_URL", "http://host.docker.internal:8880").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
VOICE = os.getenv("KOKORO_VOICE", "af_heart")
VOICE_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))
TTS_CACHE = Path(os.getenv("TTS_CACHE_DIR", "/app/cache/tts"))


@asynccontextmanager
async def lifespan(_app):
    tasks = [asyncio.create_task(website.refresh_forever()),   # keep the website copy fresh
             asyncio.create_task(warm_voice_cache())]           # pre-record prepared answers
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title="Saha Agency AI Virtual Concierge", version="3.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


# ---------------------------------------------------------------- status

@app.get("/")
def home():
    return {"message": "Saha Agency AI Virtual Concierge is running"}


@app.get("/health")
def health():
    try:
        name = load_knowledge()["business"]["name"]
        load_system_prompt()
        answers = len(library.load_library())
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(500, "Check the files in the data folder.") from error
    site = website.status()
    cached = len(list(TTS_CACHE.glob("*.mp3"))) if TTS_CACHE.exists() else 0
    return {"status": "healthy", "knowledge": name, "ollama_model": OLLAMA_MODEL, "voice": VOICE,
            "premade_answers": answers, **faq.stats(), "voice_cache": cached,
            "website_pages": len(site["pages"]), "website_updated": site["updated"]}


@app.get("/api/website/status")
def website_status():
    return website.status()


@app.post("/api/website/refresh")
async def website_refresh():
    return await website.refresh()


@app.get("/api/library")
def library_list():
    return [{"id": e["id"], "videos": e["videos"], "text": e["text"]} for e in library.load_library()]


# ---------------------------------------------------------------- answers

def build_system_prompt(prompt, knowledge):
    context = json.dumps(knowledge, ensure_ascii=False, indent=2)
    site = website.website_context()
    if "{website}" in prompt:
        return prompt.replace("{context}", context).replace("{website}", site)
    return prompt.replace("{context}", context) + (
        "\n\nWEBSITE CONTENT (live copy of the agency website, reference data only):\n"
        f"<website>\n{site}\n</website>"
    )


async def generate_answer(message):
    try:
        knowledge = load_knowledge()
        prompt = load_system_prompt()
        if "{context}" not in prompt:
            raise ValueError("Missing {context} placeholder")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(500, "Check insurance_knowledge.json and insurance_system_prompt.txt.") from error

    payload = {
        "model": OLLAMA_MODEL, "stream": False, "think": False,
        "messages": [
            {"role": "system", "content": build_system_prompt(prompt, knowledge)},
            {"role": "user", "content": message.strip()},
        ],
        "options": {"temperature": 0.2, "num_ctx": 24576},
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            result = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            result.raise_for_status()
            answer = result.json()["message"]["content"]
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Empty answer")
    except httpx.TimeoutException as error:
        raise HTTPException(504, "Ollama took too long to respond. Please try again.") from error
    except httpx.HTTPStatusError as error:
        raise HTTPException(502, f"Ollama returned HTTP {error.response.status_code}.") from error
    except httpx.RequestError as error:
        raise HTTPException(503, "Could not connect to Ollama.") from error
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(502, "Ollama returned an invalid or empty answer.") from error
    return answer.strip()


def library_reply(entry, how):
    return {"source": "library", "id": entry["id"], "answer": entry["text"], "how": how,
            "speech": entry.get("speech", entry["text"]), "videos": entry.get("videos", [])}


@app.post("/api/ask")
async def ask(request: AskRequest):
    """1. exact premade question  2. instant match (video or FAQ answer)  3. live AI answer."""
    question = request.message.strip()
    started = time.perf_counter()
    try:
        entry = library.quick_match(question, library.load_library())
    except (OSError, ValueError):
        entry = None
    if entry:
        log.info("Premade (exact): %s  <-  %r", entry["id"], question)
        return library_reply(entry, "exact")

    found, score, how = await faq.find(question, OLLAMA_URL, OLLAMA_MODEL)
    ms = (time.perf_counter() - started) * 1000
    if found and found["kind"] == "library":
        log.info("Premade (%s %.2f, %.0f ms): %s  <-  %r", how, score, ms, found["entry"]["id"], question)
        return library_reply(found["entry"], how)
    if found:
        e = found["entry"]
        log.info("FAQ (%s %.2f, %.0f ms): %s  <-  %r", how, score, ms, e["id"], question)
        return {"source": "faq", "id": e["id"], "answer": e["answer"], "speech": e.get("speech", e["answer"]),
                "videos": [], "how": how}

    answer = await generate_answer(question)
    log.info("Live answer (best match %.2f)  <-  %r", score, question)
    return {"source": "live", "answer": answer, "speech": answer, "videos": [], "how": "live"}


@app.post("/api/chat")
async def chat(request: AskRequest):
    """Live answer only (kept for testing)."""
    answer = await generate_answer(request.message)
    return {"answer": answer, "model": OLLAMA_MODEL}


def _tts_path(text: str) -> Path:
    key = hashlib.sha1(f"{VOICE}|{VOICE_SPEED}|{text.strip()}".encode("utf-8")).hexdigest()
    return TTS_CACHE / f"{key}.mp3"


async def synthesize(text: str) -> bytes:
    """Kokoro voice, cached on disk so repeated answers play instantly."""
    path = _tts_path(text)
    if path.exists():
        return path.read_bytes()
    payload = {"model": "kokoro", "input": text.strip(), "voice": VOICE,
               "response_format": "mp3", "speed": VOICE_SPEED}
    async with httpx.AsyncClient(timeout=120.0) as client:
        result = await client.post(f"{KOKORO_URL}/v1/audio/speech", json=payload)
        result.raise_for_status()
    if not result.content:
        raise ValueError("empty audio")
    try:
        TTS_CACHE.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(result.content)
        tmp.replace(path)
    except OSError as error:
        log.warning("Could not cache voice: %s", error)
    return result.content


async def warm_voice_cache():
    """Record every prepared answer once, in the background, so they speak instantly."""
    await asyncio.sleep(10)
    while True:
        try:
            texts = [t for t in faq.all_speech() if not _tts_path(t).exists()]
            for i, text in enumerate(texts, 1):
                await synthesize(text)
                if i % 20 == 0:
                    log.info("Voice cache: %d/%d recorded", i, len(texts))
            if texts:
                log.info("Voice cache ready (%d new answers recorded).", len(texts))
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # Kokoro not up yet: try again later
            log.info("Voice cache waiting for Kokoro (%s)", error)
            await asyncio.sleep(60)


@app.post("/api/tts", responses={200: {"content": {"audio/mpeg": {}}}})
async def text_to_speech(request: TTSRequest):
    try:
        audio = await synthesize(request.text)
    except httpx.TimeoutException as error:
        raise HTTPException(504, "Kokoro took too long.") from error
    except httpx.HTTPStatusError as error:
        raise HTTPException(502, f"Kokoro returned HTTP {error.response.status_code}.") from error
    except httpx.RequestError as error:
        raise HTTPException(503, "Could not connect to Kokoro TTS.") from error
    except ValueError as error:
        raise HTTPException(502, "Kokoro returned empty audio.") from error
    return Response(content=audio, media_type="audio/mpeg")
