"""ffmpeg wrappers: merge audio + silent video per scene, concat scenes
with optional crossfades.

Imported from v1, hardened slightly:
  * Output duration is LOCKED to the audio length per scene. If the
    rendered video is shorter than narration, we tpad-clone the last frame.
    Guarantees per-scene A/V sync regardless of HyperFrames timing drift.
  * Concat uses xfade + acrossfade when transitions are wanted, plain
    `-f concat` otherwise (faster and lossless).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def _ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def _ffprobe() -> str:
    return shutil.which("ffprobe") or "ffprobe"


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [_ffprobe(), "-v", "error",
         "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {path}: {out.stderr}")
    return float(json.loads(out.stdout)["format"]["duration"])


def merge_audio_video(video_in: Path, audio_in: Path, out: Path) -> None:
    """Lock output duration to audio length; clone the last video frame if
    audio is longer than video."""
    out.parent.mkdir(parents=True, exist_ok=True)
    v_dur = probe_duration(video_in)
    a_dur = probe_duration(audio_in)
    pad = max(0.0, a_dur - v_dur)
    base = [_ffmpeg(), "-y", "-i", str(video_in), "-i", str(audio_in)]
    if pad > 0.02:
        cmd = base + [
            "-filter_complex",
            f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.3f}[v]",
            "-map", "[v]", "-map", "1:a:0",
            "-t", f"{a_dur:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-r", "30",
            str(out),
        ]
    else:
        cmd = base + [
            "-map", "0:v:0", "-map", "1:a:0",
            "-t", f"{a_dur:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-r", "30",
            str(out),
        ]
    _run(cmd)


def concat_scenes(
    scene_files: list[Path],
    output: Path,
    *,
    transition_seconds: float = 0.0,
    transition_name: str = "fade",
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if transition_seconds <= 0.0 or len(scene_files) < 2:
        _concat_plain(scene_files, output)
    else:
        _concat_xfade(scene_files, output, transition_seconds, transition_name)


def _concat_plain(scene_files: list[Path], output: Path) -> None:
    filelist = output.parent / "concat_list.txt"
    filelist.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in scene_files),
        encoding="utf-8",
    )
    _run([
        _ffmpeg(), "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(filelist),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-r", "30",
        str(output),
    ])
    filelist.unlink(missing_ok=True)


def _concat_xfade(
    scene_files: list[Path],
    output: Path,
    t: float,
    transition_name: str,
) -> None:
    durations = [probe_duration(p) for p in scene_files]
    n = len(scene_files)
    inputs: list[str] = []
    for p in scene_files:
        inputs += ["-i", str(p)]
    filter_parts: list[str] = []
    prev_v = "[0:v]"
    prev_a = "[0:a]"
    cumulative = 0.0
    for i in range(1, n):
        cumulative += durations[i - 1] - t
        v_out = f"[v{i}]"
        a_out = f"[a{i}]"
        filter_parts.append(
            f"{prev_v}[{i}:v]xfade=transition={transition_name}:"
            f"duration={t}:offset={cumulative:.3f}{v_out}"
        )
        filter_parts.append(f"{prev_a}[{i}:a]acrossfade=d={t}{a_out}")
        prev_v = v_out
        prev_a = a_out
    _run([
        _ffmpeg(), "-y", *inputs,
        "-filter_complex", ";".join(filter_parts),
        "-map", prev_v, "-map", prev_a,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-r", "30",
        str(output),
    ])


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FFmpegError(
            f"Command failed: {' '.join(cmd[:4])}…\n"
            f"--- STDERR ---\n{proc.stderr}"
        )
