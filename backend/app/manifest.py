"""Per-job staging + manifest. Carries v1's crash-safe model into v2.

Each running job has a staging folder `<title>_partial/` next to where the
final mp4 will land. Inside:
  scenes/scene_001.mp4 … scene_NNN.mp4      (rendered + merged scenes)
  run_manifest.json                          (which scenes are done, hash, …)

Resume rules:
  * Same script (same SHA-256 hash) + same total scene count   → resume.
  * Different script in the staging folder                     → start fresh,
    discarding the old staging.
  * Same script, different style/canvas                        → start fresh
    (rendered HTML wouldn't match).

The hash includes only the script TEXT, not config. We re-check style/canvas
explicitly so users can't accidentally splice scenes from two different runs.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

MANIFEST_NAME = "run_manifest.json"
MANIFEST_VERSION = 2


def script_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def scene_path(staging: Path, scene_index: int) -> Path:
    return staging / "scenes" / f"scene_{scene_index:03d}.mp4"


def manifest_path(staging: Path) -> Path:
    return staging / MANIFEST_NAME


def load(staging: Path) -> dict[str, Any] | None:
    p = manifest_path(staging)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save(staging: Path, data: dict[str, Any]) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    data["updated"] = datetime.now().isoformat(timespec="seconds")
    p = manifest_path(staging)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(p)


def init(
    *,
    script_hash_value: str,
    total_scenes: int,
    title: str,
    style_key: str,
    canvas_key: str,
) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "version": MANIFEST_VERSION,
        "script_hash": script_hash_value,
        "total_scenes": total_scenes,
        "title": title,
        "style_key": style_key,
        "canvas_key": canvas_key,
        "completed": {},     # scene_index (str) → relative scene file path
        "created": now,
        "updated": now,
    }


def completed_indices(manifest: dict[str, Any]) -> set[int]:
    return {int(k) for k in manifest.get("completed", {}).keys()}


def mark_complete(
    manifest: dict[str, Any], scene_index: int, relative_filename: str,
) -> None:
    manifest.setdefault("completed", {})[str(scene_index)] = relative_filename


def staged_scene_files(staging: Path, manifest: dict[str, Any]) -> list[Path]:
    """Absolute paths to completed scene MP4s, ordered by scene index."""
    out: list[Path] = []
    for k in sorted(manifest.get("completed", {}).keys(), key=lambda s: int(s)):
        p = staging / manifest["completed"][k]
        if p.exists():
            out.append(p)
    return out


def is_resumable(
    staging: Path,
    *,
    expected_hash: str,
    expected_total: int,
    expected_style: str,
    expected_canvas: str,
) -> tuple[bool, dict[str, Any] | None]:
    """A staging folder is resumable only if every key parameter matches.
    Style/canvas mismatch means the HTML rendered earlier won't match what
    Claude would produce now — better to start over than splice."""
    m = load(staging)
    if not m:
        return False, None
    if m.get("script_hash") != expected_hash:
        return False, m
    if m.get("total_scenes") != expected_total:
        return False, m
    if m.get("style_key") != expected_style:
        return False, m
    if m.get("canvas_key") != expected_canvas:
        return False, m
    return True, m


def cleanup(staging: Path) -> None:
    """Best-effort removal. Never raises — cleanup failure must not fail a run."""
    try:
        if staging.exists():
            shutil.rmtree(staging)
    except Exception:
        pass
