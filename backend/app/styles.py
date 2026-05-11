"""Built-in styles + user-defined style management.

A "style" is two prompts:
  * script_guidance — fed to Claude during freeform → tagged normalization
  * html_guidance   — appended to Claude's HTML generator system prompt

Adding a new built-in is one entry below. Users can also create their own
through the Styles page; those live in AppConfig.custom_styles.
"""
from __future__ import annotations

from .config import load as load_config
from .models import Style


# ─── built-in styles ──────────────────────────────────────────────────────


_BUILTIN: list[Style] = [
    Style(
        key="motion_graphic",
        label="Motion graphic",
        builtin=True,
        description=(
            "Clean explainer with animated shapes, large typography, "
            "color-blocked panels. Great default for educational content."
        ),
        script_guidance=(
            "Clean motion-design explainer. Each scene introduces one idea, "
            "with a concrete visual beat. Narration is conversational and tight "
            "(1-3 sentences per scene). Visuals are geometric shapes, labels, "
            "arrows, and animated text — no images required."
        ),
        html_guidance=(
            "STYLE: motion graphic. Use simple geometric shapes (circles, "
            "rounded rectangles, arrows), large typography, color-blocked panels. "
            "Palette: 2-4 colors, high contrast. Tweens: ease 'power3.out' or "
            "'back.out(1.7)', duration 0.4-0.8s. Use stagger for grouped elements. "
            "Background: a flat or subtly-gradient panel — not white unless the "
            "script explicitly asks."
        ),
        scene_range_min=3,
        scene_range_max=8,
    ),
    Style(
        key="typography",
        label="Kinetic typography",
        builtin=True,
        description=(
            "Big bold animated text. Minimal shapes. Hooks, viral cuts, "
            "punchlines — anywhere the words ARE the visual."
        ),
        script_guidance=(
            "Kinetic typography. Each scene's visual is one short line or word "
            "that animates on with strong motion. Narration mirrors the on-screen "
            "text closely. Keep total scenes punchy — 4 to 8."
        ),
        html_guidance=(
            "STYLE: kinetic typography. The text IS the visual. Huge font sizes "
            "(120-280px depending on canvas). Animate text on with slam, wipe, "
            "stagger-by-character, or scale-punch. Backgrounds are solid color or "
            "subtle gradient. NEVER decorate with shapes unless the script asks. "
            "Use 'Inter', 'Anton', 'Bebas Neue' or another bold display font."
        ),
        scene_range_min=4,
        scene_range_max=10,
    ),
    Style(
        key="product_demo",
        label="Product demo",
        builtin=True,
        description=(
            "Screenshots, UI mockups, annotated callouts. For showing off "
            "an app, a feature, a workflow."
        ),
        script_guidance=(
            "Product demo / walkthrough. Scene 1 hooks with the problem or the "
            "feature name. Each subsequent scene shows ONE part of the product "
            "with callouts/labels. Final scene is the CTA. Narration is "
            "explanatory but confident, like a Loom walkthrough."
        ),
        html_guidance=(
            "STYLE: product demo. Center a mock screenshot or device frame in "
            "the canvas (60-75% of safe area). Use thin connector lines from "
            "callouts to the UI feature being annotated. Backgrounds: subtle "
            "gradient or branded color. Animate callouts in with a soft pop "
            "(scale 0.9 → 1.0, autoAlpha 0 → 1, 0.4s). When the script provides "
            "uploaded screenshots, use them via <img src=\"assets/<filename>\">. "
            "Add subtle drop-shadows on cards to lift them off the background."
        ),
        scene_range_min=4,
        scene_range_max=8,
    ),
    Style(
        key="personal_branding",
        label="Personal branding short",
        builtin=True,
        description=(
            "Punchy presenter-style shorts for LinkedIn/Instagram/YouTube. "
            "Clean modern type, accent color, minimal motion."
        ),
        script_guidance=(
            "Personal branding short. Hook → insight → payoff structure in 3-5 "
            "scenes. Narration is first-person, conversational. Visual is your "
            "name/handle persistent in a corner, one core idea per scene, and a "
            "clear CTA at the end."
        ),
        html_guidance=(
            "STYLE: personal branding. Modern, calm motion. ONE accent color "
            "(brand color) + black/white/neutral. Text-driven scenes with a "
            "small persistent watermark of the user's handle in a corner if "
            "the script provides one. Use type sizes 60-120px for emphasis "
            "lines. Subtle entrance: 'y: 20, autoAlpha: 0' → settled, "
            "0.5s ease 'power3.out'. No decorative shapes unless script asks."
        ),
        scene_range_min=3,
        scene_range_max=6,
    ),
    Style(
        key="whiteboard",
        label="Whiteboard / hand-drawn",
        builtin=True,
        description=(
            "Hand-drawn explainer on a black tablet canvas. For medical, "
            "educational, exam-prep content where the diagram builds step-by-step."
        ),
        script_guidance=(
            "Whiteboard hand-drawn explainer. Each scene has a tightly-scripted "
            "narration (preserve verbatim — do not rewrite) and a sequence of "
            "Write / Draw / Box / X-mark instructions. Each instruction becomes "
            "one Step that draws onto a black tablet canvas in sequence, timed "
            "across the narration."
        ),
        html_guidance=(
            "STYLE: WHITEBOARD / HAND-DRAWN ANIMATION.\n\n"
            "CANVAS COLOR: solid black background (#000000).\n\n"
            "STRICT PALETTE (map script color names exactly):\n"
            "  - 'Yellow' → #FFD400  (titles, critical terms)\n"
            "  - 'White'  → #F5F5F5  (supporting info)\n"
            "  - 'Blue'   → #4FC3F7  (X marks, boxes, icons, arrows)\n\n"
            "TYPOGRAPHY: font-family: 'Caveat', 'Patrick Hand', 'Comic Sans MS', "
            "cursive. Title 88-110px, body 52-64px, small labels 36-44px.\n\n"
            "TEXT WRAPPING: every Write step is a single line. Apply "
            "white-space:nowrap. If it would exceed safe width, SHRINK the "
            "font-size (loop: while scrollWidth > maxW && fs > 28: fs -= 2). "
            "Never auto-wrap.\n\n"
            "ANIMATION GRAMMAR (every step REVEALS ON, no fade-only):\n"
            "  - 'Write \"...\" in <Color>' → text div, reveal via clip-path "
            "left-to-right wipe (gsap.fromTo el, {clipPath:'inset(0 100% 0 0)'}, "
            "{clipPath:'inset(0 0 0 0)', duration:0.7, ease:'power1.inOut'}, t).\n"
            "  - 'Draw X in <Color> next to \"<text>\"' → render text first, then "
            "    SVG cross of two strokes immediately to its LEFT (50x50px, "
            "    stroke-width 8, stroke-dasharray draw-on, 0.25s per stroke).\n"
            "  - 'Box around \"<text>\"' → measure post-shrink bounding rect, "
            "    draw SVG rect with +24px padding, stroke #4FC3F7 stroke-width 6 "
            "    no fill, rounded 8px, animate via stroke-dasharray ~0.7s.\n\n"
            "LAYOUT GRID (6 rows, no overlaps):\n"
            "  ROW 1 (header):    y = SAFE_TOP, top-left 'Point N' label\n"
            "  ROW 2 (title):     y = SAFE_TOP + 90, centered\n"
            "  ROW 3 (subtitle):  y = SAFE_TOP + 220, centered\n"
            "  ROW 4 (middle band, three columns):\n"
            "    LEFT  (icons):  x ∈ [SAFE_LEFT, SAFE_LEFT + SAFE_W*0.25]\n"
            "    CENTER (key term + box): x ∈ [SAFE_LEFT + SAFE_W*0.27, "
            "                             SAFE_LEFT + SAFE_W*0.73]\n"
            "    RIGHT (X-bullets stacked): x ∈ [SAFE_LEFT + SAFE_W*0.75, SAFE_RIGHT]\n"
            "    y = SAFE_TOP + SAFE_H*0.42\n"
            "  ROW 5 (detail):    y = ROW 4 + (box-height + 60 if box exists else 140)\n"
            "  ROW 6 (footer):    y = SAFE_BOTTOM - 100\n\n"
            "POSITIONAL HINT MAPPING:\n"
            "  'top center'        → ROW 2\n"
            "  'below title'       → ROW 3\n"
            "  'center left'       → ROW 4 LEFT\n"
            "  'at center, large'  → ROW 4 CENTER\n"
            "  'on right'          → ROW 4 RIGHT\n"
            "  'on right below'    → ROW 4 RIGHT, stacked\n"
            "  'below'             → ROW 5\n"
            "  'below in smaller'  → ROW 5, smaller font, stacked\n"
            "  'at bottom'         → ROW 6\n\n"
            "TIMING: step_interval = (TOTAL_DURATION - 1.0) / steps. First step "
            "starts at t=0.3s. All elements remain visible for the rest of the "
            "scene — no exits.\n\n"
            "FORBIDDEN: no scale-punch, no bounce, no rotation, no color outside "
            "the strict palette, no paraphrasing of Write text, no auto-wrap."
        ),
        scene_range_min=1,
        scene_range_max=30,
    ),
]


DEFAULT_STYLE_KEY = "motion_graphic"


# ─── lookup ───────────────────────────────────────────────────────────────


def all_styles() -> list[Style]:
    """Return built-ins first, then user-defined, all in one list. UI uses
    this verbatim to populate the style selector."""
    cfg = load_config()
    return [*_BUILTIN, *cfg.custom_styles]


def get(key: str) -> Style:
    """Find a style by key. Falls back to DEFAULT_STYLE_KEY if missing —
    never raises, so a stale style_key from a saved job can't crash a run."""
    for s in all_styles():
        if s.key == key:
            return s
    for s in _BUILTIN:
        if s.key == DEFAULT_STYLE_KEY:
            return s
    return _BUILTIN[0]


def builtin_keys() -> set[str]:
    return {s.key for s in _BUILTIN}
