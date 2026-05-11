"""Persisted application config — voice profiles, custom styles, default
preferences. One JSON file under the user's home dir so it survives app
upgrades and isn't accidentally committed to git.

Why the home dir and not `backend/config/`? Two reasons:
  1. The user's API keys live in here. If they share the project folder
     with someone (or push to a repo), keys stay private.
  2. The config persists across v1 → v2 rebuilds. Both versions can be
     installed without conflict.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock

from pydantic import ValidationError

from .models import AppConfig


# Configurable via env var so dev can point at a sandbox config without
# overwriting the real one.
CONFIG_DIR = Path(
    os.environ.get("VIDEO_GEN_V2_CONFIG_DIR")
    or Path.home() / ".video-gen-v2"
)
CONFIG_PATH = CONFIG_DIR / "config.json"

_lock = Lock()


def load() -> AppConfig:
    """Read the config file. Returns a default-populated AppConfig if the
    file is missing or unparseable — never raises, since a fresh user has
    no config and the UI needs to render anyway."""
    if not CONFIG_PATH.exists():
        return AppConfig()
    try:
        raw = CONFIG_PATH.read_text(encoding="utf-8")
        return AppConfig.model_validate_json(raw)
    except (ValidationError, ValueError, OSError):
        # Corrupt or schema-drifted file — fall back to defaults.
        # The user can re-enter values; we don't auto-delete the broken
        # file so they can recover manually if they want to.
        return AppConfig()


def save(cfg: AppConfig) -> None:
    """Atomic write — tmp file + rename — so a kill mid-write can't
    corrupt the config."""
    with _lock:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_suffix(".json.tmp")
        tmp.write_text(
            cfg.model_dump_json(indent=2),
            encoding="utf-8",
        )
        tmp.replace(CONFIG_PATH)


def update(mutate) -> AppConfig:
    """Read, apply a mutation callable, write back. Use this for any
    partial-update path so we don't race on simultaneous edits."""
    with _lock:
        cfg = load()
        mutate(cfg)
        # save() also acquires _lock — release ours first to avoid re-entry.
    save(cfg)
    return cfg
