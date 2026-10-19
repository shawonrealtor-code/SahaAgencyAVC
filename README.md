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

1. **Exact match** — a question identical to a prepared one answers immediately.
2. **Instant match** — `backend/app/faq.py` compares the question with ~1,190 prepared questions
   (the 29 video answers + 100 FAQ topics in `data/faq.json`) in about a millisecond, no AI needed.
   Borderline questions let Qwen choose between the top 4 candidates (about half a second).
3. **Premade answer** — if the match has a video, the screen plays `library/<id>.mp4` with her own voice.
   Otherwise the FAQ answer is spoken with Kokoro; every prepared answer is pre-recorded in the
   background (`cache/tts`), so it starts playing instantly.
4. **Live answer** — anything else: Qwen answers from `data/insurance_knowledge.json` + the website.

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

**Permanent (recommended): `ONLINE.ps1`** — puts the PC backend on your free ngrok static domain
(e.g. `https://saha-concierge.ngrok-free.app`). First run asks for the ngrok Authtoken and domain
(dashboard.ngrok.com) and remembers them. With that domain in `backend.json` (below), plain
`https://securepayllc.com/` works for every visitor. Keep the ONLINE window open.

The quick-tunnel address changes every time `TUNNEL.ps1` restarts. For the plain address
(`https://securepayllc.com/`) to work for every visitor, give the PC backend a **permanent** address
(a named Cloudflare Tunnel such as `https://api.securepayllc.com`, or a free ngrok static domain) and put it in
`avatar-frontend/public/backend.json`:

```json
{ "api": "https://api.securepayllc.com" }
```

Commit it on GitHub — the hosting service redeploys and every device uses it automatically.
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
  app/library.py         premade video answers (exact matches)
  app/faq.py             instant matching over all prepared questions
  app/website.py         sahaagency.com crawler (cached, refreshed every 6 h)
data/
  answer_library.json    premade answers: text, spoken line, video files, example questions
  faq.json               100 instant answers x 10 phrasings (built by tools/build_faq.py)
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
UPDATE.ps1               get the latest version from GitHub and rebuild
ONLINE.ps1               permanent public address for the PC backend (ngrok) - hosted site works for everyone
TUNNEL.ps1               temporary public address (Cloudflare quick tunnel, needs ?api= link)
voice-samples.ps1        listen to the Kokoro voices
```

## Instant answers (FAQ)

`data/faq.json` holds 100 answers, each with 10 ways of asking (1,000 questions), covering general,
auto, home, renters/landlord, life, health, business, claims, payments and customer-support questions.
Answers follow the agency rules: no prices, carriers or guarantees, and lines the agency doesn't list
(life, health, renters, landlord) point visitors to an advisor.

- To edit: change `tools/faq_source_1.py` / `faq_source_2.py`, run `python tools/build_faq.py`,
  then `python backend/tests/test_faq_match.py` (matching accuracy check, currently 93/98 with no wrong instant answers).
- Small text edits can also be made directly in `data/faq.json`; the backend reloads it automatically.

## Updating the office PC

```powershell
powershell -ExecutionPolicy Bypass -File .\UPDATE.ps1
```

Downloads the latest version from GitHub, rebuilds the backend and keeps your PC-only settings.

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
