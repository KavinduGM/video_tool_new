"""HyperFrames adapter: HTML scaffolding + project init + render.

This file is the single source of truth for the HTML that gets fed to the
HyperFrames renderer. The contract is taken directly from HeyGen's official
`docs/guides/claude-design-hyperframes.md` and `packages/engine` reference.

Three rules we DO NOT bend:

1. The composition is a complete HTML document (`<!doctype html>` + html +
   head + body). Bare fragments are rejected by the renderer.

2. Three CDN scripts load in this exact order inside <head>:
     a. gsap@3.14.2
     b. @hyperframes/core/dist/hyperframe.runtime.iife.js
     c. @hyperframes/shader-transitions/dist/index.global.js   (optional)
   The middle one is what auto-creates `window.__hf = { duration, seek }`
   from the data-attributes on the root + clips. We DO NOT write
   window.__hf manually. (That's what burned v1 when the contract changed.)

3. Scene anatomy:
     <div class="scene clip" id="sN"
          data-start data-duration data-track-index="0"
          style="visibility:hidden;">
       <div class="scene-content">
         <!-- visible elements here, each absolutely positioned -->
       </div>
     </div>
   And the timeline must include:
     tl.set("#sN", { autoAlpha: 1 }, sceneStart);
     tl.set("#sN", { autoAlpha: 0 }, sceneStart + sceneDuration);
"""
from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import CanvasKey

IS_WINDOWS = platform.system() == "Windows"


# ─── pinned dependency versions (kept in lockstep with what we test) ──────
# When HyperFrames the package updates, we also update these pins after
# running the smoke test successfully.

GSAP_VERSION = "3.14.2"
HYPERFRAMES_RUNTIME_CDN = (
    "https://cdn.jsdelivr.net/npm/@hyperframes/core/dist/"
    "hyperframe.runtime.iife.js"
)
HYPERFRAMES_SHADER_CDN = (
    "https://cdn.jsdelivr.net/npm/@hyperframes/shader-transitions/dist/"
    "index.global.js"
)
GSAP_CDN = f"https://cdn.jsdelivr.net/npm/gsap@{GSAP_VERSION}/dist/gsap.min.js"


# ─── canvas dimensions ────────────────────────────────────────────────────


@dataclass(frozen=True)
class CanvasSize:
    width: int
    height: int
    label: str


CANVAS_DIMENSIONS: dict[CanvasKey, CanvasSize] = {
    CanvasKey.SHORTS:    CanvasSize(1080, 1920, "9:16 Shorts/Reels"),
    CanvasKey.LANDSCAPE: CanvasSize(1920, 1080, "16:9 Landscape"),
    CanvasKey.SQUARE:    CanvasSize(1080, 1080, "1:1 Square"),
}


def canvas_for(key: CanvasKey) -> CanvasSize:
    return CANVAS_DIMENSIONS[key]


# ─── HTML scaffold ────────────────────────────────────────────────────────


def build_single_scene_composition(
    *,
    scene_body_html: str,
    timeline_animations_js: str,
    duration_seconds: float,
    canvas: CanvasSize,
    background_css: str = "#000",
) -> str:
    """Wrap a single scene's body + GSAP animation code in a full HyperFrames
    composition. Returns a complete HTML document ready for `npx hyperframes
    render`.

    `scene_body_html`   — markup that goes INSIDE the `<div class="scene-content">`.
                          Should be absolutely-positioned elements only.
    `timeline_animations_js`
                        — JS statements adding tweens to `tl` (the GSAP
                          timeline). Do NOT redeclare `tl` here. Do NOT
                          set window.__timelines or window.__hf here —
                          we handle both.
    `duration_seconds`  — total scene duration. Both root composition and
                          the single scene clip use this.
    `canvas`            — width/height + label.
    `background_css`    — applied to <body> AND root <div> so letterbox
                          colour matches scene content.

    Output is intentionally one long string with embedded newlines — easier
    to debug if you `cat` the rendered index.html and read it top-to-bottom.
    """
    w = canvas.width
    h = canvas.height
    # Numeric duration must be JS-safe — round to 3dp, no scientific notation.
    dur = f"{duration_seconds:.3f}"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width={w}, height={h}" />
  <title>scene</title>
  <!-- HyperFrames requires these three scripts, in this order. -->
  <script src="{GSAP_CDN}"></script>
  <script src="{HYPERFRAMES_RUNTIME_CDN}"></script>
  <script src="{HYPERFRAMES_SHADER_CDN}"></script>
  <style>
    /* Reset + canvas background. */
    html, body {{
      margin: 0;
      padding: 0;
      background: {background_css};
      width: {w}px;
      height: {h}px;
      overflow: hidden;
      font-family: -apple-system, 'SF Pro Display', 'Inter',
                   'Helvetica Neue', sans-serif;
    }}
    /* Each scene clip is full-canvas absolute. */
    .scene {{
      position: absolute;
      inset: 0;
      width: {w}px;
      height: {h}px;
      overflow: hidden;
    }}
    .scene-content {{
      position: relative;
      width: 100%;
      height: 100%;
    }}
  </style>
</head>
<body>
  <div id="main"
       data-composition-id="main"
       data-width="{w}"
       data-height="{h}"
       data-start="0"
       data-duration="{dur}"
       style="position: relative; width: {w}px; height: {h}px;
              background: {background_css}; overflow: hidden;">

    <div class="scene clip"
         id="s1"
         data-start="0"
         data-duration="{dur}"
         data-track-index="0"
         style="visibility: hidden;">
      <div class="scene-content">
{scene_body_html}
      </div>
    </div>

  </div>

  <script>
    // ──────────────────────────────────────────────────────────────────
    // Timeline registration. The HyperFrames runtime script loaded above
    // discovers this and wires window.__hf automatically. Do not assign
    // window.__hf manually — that's the runtime's job.
    // ──────────────────────────────────────────────────────────────────
    window.__timelines = window.__timelines || {{}};
    var tl = gsap.timeline({{ paused: true }});

    // Make scene 1 visible for its full window. autoAlpha (not visibility)
    // because HyperShader manipulates opacity during transitions.
    tl.set("#s1", {{ autoAlpha: 1 }}, 0);

    // ── Scene animations (generated by Claude per visual instructions) ──
{timeline_animations_js}

    window.__timelines["main"] = tl;
  </script>
</body>
</html>
"""


# ─── npx hyperframes wrappers ─────────────────────────────────────────────


class HyperFramesError(RuntimeError):
    """Raised when an npx hyperframes subprocess returns non-zero."""


def _hyperframes_command() -> list[str]:
    """Resolve `hyperframes` on Windows where bare `hyperframes` from
    PATH may be hyperframes.cmd; shutil.which handles both."""
    direct = shutil.which("hyperframes")
    if direct:
        return [direct]
    # Fall back to npx (the runner's _resolve_executable handles npx.cmd).
    return ["npx", "--yes", "hyperframes"]


def init_project(project_dir: Path) -> None:
    """Scaffold a fresh HyperFrames project at `project_dir`. The directory
    must not already exist; we delete then recreate to guarantee a clean
    state if a previous attempt left junk."""
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        *_hyperframes_command(),
        "init", project_dir.name,
        "--non-interactive", "--example", "blank",
    ]
    _run(cmd, cwd=project_dir.parent)


def write_composition(project_dir: Path, html: str) -> None:
    """Drop the generated HTML into the project's index.html."""
    (project_dir / "index.html").write_text(html, encoding="utf-8")


def render(project_dir: Path, output_mp4: Path) -> None:
    """Render the project to MP4. Output_mp4's parent dir is created."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        *_hyperframes_command(),
        "render",
        "--output", str(output_mp4),
    ]
    _run(cmd, cwd=project_dir)


def installed_version() -> str | None:
    """`npx hyperframes --version` → '0.5.7' or None if not installed."""
    try:
        out = subprocess.run(
            [*_hyperframes_command(), "--version"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return None
        # The CLI prints just the version on stdout.
        m = re.search(r"\d+\.\d+\.\d+", out.stdout)
        return m.group(0) if m else None
    except Exception:
        return None


# ─── subprocess plumbing ──────────────────────────────────────────────────


def _run(cmd: list[str], cwd: Path) -> None:
    """Run a subprocess, capture stdout/stderr, and raise HyperFramesError
    on non-zero exit. Output is bundled into the exception so the worker
    thread can stuff it into the job's log."""
    # On Windows we need shell-friendly handling of .cmd shims; subprocess
    # will resolve via PATH which is fine after `shutil.which` upstream.
    proc = subprocess.run(
        cmd, cwd=cwd,
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise HyperFramesError(
            f"Command failed: {' '.join(cmd)}\n"
            f"CWD: {cwd}\n"
            f"--- STDOUT ---\n{proc.stdout}\n"
            f"--- STDERR ---\n{proc.stderr}"
        )
