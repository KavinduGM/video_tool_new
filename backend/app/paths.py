"""Path utilities. Today's job is filename-collision handling.

When the user submits a job titled `My Video`, we save `My Video.mp4` in
their output folder. If that file already exists (a previous run, or a
duplicate-titled job), we DO NOT overwrite — we suffix with `_2`, `_3`, etc.
The same suffix is applied to the `<title>_partial/` staging folder so the
two stay coupled.
"""
from __future__ import annotations

import re
from pathlib import Path


# Characters that are illegal in filenames on Windows. macOS/Linux are more
# permissive but it's easier to apply one strict rule everywhere.
_WIN_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename_stem(title: str) -> str:
    """Normalize a user-supplied video title into a filesystem-safe stem.
    Preserves Unicode letters/digits/spaces; strips control chars and the
    Windows-illegal punctuation set; collapses runs of whitespace."""
    cleaned = _WIN_ILLEGAL.sub("", title).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Windows doesn't allow trailing dots or spaces. Strip them.
    cleaned = cleaned.rstrip(" .")
    return cleaned or "untitled"


def reserve_unique_paths(output_folder: Path, title: str) -> tuple[Path, Path]:
    """Compute the final mp4 path and matching staging-folder path, both
    guaranteed not to exist yet (auto-suffix on collision).

    Returns (final_mp4, staging_dir). Neither is created — caller owns mkdir.
    """
    stem = sanitize_filename_stem(title)
    candidate_stem = stem
    n = 1
    while True:
        mp4 = output_folder / f"{candidate_stem}.mp4"
        staging = output_folder / f"{candidate_stem}_partial"
        # We reserve the pair atomically: both must be free, else bump.
        if not mp4.exists() and not staging.exists():
            return mp4, staging
        n += 1
        candidate_stem = f"{stem}_{n}"
        if n > 9999:  # paranoid guard
            raise RuntimeError(f"Could not find a free filename for '{title}'")
