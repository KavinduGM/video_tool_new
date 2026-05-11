"""Core domain types. Everything that crosses module boundaries — HTTP
request bodies, persisted JSON, queue messages — is one of these.

Designed to be Pydantic-validated so the frontend gets clear 422s on bad
input and the backend never has to second-guess a dict's shape.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ─── enums ────────────────────────────────────────────────────────────────


class CanvasKey(str, Enum):
    SHORTS = "shorts"      # 1080×1920
    LANDSCAPE = "landscape"  # 1920×1080
    SQUARE = "square"      # 1080×1080


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # Paused = user-initiated pause; the job will resume from staged scenes
    # when the queue picks it up again.
    PAUSED = "paused"


class ScriptFormat(str, Enum):
    """Result of script-format auto-detection."""
    TAGGED = "tagged"          # [SCENE]/[NARRATION]/[VISUAL] blocks
    WHITEBOARD = "whiteboard"  # Point N: / VOICEOVER: / DRAWING:
    FREEFORM = "freeform"      # Plain prose, needs Claude normalization


# ─── voice profiles ───────────────────────────────────────────────────────


class VoiceProfile(BaseModel):
    """A saved (API key, voice_id) pair for the local TTS server.
    Multiple profiles can be saved; users pick one per job."""
    id: str                          # internal short id (uuid4 hex prefix)
    name: str                        # user-supplied display name
    server_url: str                  # e.g. http://127.0.0.1:8000
    api_key: str                     # the vct_… key
    voice_id: str                    # 12-char hex from the TTS server
    description: str = ""            # optional user note
    created_at: datetime = Field(default_factory=datetime.now)


# ─── styles ───────────────────────────────────────────────────────────────


class Style(BaseModel):
    """A visual style for HTML generation. Built-in styles ship with the app;
    users can add their own through the Styles page."""
    key: str                         # snake_case identifier
    label: str                       # human-readable name
    builtin: bool = False            # True for shipped styles, False for user-created
    description: str = ""            # tooltip / catalog text
    # Guidance fed to Claude when normalizing freeform scripts into scenes:
    script_guidance: str
    # Guidance appended to the HTML generator's system prompt:
    html_guidance: str
    # Soft hint for scene count when normalizing freeform input.
    scene_range_min: int = 3
    scene_range_max: int = 7
    created_at: datetime = Field(default_factory=datetime.now)


# ─── jobs ─────────────────────────────────────────────────────────────────


class JobRequest(BaseModel):
    """What the frontend POSTs to enqueue a new job."""
    title: str = Field(..., min_length=1, max_length=200,
                       description="Used as the output mp4 filename.")
    script: str = Field(..., min_length=1,
                        description="Raw script text. Any format — auto-detected.")
    output_folder: str = Field(..., description="Absolute path where the mp4 should land.")
    style_key: str = Field(default="motion_graphic")
    canvas_key: CanvasKey = CanvasKey.SHORTS
    voice_profile_id: str = Field(..., description="Which saved voice profile to use.")
    # Pacing controls (same as v1):
    narration_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    transition_seconds: float = Field(default=0.5, ge=0.0, le=1.5)
    transition_name: str = "fade"
    # Anthropic config — could be sourced from env, but allow per-job override.
    anthropic_model: str = "claude-opus-4-7"


class JobProgress(BaseModel):
    """Per-job live progress snapshot — drives the queue UI."""
    current_scene: int = 0
    total_scenes: int = 0
    current_step: str = ""           # human-readable, e.g. "Scene 3: rendering"
    elapsed_seconds: float = 0.0
    eta_seconds: float | None = None


class Job(BaseModel):
    """A queued or running job. Persisted to disk so the queue survives
    crashes and restarts."""
    id: str                          # uuid4 hex prefix
    request: JobRequest
    status: JobStatus = JobStatus.QUEUED
    progress: JobProgress = Field(default_factory=JobProgress)
    detected_format: ScriptFormat | None = None
    result_path: str | None = None   # absolute path to the final mp4 when COMPLETED
    error_message: str | None = None
    error_traceback: str | None = None
    # Log lines accumulated during the run; bounded length (most recent N kept).
    log_lines: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None


# ─── app-wide settings ────────────────────────────────────────────────────


class AppConfig(BaseModel):
    """Top-level user-editable config — persisted as config/app_config.json."""
    # API keys (Anthropic only — TTS keys live on the VoiceProfile)
    anthropic_api_key: str = ""
    # Last-used defaults the UI prepopulates with.
    default_output_folder: str = ""
    default_style_key: str = "motion_graphic"
    default_canvas_key: CanvasKey = CanvasKey.SHORTS
    default_voice_profile_id: str | None = None
    # Auto-update behaviour.
    hyperframes_auto_check: bool = True       # check `npm outdated` on startup
    hyperframes_auto_install: bool = False    # ask first vs install silently
    # UI theme.
    theme: Literal["dark", "light", "auto"] = "dark"

    # Lists kept inside the same file for simplicity. (Voice profiles and
    # custom styles are large enough that we may split them out later.)
    voice_profiles: list[VoiceProfile] = Field(default_factory=list)
    custom_styles: list[Style] = Field(default_factory=list)


# ─── HyperFrames status ───────────────────────────────────────────────────


class HyperFramesStatus(BaseModel):
    """Surfaced by GET /api/hyperframes/status. Drives the update banner."""
    installed_version: str | None = None       # None = not installed
    latest_version: str | None = None
    is_outdated: bool = False
    last_check: datetime | None = None
    last_smoke_test_passed: bool | None = None
    last_smoke_test_error: str | None = None


# ─── TTS status ───────────────────────────────────────────────────────────


class TTSHealth(BaseModel):
    """Reply from the user's TTS server's /api/health."""
    status: str                     # "ok" or "loading"
    device: str | None = None       # "cuda" / "cpu"
    voices: int | None = None
    auth_required: bool | None = None
    reachable: bool = True          # False = couldn't connect at all
    error: str | None = None
