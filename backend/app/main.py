"""FastAPI application — every route the frontend calls.

Run with:  uvicorn app.main:app --port 8765

Route map:

  GET  /api/health                       liveness probe
  GET  /api/config                       read AppConfig (sans secrets in v2 we keep them — local-only app)
  PUT  /api/config                       replace whole AppConfig (validated)
  POST /api/config/voice-profiles        add a voice profile
  DELETE /api/config/voice-profiles/{id} remove

  GET  /api/tts/health?profile_id=…      probe the user's TTS server
  GET  /api/tts/voices?profile_id=…      list voices on the TTS server

  GET  /api/styles                       all styles (builtin + custom)
  POST /api/styles                       add a custom style
  DELETE /api/styles/{key}               remove a custom style (builtins refused)

  GET  /api/hyperframes/status           installed + latest + last smoke result
  POST /api/hyperframes/update           install latest
  POST /api/hyperframes/smoke-test       render smoke fixture; returns result

  POST /api/jobs                         enqueue a new job
  GET  /api/jobs                         list jobs (most recent first)
  GET  /api/jobs/{id}                    one job (polled by UI)
  POST /api/jobs/{id}/cancel             cancel queued or stop-after-current-scene
  POST /api/jobs/{id}/retry              re-queue failed/cancelled (resume semantics)
  DELETE /api/jobs/{id}                  remove from list (non-running only)

  GET  /api/files/output?folder=…        list .mp4s in a folder (Library page)

All non-trivial work runs in jobs.py's worker thread — routes are thin.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import config, hyperframes_update, jobs, styles, tts
from .models import AppConfig, Job, JobRequest, Style, VoiceProfile


# Path to the bundled frontend (served at /). Resolves to v2/frontend/.
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"

app = FastAPI(title="Video Generator v2", version="2.0.0")

# Dev convenience: the Vite dev server runs on a different port. In
# production we'll serve the built SPA from the same origin so this is
# wide-open only locally.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup() -> None:
    jobs.start_worker()


@app.on_event("shutdown")
def _on_shutdown() -> None:
    jobs.stop_worker()


# ─── health ───────────────────────────────────────────────────────────────


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ─── config ───────────────────────────────────────────────────────────────


@app.get("/api/config", response_model=AppConfig)
def get_config() -> AppConfig:
    return config.load()


@app.put("/api/config", response_model=AppConfig)
def put_config(cfg: AppConfig) -> AppConfig:
    config.save(cfg)
    return cfg


@app.post("/api/config/voice-profiles", response_model=VoiceProfile)
def add_voice_profile(profile: VoiceProfile) -> VoiceProfile:
    def mutate(cfg: AppConfig) -> None:
        # Replace if id collides, otherwise append.
        cfg.voice_profiles = [p for p in cfg.voice_profiles if p.id != profile.id]
        cfg.voice_profiles.append(profile)
    config.update(mutate)
    return profile


@app.delete("/api/config/voice-profiles/{profile_id}")
def delete_voice_profile(profile_id: str) -> dict:
    def mutate(cfg: AppConfig) -> None:
        cfg.voice_profiles = [p for p in cfg.voice_profiles if p.id != profile_id]
    config.update(mutate)
    return {"ok": True}


# ─── TTS proxy (UI calls the user's TTS server via the backend so CORS
#     and key handling stay on the server) ───────────────────────────────


@app.get("/api/tts/health")
def tts_health(profile_id: str) -> dict:
    cfg = config.load()
    profile = next((p for p in cfg.voice_profiles if p.id == profile_id), None)
    if not profile:
        raise HTTPException(404, f"Voice profile '{profile_id}' not found.")
    return tts.health_check(profile.server_url, profile.api_key).model_dump()


@app.get("/api/tts/voices")
def tts_voices(profile_id: str) -> dict:
    cfg = config.load()
    profile = next((p for p in cfg.voice_profiles if p.id == profile_id), None)
    if not profile:
        raise HTTPException(404, f"Voice profile '{profile_id}' not found.")
    try:
        return {"voices": tts.list_voices(profile.server_url, profile.api_key)}
    except Exception as e:
        raise HTTPException(502, f"TTS server error: {e}") from e


# ─── styles ───────────────────────────────────────────────────────────────


@app.get("/api/styles", response_model=list[Style])
def list_styles() -> list[Style]:
    return styles.all_styles()


@app.post("/api/styles", response_model=Style)
def add_style(style: Style) -> Style:
    if style.key in styles.builtin_keys():
        raise HTTPException(400, f"'{style.key}' is a built-in style.")
    def mutate(cfg: AppConfig) -> None:
        cfg.custom_styles = [s for s in cfg.custom_styles if s.key != style.key]
        cfg.custom_styles.append(style)
    config.update(mutate)
    return style


@app.delete("/api/styles/{key}")
def delete_style(key: str) -> dict:
    if key in styles.builtin_keys():
        raise HTTPException(400, "Built-in styles cannot be deleted.")
    def mutate(cfg: AppConfig) -> None:
        cfg.custom_styles = [s for s in cfg.custom_styles if s.key != key]
    config.update(mutate)
    return {"ok": True}


# ─── HyperFrames management ───────────────────────────────────────────────


@app.get("/api/hyperframes/status")
def hf_status() -> dict:
    return hyperframes_update.status().model_dump()


@app.post("/api/hyperframes/update")
def hf_update() -> dict:
    try:
        new_version = hyperframes_update.install_latest()
        return {"installed_version": new_version}
    except hyperframes_update.InstallError as e:
        raise HTTPException(500, str(e)) from e


@app.post("/api/hyperframes/smoke-test")
def hf_smoke_test() -> dict:
    ok, err = hyperframes_update.smoke_test()
    return {"passed": ok, "error": err}


# ─── jobs ─────────────────────────────────────────────────────────────────


@app.post("/api/jobs", response_model=Job)
def create_job(req: JobRequest) -> Job:
    # Light pre-validation: voice profile must exist.
    cfg = config.load()
    if not any(p.id == req.voice_profile_id for p in cfg.voice_profiles):
        raise HTTPException(400, f"Voice profile '{req.voice_profile_id}' not found.")
    return jobs.enqueue(req)


@app.get("/api/jobs", response_model=list[Job])
def list_jobs() -> list[Job]:
    return jobs.list_all()


@app.get("/api/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, f"Job '{job_id}' not found.")
    return j


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    if not jobs.cancel(job_id):
        raise HTTPException(404, f"Job '{job_id}' not found or not cancellable.")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str) -> dict:
    if not jobs.retry(job_id):
        raise HTTPException(400, "Job is not in a retryable state.")
    return {"ok": True}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    if not jobs.delete(job_id):
        raise HTTPException(400, "Job is running or doesn't exist.")
    return {"ok": True}


# ─── library: list mp4s in an output folder ───────────────────────────────


@app.post("/api/dialog/pick-folder")
def pick_folder() -> dict:
    """Open the native OS folder picker (tkinter). Blocks the API thread
    until the user picks or cancels — fine because uvicorn is multi-worker
    and this app has one human user.

    Returns: {"path": "<chosen path>"} or {"path": null} on cancel.

    On Windows this shows the standard Explorer folder browser. On macOS
    it shows the native AppleScript folder chooser. On headless Linux
    where tkinter has no display, raises 500 with a clear message.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as e:
        raise HTTPException(500, f"tkinter unavailable: {e}")
    try:
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        folder = filedialog.askdirectory(title="Select output folder")
        root.destroy()
        return {"path": folder or None}
    except Exception as e:
        raise HTTPException(500, f"Folder picker error: {e}")


@app.get("/api/files/output")
def list_output(folder: str) -> dict:
    p = Path(folder).expanduser()
    if not p.exists() or not p.is_dir():
        return {"files": []}
    out: list[dict] = []
    for f in sorted(p.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        st = f.stat()
        out.append({
            "name": f.name,
            "path": str(f),
            "size_bytes": st.st_size,
            "mtime": st.st_mtime,
        })
    return {"files": out}


@app.get("/api/files/stream")
def stream_video(path: str):
    """Serve any local .mp4 by absolute path. Used by the Library page to
    preview a video in-browser. Only mp4/webm are allowed to reduce abuse."""
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "File not found.")
    if p.suffix.lower() not in (".mp4", ".webm", ".mov"):
        raise HTTPException(400, "Only video files may be streamed.")
    return FileResponse(p, media_type="video/mp4")


# ─── frontend static serving (registered AFTER all /api routes) ───────────


if FRONTEND_DIR.exists():
    # Serve the SPA's static assets. The catch-all SPA fallback lives below.
    app.mount(
        "/src",
        StaticFiles(directory=str(FRONTEND_DIR / "src")),
        name="frontend-src",
    )

    @app.get("/", response_class=HTMLResponse)
    def _root_index() -> HTMLResponse:
        index = FRONTEND_DIR / "index.html"
        if not index.exists():
            return HTMLResponse(
                "<h1>Frontend not built yet</h1>"
                "<p>Expected file: " + str(index) + "</p>",
                status_code=500,
            )
        return HTMLResponse(index.read_text(encoding="utf-8"))
