# Video Generator v2

A multi-style HyperFrames-based video generator. Build any kind of short or
long-form video — motion-graphic explainers, kinetic typography, product
demos, personal-branding shorts, hand-drawn whiteboard — from any kind of
script. Queue multiple jobs. Resume after crashes. Designed for Windows.

## What it does

1. **Script intake.** Paste any text — tagged scenes, whiteboard `Point N:`,
   or freeform. The system auto-detects the format and routes accordingly.
2. **Audio.** Calls your local TTS server (your own voice-clone tool, not
   ElevenLabs) to generate narration with the voice profile you pick.
3. **Visuals.** Claude generates HyperFrames-compliant HTML per scene,
   following the style guidance you configure.
4. **Render.** `npx hyperframes render` turns the HTML into an MP4. ffmpeg
   merges audio and concats scenes.
5. **Save.** The final video lands in your output folder, named after the
   title you provided. Collisions auto-suffix (`title.mp4`, `title_2.mp4`,
   …) — videos are never overwritten.
6. **Queue.** Submit many jobs; the worker processes them one at a time.
   Runs for hours or days; crashes/power-cuts don't lose work.

## Run on Windows (the primary target)

### One-time setup

Make sure these are installed and on your PATH:

| Tool | Install command |
|---|---|
| Python 3.11 or newer | `winget install Python.Python.3.12`  (tick "Add to PATH" in the installer) |
| Node.js LTS | `winget install OpenJS.NodeJS.LTS` |
| ffmpeg | `winget install Gyan.FFmpeg` |

Reopen PowerShell after installing so the new PATH entries are picked up.

### Daily use

**Double-click `start.bat`** in the `v2/` folder. The first run will:

- Create the Python virtual environment (`.venv\`).
- Install Python dependencies (FastAPI, Anthropic SDK, etc.).
- Install HyperFrames globally via `npm install -g hyperframes`.
- Open `http://localhost:8765` in your browser.

A black window stays open showing live logs. **Press Ctrl+C in that window
to stop the server.** Closing the window also stops it.

Subsequent runs are fast — only the actual server start (a few seconds).

### Run on macOS or Linux

```bash
cd v2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install -g hyperframes
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Then open <http://localhost:8765>.

## First-time configuration

After launching, the dashboard prompts you to add:

1. **Anthropic API key** — Settings → API keys.
2. **A voice profile** — Settings → Voice profiles → "Add new profile".
   - Server URL: `http://127.0.0.1:8000` (your local TTS server).
   - API key: the `vct_…` key from your TTS server's web UI.
   - Voice ID: 12-char hex from your TTS server.
   - Click "Test" to verify the server is reachable.

Once both are set, click "New job" and you're ready.

## Architecture

```
v2/
├── start.bat                ← Windows launcher (double-click)
├── README.md                ← this file
├── requirements.txt         ← Python deps
├── package.json             ← pins hyperframes version
│
├── backend/                 ← FastAPI server on :8765
│   ├── app/
│   │   ├── main.py          ← HTTP routes + static SPA serving
│   │   ├── models.py        ← Pydantic types (Job, Style, VoiceProfile, …)
│   │   ├── config.py        ← Persists ~/.video-gen-v2/config.json
│   │   ├── paths.py         ← Filename collision → auto _2/_3 suffix
│   │   ├── manifest.py      ← Per-job staging dir + resume manifest
│   │   ├── script_parser.py ← Detect tagged/whiteboard/freeform + parse
│   │   ├── styles.py        ← 5 built-in styles + user-defined storage
│   │   ├── tts.py           ← Adapter for your local TTS server
│   │   ├── claude.py        ← Script normalizer + HTML generator
│   │   ├── hyperframes.py   ← Correct HTML scaffold + npx renderer
│   │   ├── hyperframes_update.py  ← Auto-update + smoke-test fixture
│   │   ├── composer.py      ← ffmpeg merge + concat (with crossfades)
│   │   └── jobs.py          ← Queue worker (single-threaded, sequential)
│   ├── config/              ← created on first run
│   └── workspace/           ← transient per-job working files
│
└── frontend/                ← single-page app (no build step!)
    ├── index.html           ← shell — loads Lit + Tailwind from CDN
    └── src/
        ├── main.js          ← entry point
        ├── app.js           ← sidebar + router shell
        ├── api.js           ← backend HTTP client
        ├── router.js        ← hash-based router
        ├── state.js         ← observable store + polling
        ├── components.js    ← Card, Button, Badge, Input, …
        ├── styles.css       ← layered on top of Tailwind
        └── pages/
            ├── dashboard.js
            ├── new-job.js
            ├── queue.js
            ├── library.js
            ├── settings.js
            └── styles.js
```

## HyperFrames contract (what the HTML generator emits)

Per HeyGen's official `claude-design-hyperframes.md`:

- Full `<!doctype html><html><head>…</head><body>…</body></html>` wrapper.
- Three CDN scripts loaded in `<head>` in order:
  1. `gsap@3.14.2`
  2. `@hyperframes/core/dist/hyperframe.runtime.iife.js` ← this auto-creates
     `window.__hf = { duration, seek }` from the data attributes; we don't
     touch it manually.
  3. `@hyperframes/shader-transitions` (optional)
- Root `<div id="main" data-composition-id="main" data-width data-height data-start="0" data-duration>`.
- Each scene: `<div class="scene clip" id="sN" data-start data-duration data-track-index="0" style="visibility:hidden">` containing `<div class="scene-content">`.
- Timeline: `window.__timelines["main"] = gsap.timeline({paused: true})`, with `tl.set("#sN", {autoAlpha: 1}, t)` to reveal scenes.

The system generates **one composition per scene** (single-scene-per-render)
so we can resume + re-cut individual scenes. Each scene MP4 is concatenated
into the final video by ffmpeg.

## Crash safety / resume

Each running job has a `<title>_partial/` folder next to where its final
MP4 will land:

```
<output_folder>/
  My Video.mp4               ← only written on full success
  My Video_partial/
    scenes/
      scene_001.mp4          ← staged as each scene finishes
      scene_002.mp4
      …
    run_manifest.json        ← script hash + completed indices
```

If the process dies mid-job (power cut, Windows update reboot, crash),
re-launching and starting the same job (same title, same script, same
style, same canvas) **resumes from the scene after the last one staged**.
Already-rendered scenes are reused — no API calls re-spent.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET    | `/api/health` | liveness probe |
| GET    | `/api/config` | read AppConfig |
| PUT    | `/api/config` | replace whole AppConfig |
| POST   | `/api/config/voice-profiles` | add a voice profile |
| DELETE | `/api/config/voice-profiles/{id}` | remove |
| GET    | `/api/tts/health?profile_id=…` | probe TTS server |
| GET    | `/api/tts/voices?profile_id=…` | list voices on TTS server |
| GET    | `/api/styles` | all styles (built-in + custom) |
| POST   | `/api/styles` | add a custom style |
| DELETE | `/api/styles/{key}` | remove (built-ins refused) |
| GET    | `/api/hyperframes/status` | installed + latest version |
| POST   | `/api/hyperframes/update` | npm install -g latest |
| POST   | `/api/hyperframes/smoke-test` | render a fixture composition |
| POST   | `/api/jobs` | enqueue a job |
| GET    | `/api/jobs` | list jobs (newest first) |
| GET    | `/api/jobs/{id}` | one job (polled by the queue UI) |
| POST   | `/api/jobs/{id}/cancel` | cancel queued or stop-after-current-scene |
| POST   | `/api/jobs/{id}/retry` | re-queue failed/cancelled (resumes) |
| DELETE | `/api/jobs/{id}` | remove from list (non-running only) |
| GET    | `/api/files/output?folder=…` | list .mp4s in a folder |
| GET    | `/api/files/stream?path=…` | stream a local .mp4 for preview |

## Where state lives on disk

| What | Where |
|---|---|
| API keys, voice profiles, defaults | `%USERPROFILE%\.video-gen-v2\config.json` |
| Job queue + history | `%USERPROFILE%\.video-gen-v2\queue.json` |
| Per-job transient files | `v2\backend\workspace\<job_id>\` |
| Per-job staged scenes | `<your output folder>\<title>_partial\` |
| Final videos | `<your output folder>\<title>.mp4` |

Wipe `.video-gen-v2\` to reset all settings without losing your videos.

## Updating HyperFrames

The dashboard sidebar shows the installed and latest version. When they
diverge, the badge turns amber. Go to **Settings → HyperFrames** and click
**Update**. Then click **Smoke test** to verify the new version still
renders our HTML scaffold correctly. If the smoke test fails, the test's
error message tells you which contract changed — paste it to me and I'll
fix the prompt.

## Stopping the server

The black window is uvicorn running in the foreground. Click into it and
press **Ctrl+C**. The server exits cleanly. Running jobs are paused (their
staged scenes survive); pending jobs stay in the queue and resume on the
next launch.
