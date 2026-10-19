# Saha Agency — AI Virtual Concierge (AVC)

A real-person virtual receptionist for **Saha Agency** (insurance, Woodbridge, VA), built to run on a reception screen.
Visitors tap the microphone (or type) and ask a question:

- **Common questions** → she answers with a premade video of herself (31 clips, made in Google Flow).
- **Anything else** → a live answer from a local AI model (Qwen via Ollama) using the agency's facts and its website,
  spoken with a Kokoro voice over her "talking" video loop.
- If a premade video file is missing, that answer is spoken live instead — nothing breaks.

Everything runs locally on the agency PC. No cloud AI services are required.

## How it works

```
Visitor  ──►  Screen (Vite, Chrome)  ──►  Backend (FastAPI, Docker)  ──►  Ollama  (qwen3:8b)
   ▲              │ premade video                │ live answer            Kokoro TTS (voice)
   └──────────────┘ or voice + talking loop       └─ sahaagency.com copy (refreshed every 6 h)
```

1. **Matching** — `backend/app/library.py` checks the question against `data/answer_library.json`:
   an instant exact match on ~190 example questions, otherwise Qwen picks the matching answer or "none".
2. **Premade answer** — the screen plays `library/<id>.mp4` (with her own voice). Two-part answers play back to back.
3. **Live answer** — Qwen answers from `data/insurance_knowledge.json` + the website text; Kokoro speaks it.

## Requirements (Windows PC)

| Needed | Notes |
|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | runs the backend container `saha-avc-api` (port 8081) |
| [Ollama](https://ollama.com) with `qwen3:8b` | `ollama pull qwen3:8b` |
| Kokoro TTS on port 8880 | e.g. the `kokoro-fastapi` Docker image (GPU or CPU) |
| [Node.js](https://nodejs.org) 20+ | runs the screen |
| Google Chrome or Microsoft Edge | needed for voice input |

## Install

```powershell
git clone https://github.com/shawonrealtor-code/SahaAgencyAVC.git "C:\Saha AVC"
cd "C:\Saha AVC"
powershell -ExecutionPolicy Bypass -File .\INSTALL.ps1
```

(Or download the ZIP from GitHub, extract it, and run `INSTALL.ps1` from that folder.)

## Run (every day)

```powershell
cd "C:\Saha AVC"
powershell -ExecutionPolicy Bypass -File .\START.ps1
```

Chrome opens the concierge at http://localhost:5173 — press **F11** for full screen and tap the screen once
(browsers need one tap before they play sound).

## Project layout

```
backend/                 FastAPI app (Docker): /api/ask, /api/tts, /api/library, /health
  app/main.py            answer flow, Ollama + Kokoro calls
  app/library.py         premade-answer matching
  app/website.py         sahaagency.com crawler (cached, refreshed every 6 h)
data/
  answer_library.json    premade answers: text, spoken line, video files, example questions
  insurance_knowledge.json  agency facts for live answers
  insurance_system_prompt.txt  rules for the live AI answers
avatar-frontend/         the screen (vanilla JS + Vite)
  src/config.js          quick-tap questions, contact details, backend URL
  src/components/VideoConcierge.js  video layers, cross-fades, premade clip playback
  public/videos/         idle_loop, listening, thinking, talking_base (muted loops)
  public/videos/library/ 31 premade answer videos
tools/prepare_clips.py   trims silence and evens the volume of new Flow clips (needs ffmpeg)
FLOW_PROMPTS.txt         Google Flow prompt for every answer video
saha-start-frame.png     first frame to use for every Flow clip
compose.yaml             backend container settings (model, voice, website)
INSTALL.ps1 / START.ps1  one-time install / daily start
voice-samples.ps1        listen to the Kokoro voices
```

## Common changes

- **Edit an answer or add example questions** → `data/answer_library.json`, then `docker compose up -d --build`.
- **Add or replace an answer video** → make it in Google Flow with `saha-start-frame.png` as the first frame
  (prompts in `FLOW_PROMPTS.txt`), save as `avatar-frontend/public/videos/library/<file name>.mp4`, refresh Chrome.
- **Change the live voice** → `KOKORO_VOICE` / `KOKORO_SPEED` in `compose.yaml`, then `docker compose up -d --build`.
- **Quick-tap questions / phone / address on screen** → `avatar-frontend/src/config.js`.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Concierge offline" on screen | Docker Desktop not running, or `docker logs saha-avc-api` |
| "I'm having trouble thinking" | Start Ollama |
| Videos play but no sound | Tap the screen once, then ask again |
| Live answers have no voice | Kokoro is not running on port 8880 |
| Screen opens on port 5174 | An old concierge window is still running — close it |
