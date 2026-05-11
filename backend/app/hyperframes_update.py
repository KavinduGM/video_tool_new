"""HyperFrames version management.

Three operations:

  1. status()  — what's installed locally? what's the latest on npm?
  2. install() — `npm install -g hyperframes@latest`
  3. smoke_test() — render a 1-second fixture composition to prove the
     CURRENT HTML scaffold still works after an update. If it fails, the
     UI shows the error and links to HyperFrames' changelog so the user
     knows to update our prompt accordingly.

The smoke test is what protects us from silent contract drift — if their
runtime changes again like with `window.__hf`, the smoke render will fail
fast on a known-good fixture instead of burning credits on a real job.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from . import hyperframes
from .models import CanvasKey, HyperFramesStatus


# ─── status ────────────────────────────────────────────────────────────────


def status() -> HyperFramesStatus:
    """Combine installed-version + npm-latest + last smoke-test result."""
    installed = hyperframes.installed_version()
    latest = _npm_latest_version("hyperframes")
    return HyperFramesStatus(
        installed_version=installed,
        latest_version=latest,
        is_outdated=bool(installed and latest and installed != latest),
        last_check=datetime.now(),
    )


def _npm_latest_version(pkg: str) -> str | None:
    """`npm view <pkg> version` → latest published version."""
    npm = shutil.which("npm") or "npm"
    try:
        out = subprocess.run(
            [npm, "view", pkg, "version"],
            capture_output=True, text=True, timeout=30,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


# ─── install ──────────────────────────────────────────────────────────────


class InstallError(RuntimeError):
    """`npm install -g` failed."""


def install_latest() -> str:
    """Install the latest hyperframes globally. Returns the new version
    string. Raises InstallError on failure with stderr included.

    On Windows the user might need to run their PowerShell as admin if
    npm's global prefix lives under Program Files. The error message will
    surface that if it happens."""
    npm = shutil.which("npm") or "npm"
    out = subprocess.run(
        [npm, "install", "-g", "hyperframes@latest"],
        capture_output=True, text=True, timeout=300,
    )
    if out.returncode != 0:
        raise InstallError(
            f"npm install failed (code {out.returncode}):\n"
            f"--- STDOUT ---\n{out.stdout}\n"
            f"--- STDERR ---\n{out.stderr}"
        )
    new_version = hyperframes.installed_version()
    if not new_version:
        raise InstallError(
            "npm reported success but `hyperframes --version` still fails."
        )
    return new_version


# ─── smoke test ───────────────────────────────────────────────────────────


SMOKE_BODY = """
<div id="title"
     style="position:absolute; left:50%; top:50%;
            transform:translate(-50%, -50%);
            font-size:64px; color:#fff; font-family:sans-serif;
            white-space:nowrap;">
  smoke test
</div>
"""

SMOKE_TIMELINE = """
tl.from("#title", { autoAlpha: 0, duration: 0.4, ease: "power3.out" }, 0.1);
"""


def smoke_test() -> tuple[bool, str | None]:
    """Render a 1-second composition with the current scaffold. Returns
    (passed, error_message_or_none). Never raises — the caller wants a
    pass/fail not an exception."""
    canvas = hyperframes.canvas_for(CanvasKey.LANDSCAPE)
    html = hyperframes.build_single_scene_composition(
        scene_body_html=SMOKE_BODY,
        timeline_animations_js=SMOKE_TIMELINE,
        duration_seconds=1.0,
        canvas=canvas,
        background_css="#111827",
    )
    with tempfile.TemporaryDirectory(prefix="hf-smoke-") as tmp_dir:
        project = Path(tmp_dir) / "smoke"
        try:
            hyperframes.init_project(project)
            hyperframes.write_composition(project, html)
            out_mp4 = Path(tmp_dir) / "out.mp4"
            hyperframes.render(project, out_mp4)
            if not out_mp4.exists() or out_mp4.stat().st_size < 1024:
                return False, "Render produced no output file."
            return True, None
        except Exception as e:
            return False, str(e)
