"""Script intake: detect format, parse into a list of Scenes.

Three formats supported:

  TAGGED        [SCENE 1]
                [NARRATION]<...>[/NARRATION]
                [VISUAL]<...>[/VISUAL]
                [/SCENE]

  WHITEBOARD    Point 1: <title>
                VOICEOVER:
                "<...>"
                DRAWING/WRITING:
                Step 1: <...>
                Step 2: <...>

  FREEFORM      Plain prose. Auto-normalized to TAGGED via Claude before render.

The detector tries TAGGED → WHITEBOARD → FREEFORM. If a script *looks* tagged
but doesn't parse cleanly, we fall through to FREEFORM (Claude will rewrite).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ScriptFormat


# ─── parsed-scene representation ──────────────────────────────────────────


@dataclass(frozen=True)
class Scene:
    index: int          # 1-based, matches what the script labels
    narration: str
    visual: str         # multi-line visual instructions block


class ScriptParseError(ValueError):
    """Surfaceable parse failure with a user-readable message."""


# ─── format detection ─────────────────────────────────────────────────────


_HAS_SCENE_TAG = re.compile(r"\[SCENE\s+\d+", re.IGNORECASE)
_HAS_NARR_TAG = re.compile(r"\[NARRATION\]", re.IGNORECASE)
_HAS_VIS_TAG = re.compile(r"\[VISUAL\]", re.IGNORECASE)

_HAS_POINT_HEADER = re.compile(r"^\s*Point\s+\d+\s*[:.]", re.IGNORECASE | re.MULTILINE)
_HAS_VOICEOVER = re.compile(r"^\s*VOICEOVER\s*:", re.IGNORECASE | re.MULTILINE)
_HAS_DRAWING = re.compile(r"^\s*DRAWING\s*[/]?\s*WRITING\s*:", re.IGNORECASE | re.MULTILINE)


def detect_format(text: str) -> ScriptFormat:
    """Cheapest check first. A real parse attempt happens later; this is
    only for routing the request through the right pipeline."""
    if _HAS_SCENE_TAG.search(text) and _HAS_NARR_TAG.search(text) and _HAS_VIS_TAG.search(text):
        try:
            parse_tagged(text)
            return ScriptFormat.TAGGED
        except ScriptParseError:
            pass  # looks tagged but didn't parse — treat as freeform.
    if _HAS_POINT_HEADER.search(text) and _HAS_VOICEOVER.search(text) and _HAS_DRAWING.search(text):
        return ScriptFormat.WHITEBOARD
    return ScriptFormat.FREEFORM


# ─── tagged parser ────────────────────────────────────────────────────────


_SCENE_BLOCK = re.compile(
    r"\[SCENE\s+(\d+)\](.*?)\[/SCENE\]",
    re.IGNORECASE | re.DOTALL,
)
_NARR_BLOCK = re.compile(
    r"\[NARRATION\](.*?)\[/NARRATION\]",
    re.IGNORECASE | re.DOTALL,
)
_VIS_BLOCK = re.compile(
    r"\[VISUAL\](.*?)\[/VISUAL\]",
    re.IGNORECASE | re.DOTALL,
)


def parse_tagged(text: str) -> list[Scene]:
    """Parse the [SCENE]/[NARRATION]/[VISUAL] format. Raises on malformed
    input with a message that names the bad scene index when possible."""
    scenes: list[Scene] = []
    for match in _SCENE_BLOCK.finditer(text):
        index = int(match.group(1))
        body = match.group(2)
        n_match = _NARR_BLOCK.search(body)
        v_match = _VIS_BLOCK.search(body)
        if not n_match or not v_match:
            raise ScriptParseError(
                f"Scene {index} is missing [NARRATION] or [VISUAL] block."
            )
        narration = _clean(n_match.group(1))
        visual = _clean(v_match.group(1))
        if not narration:
            raise ScriptParseError(f"Scene {index} has empty narration.")
        if not visual:
            raise ScriptParseError(f"Scene {index} has empty visual instructions.")
        scenes.append(Scene(index=index, narration=narration, visual=visual))
    if not scenes:
        raise ScriptParseError("No [SCENE N] blocks found.")
    return scenes


# ─── whiteboard parser ────────────────────────────────────────────────────


_POINT_HEADER_LINE = re.compile(
    r"^\s*Point\s+(\d+)\s*[:.]?\s*(.*)$",
    re.IGNORECASE,
)


def parse_whiteboard(text: str) -> list[Scene]:
    """Mechanical conversion of `Point N: / VOICEOVER: / DRAWING:` blocks
    into Scenes. Narration is preserved VERBATIM — no LLM call needed,
    which is important for medical accuracy.

    The drawing instructions are normalized into 'Step N:' lines for the
    HTML generator's per-step animation grammar.
    """
    # Split into per-Point chunks. We keep the header inside each chunk.
    chunks = _split_on_point_headers(text)
    if not chunks:
        raise ScriptParseError("No 'Point N:' headers found.")

    scenes: list[Scene] = []
    for chunk in chunks:
        header_line = chunk.splitlines()[0]
        m = _POINT_HEADER_LINE.match(header_line)
        if not m:
            continue
        index = int(m.group(1))
        body = "\n".join(chunk.splitlines()[1:])

        narration = _extract_block(body, "VOICEOVER").strip().strip('"').strip()
        drawing = _extract_block(body, r"DRAWING\s*[/]?\s*WRITING")

        if not narration:
            raise ScriptParseError(f"Point {index}: no VOICEOVER content.")
        if not drawing.strip():
            raise ScriptParseError(f"Point {index}: no DRAWING/WRITING content.")

        # Normalize each instruction line to "Step N: ...".
        step_lines = [
            line.strip() for line in drawing.splitlines()
            if line.strip() and not line.strip().upper().startswith(
                ("END RECORDING", "TABLET SETUP", "DRAWING", "WRITING")
            )
        ]
        # Prepend the persistent "Point N" label as Step 1 — every whiteboard
        # scene has this top-left label visible the whole scene.
        normalized_visual: list[str] = []
        normalized_visual.append(
            f"Step 1: Persistent label \"Point {index}\" in White at top-left corner "
            f"for the entire scene."
        )
        for i, line in enumerate(step_lines, start=2):
            # Lines often start with "Step N:" already; strip that prefix
            # because we're renumbering them.
            stripped = re.sub(r"^Step\s*\d+\s*[:.]?\s*", "", line, flags=re.IGNORECASE)
            normalized_visual.append(f"Step {i}: {stripped}")

        scenes.append(
            Scene(
                index=index,
                narration=narration,
                visual="\n".join(normalized_visual),
            )
        )
    if not scenes:
        raise ScriptParseError("Whiteboard parse produced zero scenes.")
    return scenes


def _split_on_point_headers(text: str) -> list[str]:
    """Cut the text into chunks, each starting with a 'Point N' line.
    The header is kept inside its chunk."""
    lines = text.splitlines()
    chunks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _POINT_HEADER_LINE.match(line):
            if current:
                chunks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        chunks.append(current)
    return ["\n".join(c) for c in chunks]


def _extract_block(text: str, label_pattern: str) -> str:
    """Return everything between `<label>:` and the next ALL-CAPS label or
    end of text. Used for VOICEOVER and DRAWING/WRITING blocks."""
    pattern = re.compile(
        rf"{label_pattern}\s*:\s*(.*?)(?=^\s*[A-Z][A-Z /]+\s*:|\Z)",
        re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


# ─── shared helpers ───────────────────────────────────────────────────────


def _clean(s: str) -> str:
    """Trim and collapse internal blank-line clusters."""
    s = s.strip()
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s


# ─── top-level dispatcher ─────────────────────────────────────────────────


def parse(text: str, fmt: ScriptFormat) -> list[Scene]:
    """Dispatcher used after detect_format(). FREEFORM is handled by the
    normalizer, not here — callers should normalize first then re-parse
    as TAGGED."""
    if fmt == ScriptFormat.TAGGED:
        return parse_tagged(text)
    if fmt == ScriptFormat.WHITEBOARD:
        return parse_whiteboard(text)
    raise ScriptParseError(
        "Freeform scripts must be normalized via Claude before parsing."
    )
