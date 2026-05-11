"""Adapter for the user's local voice-clone TTS server.

Server contract (from API.md):
  POST /api/generate
    multipart form: voice_id, text, speed, format
    header: X-API-Key
    returns: raw audio bytes (audio/wav or audio/mpeg)
  GET  /api/health           → { status, device, voices, auth_required }
  GET  /api/voices           → { voices: [{ voice_id, name, description, … }] }

Key engineering choices:
  * Long timeouts. CPU generation can take 5+ minutes. We default to 15 min
    per request so a slow scene doesn't fail spuriously.
  * Audio duration is measured via ffprobe after save (the server gives us no
    duration). The pipeline needs duration to set scene length.
  * Pause tags `<break time="1s" />` are passed through verbatim — the server
    handles them. We never inject breaks automatically.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import httpx

from .models import TTSHealth, VoiceProfile


class TTSError(RuntimeError):
    """Raised when the TTS server returns a non-2xx response or unreachable."""


@dataclass(frozen=True)
class GeneratedAudio:
    """Result of a generate call. Path is absolute, duration in seconds."""
    path: Path
    duration_seconds: float


# Default per-request budget. CPU XTTS can chew through long scripts slowly;
# we'd rather wait than spurious-fail and waste the work done before.
DEFAULT_TIMEOUT_SECONDS = 900.0          # 15 minutes
HEALTH_CHECK_TIMEOUT_SECONDS = 10.0


def health_check(server_url: str, api_key: str | None = None) -> TTSHealth:
    """Probe `/api/health`. Auth is not required for this endpoint, but
    we send the key anyway in case the server policy changes.

    Returns a populated TTSHealth even on failure — `reachable=False` and
    `error` will be set. Never raises, so the UI can render a clear
    'TTS server unreachable' state without try/except boilerplate.
    """
    url = _join(server_url, "/api/health")
    headers = {"X-API-Key": api_key} if api_key else {}
    try:
        with httpx.Client(timeout=HEALTH_CHECK_TIMEOUT_SECONDS) as c:
            r = c.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
        return TTSHealth(
            status=data.get("status", "unknown"),
            device=data.get("device"),
            voices=data.get("voices"),
            auth_required=data.get("auth_required"),
            reachable=True,
        )
    except Exception as e:
        return TTSHealth(status="unreachable", reachable=False, error=str(e))


def list_voices(server_url: str, api_key: str) -> list[dict]:
    """Fetch `/api/voices`. Returns the raw list of dicts so the frontend
    can render any fields the server adds in future versions."""
    url = _join(server_url, "/api/voices")
    with httpx.Client(timeout=HEALTH_CHECK_TIMEOUT_SECONDS) as c:
        r = c.get(url, headers={"X-API-Key": api_key})
        r.raise_for_status()
        return r.json().get("voices", [])


def generate(
    profile: VoiceProfile,
    text: str,
    output_path: Path,
    *,
    speed: float = 1.0,
    fmt: str = "mp3",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> GeneratedAudio:
    """Generate one audio file. Returns its path + measured duration.

    The server handles long-text chunking internally, so we never split.

    `fmt` is "mp3" or "wav". MP3 is 192kbps — fine for video narration and
    one-third the bytes of WAV, which matters when scenes are 60+ seconds.
    """
    if not text.strip():
        raise TTSError("Empty narration text — cannot synthesize silence.")

    url = _join(profile.server_url, "/api/generate")
    headers = {"X-API-Key": profile.api_key}
    data = {
        "voice_id": profile.voice_id,
        "text": text,
        "speed": str(speed),
        "format": fmt,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(timeout=timeout_seconds) as c:
            # Stream so we can write a multi-MB response to disk without
            # buffering it all in memory (long narration on WAV can be 50MB+).
            with c.stream("POST", url, headers=headers, data=data) as r:
                if r.status_code != 200:
                    # Try to surface the server's JSON detail when present.
                    try:
                        detail = r.read().decode("utf-8", errors="replace")
                        as_json = json.loads(detail)
                        msg = as_json.get("detail", detail)
                    except Exception:
                        msg = f"HTTP {r.status_code}"
                    raise TTSError(f"TTS server rejected request: {msg}")

                with open(output_path, "wb") as fh:
                    for chunk in r.iter_bytes(chunk_size=64 * 1024):
                        fh.write(chunk)
    except httpx.RequestError as e:
        raise TTSError(f"TTS server unreachable: {e}") from e

    duration = _ffprobe_duration(output_path)
    return GeneratedAudio(path=output_path, duration_seconds=duration)


# ─── helpers ──────────────────────────────────────────────────────────────


def _join(base: str, path: str) -> str:
    base = base.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _ffprobe_duration(path: Path) -> float:
    """Read media duration via ffprobe. Required because the TTS server
    doesn't return duration in its response headers."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise TTSError(
            f"ffprobe failed reading {path.name}: {result.stderr.strip()}"
        )
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception as e:
        raise TTSError(f"Could not parse duration from ffprobe: {e}") from e
