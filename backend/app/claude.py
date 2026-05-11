"""Anthropic SDK calls. Two distinct uses:

  1. normalize_script() — freeform text → tagged [SCENE]/[NARRATION]/[VISUAL]
  2. generate_scene_html() — one parsed scene → (body_html, timeline_js)
                              that slots into hyperframes.build_single_scene_composition()

Both calls produce strictly-structured text. We post-process: strip code
fences, validate parse-ability, raise clear errors when the output drifted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from anthropic import Anthropic

from . import script_parser
from .models import ScriptFormat, Style
from .hyperframes import CanvasSize


def _create_message_with_fallback(client: Anthropic, kwargs: dict):
    """Call client.messages.create(**kwargs), but if the SDK doesn't
    recognise the `thinking` keyword (older versions pre-extended-thinking),
    drop it and retry. Lets the same code run against a range of SDK
    versions instead of blowing up with TypeError at request time.

    Any error that isn't an SDK-version mismatch is re-raised unchanged.
    """
    try:
        return client.messages.create(**kwargs)
    except TypeError as e:
        msg = str(e)
        if "thinking" in msg and "thinking" in kwargs:
            kwargs.pop("thinking", None)
            return client.messages.create(**kwargs)
        raise


# ─── normalization ────────────────────────────────────────────────────────


NORMALIZER_SYSTEM_PROMPT = """You convert freeform video scripts into a strictly-formatted scene block format for a HyperFrames-based AI video generator.

OUTPUT FORMAT — produce ONLY this, nothing else:

[SCENE 1]
[NARRATION]
<one short paragraph of natural spoken English — 1 to 3 sentences, what the narrator says aloud>
[/NARRATION]
[VISUAL]
Step 1: <concrete visual beat>
Step 2: <next visual beat>
Step 3: <next visual beat>
[/VISUAL]
[/SCENE]

[SCENE 2]
... and so on.

CORE RULES:

1. NARRATION is what the narrator SAYS aloud. Natural, spoken English. No stage directions, no "(pause)", no emojis. Punchy and clear. Length: 1-3 sentences typically, max ~30 words.

2. VISUAL is what the viewer SEES on screen. Concrete, animatable beats. Each "Step N:" is one visible event (an element appearing, a transition, a transformation). Be specific about colors (hex when possible), positions ("center", "top", "left half"), sizes ("large title", "small caption"), and motion ("fades in", "slides from left", "scales up"). 3-6 steps per scene.

3. PRESERVE the user's meaning. Do not invent new facts or examples that aren't in the source. If the source is sparse, you may elaborate visually but keep narration faithful.

4. SCENE COUNT: the SUGGESTED range below is a hint, not a cap. For a short source stay near the low end. For a long source feel free to exceed the high end — break naturally on idea boundaries. Never cram unrelated ideas into one scene.

5. SCENE LENGTH: aim for narration that reads aloud in 4-12 seconds. If a paragraph would take 25 seconds, split it.

6. Output the raw scene blocks ONLY. No preamble, commentary, markdown fences, or closing remarks. Start with "[SCENE 1]" and end with "[/SCENE]"."""


def normalize_script(
    *,
    raw_text: str,
    style: Style,
    anthropic_api_key: str,
    model: str,
) -> str:
    """Turn freeform prose into tagged scene blocks. Idempotent on already-
    tagged input (we don't call the API in that case)."""
    if script_parser.detect_format(raw_text) == ScriptFormat.TAGGED:
        return raw_text.strip()

    user_msg = (
        f"VIDEO STYLE: {style.label}\n"
        f"STYLE GUIDANCE: {style.script_guidance}\n"
        f"SUGGESTED SCENE COUNT: {style.scene_range_min} to {style.scene_range_max} "
        f"scenes (more is fine for long source material).\n\n"
        f"SOURCE SCRIPT (freeform — convert this to the tagged format):\n\n"
        f"{raw_text.strip()}"
    )

    # Output budget scales with input length so long articles don't get clipped.
    source_chars = len(raw_text)
    max_output = max(8000, min(32000, 4000 + source_chars * 4))

    kwargs: dict = {
        "model": model,
        "max_tokens": max_output,
        "system": NORMALIZER_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_msg}],
    }
    if model.startswith("claude-opus-4-7"):
        kwargs["thinking"] = {"type": "adaptive"}
    elif model.startswith("claude-sonnet-4") or model.startswith("claude-opus-4"):
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": 3000}

    client = Anthropic(api_key=anthropic_api_key)
    resp = _create_message_with_fallback(client, kwargs)
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    text = _strip_code_fences(text)

    # Validate it actually parses; if not, surface a useful error.
    try:
        script_parser.parse_tagged(text)
    except script_parser.ScriptParseError as e:
        raise script_parser.ScriptParseError(
            f"Normalizer output didn't parse cleanly: {e}\n\n"
            f"First 500 chars:\n{text[:500]}..."
        )
    return text


# ─── per-scene HTML generation ────────────────────────────────────────────


@dataclass(frozen=True)
class SceneHtml:
    """The two slots that go into hyperframes.build_single_scene_composition."""
    body_html: str           # innerHTML for the .scene-content div
    timeline_js: str         # JS statements added to the GSAP timeline `tl`


def _html_system_prompt(*, canvas: CanvasSize, style: Style, total_scenes: int) -> str:
    w = canvas.width
    h = canvas.height
    # Safe margins — 6% inset on each side.
    sl = round(w * 0.06)
    sr = w - sl
    st = round(h * 0.06)
    sb = h - st
    safe_w = sr - sl
    safe_h = sb - st

    return f"""You generate HyperFrames-compatible HTML + JS for ONE scene of a {total_scenes}-scene video.

You are filling in TWO slots that get embedded into a strict scaffold our build system controls. DO NOT output a full HTML document. DO NOT output <html>, <head>, <body>, <script src=…> tags. The scaffold loads GSAP and the HyperFrames runtime for you.

═══════════════════════════════════════════════════════════════════
CANVAS: {w} x {h} pixels.
SAFE ZONE (keep everything inside): x in [{sl}, {sr}], y in [{st}, {sb}].
SAFE WIDTH = {safe_w}px, SAFE HEIGHT = {safe_h}px.
═══════════════════════════════════════════════════════════════════
OUTPUT FORMAT — two separated blocks, in this exact order:

===BODY===
<!-- absolutely-positioned visible elements that go INSIDE .scene-content -->
<div style="position:absolute; left:60px; top:120px; ...">...</div>
<svg style="position:absolute; ...">...</svg>

===TIMELINE===
// JS statements added to a pre-existing `tl` (GSAP timeline, paused).
// Do NOT redeclare tl. Do NOT touch window.__timelines or window.__hf.
tl.from("#title", {{ y: 40, autoAlpha: 0, duration: 0.6, ease: "power3.out" }}, 0.3);
tl.from("#subtitle", {{ y: 30, autoAlpha: 0, duration: 0.5, ease: "power3.out" }}, 0.7);

═══════════════════════════════════════════════════════════════════
HARD RULES:

1. Every visible element must satisfy:
     - left edge >= {sl}px
     - right edge <= {sr}px
     - top edge >= {st}px
     - bottom edge <= {sb}px
   Compute the rendered bounding box for each element BEFORE emitting it.
   If a text element would exceed the safe width at the chosen font-size,
   SHRINK the font-size — never auto-wrap unless the script explicitly
   says "on multiple lines".

2. Every visible element must have:
     - position: absolute
     - explicit `left:` and `top:` (or `right:` / `bottom:`) in px
     - a unique `id="..."` so the timeline can target it
   Pick stable ids like #title, #subtitle, #icon1, #label-left, etc.

3. Every text element gets `white-space: nowrap` by default. If the script
   says the text should wrap, use `width: <Npx>; white-space: normal;
   word-break: break-word;` explicitly.

4. SVG for shapes/icons/arrows — inline. Use viewBox correctly.

5. Animations: build the timeline using `tl.from()`, `tl.to()`,
   `tl.fromTo()`, `tl.set()`. The third positional arg is ABSOLUTE time in
   seconds from scene start. Use eases:
     'power3.out'    — most entrances
     'back.out(1.7)' — punchy entrances
     'power1.inOut'  — wipes, clip-path reveals
     'sine.inOut'    — gentle continuous motion

6. The scene starts at t=0 and ends at TOTAL_DURATION. The first reveal
   should land at t ≈ 0.3s (a beat after scene fade-in). The final reveal
   should complete by t = TOTAL_DURATION - 0.4s. Elements then HOLD until
   the end (no exit animations — the system handles transitions).

7. NEVER assign to window.* in the timeline block. The scaffold does that.

═══════════════════════════════════════════════════════════════════
STYLE GUIDANCE FOR THIS SCENE:

{style.html_guidance}

═══════════════════════════════════════════════════════════════════
You will be told the scene's narration text (for tone reference), the visual
instructions (what to show, step by step), and TOTAL_DURATION in seconds.
Produce the ===BODY=== and ===TIMELINE=== blocks. Nothing else."""


def generate_scene_html(
    *,
    anthropic_api_key: str,
    model: str,
    canvas: CanvasSize,
    style: Style,
    scene_index: int,
    total_scenes: int,
    narration: str,
    visual_instructions: str,
    duration_seconds: float,
) -> SceneHtml:
    """One scene → body HTML + timeline JS. Caller wraps them in the
    HyperFrames scaffold via hyperframes.build_single_scene_composition()."""
    user_msg = (
        f"SCENE {scene_index} of {total_scenes}\n"
        f"TOTAL_DURATION: {duration_seconds:.3f} seconds\n\n"
        f"NARRATION (for tone reference — not displayed):\n"
        f"\"{narration}\"\n\n"
        f"VISUAL INSTRUCTIONS (literal — implement every step):\n"
        f"{visual_instructions}\n\n"
        f"Produce ===BODY=== and ===TIMELINE=== blocks now."
    )

    kwargs: dict = {
        "model": model,
        "max_tokens": 16000,
        "system": _html_system_prompt(
            canvas=canvas, style=style, total_scenes=total_scenes,
        ),
        "messages": [{"role": "user", "content": user_msg}],
    }
    if model.startswith("claude-opus-4-7"):
        kwargs["thinking"] = {"type": "adaptive"}
    elif model.startswith("claude-sonnet-4") or model.startswith("claude-opus-4"):
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": 4000}

    client = Anthropic(api_key=anthropic_api_key)
    resp = _create_message_with_fallback(client, kwargs)
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return _split_body_and_timeline(text)


# ─── post-processing ──────────────────────────────────────────────────────


_BODY_HEADER = re.compile(r"^===\s*BODY\s*===\s*$", re.MULTILINE | re.IGNORECASE)
_TIMELINE_HEADER = re.compile(r"^===\s*TIMELINE\s*===\s*$", re.MULTILINE | re.IGNORECASE)


def _split_body_and_timeline(text: str) -> SceneHtml:
    """Parse Claude's reply into the two slots. Tolerant of leading prose
    or trailing commentary that occasionally slips through."""
    text = _strip_code_fences(text)
    body_match = _BODY_HEADER.search(text)
    tl_match = _TIMELINE_HEADER.search(text)
    if not body_match or not tl_match or tl_match.start() < body_match.end():
        raise ValueError(
            "Claude output didn't include the expected ===BODY=== / ===TIMELINE=== "
            f"separators. First 300 chars: {text[:300]!r}"
        )
    body_html = text[body_match.end():tl_match.start()].strip()
    timeline_js = text[tl_match.end():].strip()

    # Some replies wrap each section in its own fence — strip again.
    body_html = _strip_code_fences(body_html)
    timeline_js = _strip_code_fences(timeline_js)

    # Reject obvious contract violations early.
    forbidden = ("window.__timelines", "window.__hf", "gsap.timeline(")
    for marker in forbidden:
        if marker in timeline_js:
            raise ValueError(
                f"Claude's timeline includes forbidden marker `{marker}` — "
                f"the scaffold owns that. First 200 chars: "
                f"{timeline_js[:200]!r}"
            )
    return SceneHtml(body_html=body_html, timeline_js=timeline_js)


def _strip_code_fences(text: str) -> str:
    """Remove a single wrapping ```lang … ``` block if present."""
    m = re.match(r"^```(?:[\w-]+)?\s*\n?(.*?)\s*```$", text.strip(), re.DOTALL)
    return m.group(1).strip() if m else text.strip()
