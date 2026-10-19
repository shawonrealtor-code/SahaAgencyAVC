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

## Using it on phones, tablets or the hosted website

The AI (Docker backend, Ollama, Kokoro) always runs on the office PC. Other devices reach it in one of two ways:

**A. Hosted website (e.g. securepayllc.com, built from this repo)** — the hosting service only serves the
page and videos, so the PC's backend needs a public address:

1. On the PC run `START.ps1`, then `TUNNEL.ps1` (installs Cloudflare's free tunnel the first time).
2. It prints and copies a link like `https://securepayllc.com/?api=https://abc-xyz.trycloudflare.com`.
3. Open that link once on each phone/tablet/screen — the device remembers it. Keep the TUNNEL window open.

The quick-tunnel address changes every time `TUNNEL.ps1` restarts. For a permanent address, create a named
Cloudflare Tunnel (e.g. `api.securepayllc.com` → `http://localhost:8081`) and set the build variable
`VITE_API_BASE=https://api.securepayllc.com` on the hosting service — then no `?api=` link is needed.
(Open `?api=` with nothing after it to clear a remembered address on a device.)

**B. Same Wi-Fi, no hosting** — open the "Other devices" address `START.ps1` prints (e.g. `http://192.168.1.20:5173`);
the screen server forwards `/api` to the backend (`avatar-frontend/vite.config.js`). Allow Node.js in Windows Firewall.

Notes: phones only allow the microphone on **https** pages. On iPhone/iPad tap the screen once before asking so
Safari allows sound; voice input needs Siri & Dictation enabled (otherwise use the keyboard button).
Anyone who can open the address can use the concierge.

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
TUNNEL.ps1               public address for the PC backend (hosted site, phones anywhere)
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
