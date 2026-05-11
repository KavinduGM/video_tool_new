"""Job queue + worker thread.

Single worker, jobs processed in FIFO order. The user can submit dozens of
scripts; the worker runs each to completion (or failure) and moves on.
The queue persists to disk so a restart resumes where it left off.

State machine per job:
  QUEUED → RUNNING → COMPLETED
                  ↘ FAILED
                  ↘ CANCELLED (user requested)

Crash safety:
  * Each scene's MP4 is staged inside <output_folder>/<title>_partial/scenes/
    as it completes (via manifest.py). A crash mid-job means the next run
    of that job resumes from the scene after the last one staged.
  * Queue state (the Job list) is persisted on every mutation.
"""
from __future__ import annotations

import json
import shutil
import threading
import time
import traceback
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path

from . import (
    claude,
    composer,
    config,
    hyperframes,
    manifest,
    paths,
    script_parser,
    styles,
    tts,
)
from .models import Job, JobProgress, JobRequest, JobStatus, ScriptFormat


# ─── persistent queue file ────────────────────────────────────────────────


QUEUE_FILE = config.CONFIG_DIR / "queue.json"
WORKSPACE = Path(__file__).parent.parent / "workspace"
LOG_LINE_CAP = 500  # keep the most recent N log lines per job, drop older


_lock = threading.Lock()
_jobs: dict[str, Job] = {}
_order: deque[str] = deque()
_worker_thread: threading.Thread | None = None
_shutdown = threading.Event()
_cancel_request: set[str] = set()
_current_job_id: str | None = None


# ─── public API used by FastAPI routes ────────────────────────────────────


def start_worker() -> None:
    """Idempotent. Spawns the single worker thread if it isn't already up."""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _load_from_disk()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()


def stop_worker() -> None:
    """Used during shutdown — signals the worker to finish the current scene
    and exit. Does not abort mid-scene."""
    _shutdown.set()


def enqueue(req: JobRequest) -> Job:
    """Add a new job. Returns it (with id, created_at populated)."""
    job = Job(id=uuid.uuid4().hex[:8], request=req)
    with _lock:
        _jobs[job.id] = job
        _order.append(job.id)
        _save_to_disk_locked()
    return job


def get(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def list_all() -> list[Job]:
    """Most recent first. Includes finished jobs so the UI can render
    history."""
    with _lock:
        return sorted(
            _jobs.values(),
            key=lambda j: j.created_at,
            reverse=True,
        )


def cancel(job_id: str) -> bool:
    """Mark a queued job CANCELLED, or request the running job to stop
    after the current scene finishes."""
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return False
        if job.status == JobStatus.QUEUED:
            job.status = JobStatus.CANCELLED
            try:
                _order.remove(job_id)
            except ValueError:
                pass
            _save_to_disk_locked()
            return True
        if job.status == JobStatus.RUNNING:
            _cancel_request.add(job_id)
            return True
    return False


def retry(job_id: str) -> bool:
    """Re-queue a FAILED or CANCELLED job. It keeps its existing staging
    folder so completed scenes are reused (resume semantics)."""
    with _lock:
        job = _jobs.get(job_id)
        if not job or job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
            return False
        job.status = JobStatus.QUEUED
        job.error_message = None
        job.error_traceback = None
        job.started_at = None
        job.completed_at = None
        if job_id not in _order:
            _order.append(job_id)
        _save_to_disk_locked()
        return True


def delete(job_id: str) -> bool:
    """Remove a finished/failed job from the list. Refuses to delete a
    currently-running job — cancel it first."""
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return False
        if job.status == JobStatus.RUNNING:
            return False
        _jobs.pop(job_id, None)
        try:
            _order.remove(job_id)
        except ValueError:
            pass
        _save_to_disk_locked()
        return True


# ─── persistence ──────────────────────────────────────────────────────────


def _save_to_disk_locked() -> None:
    """Caller must hold _lock."""
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "order": list(_order),
        "jobs": {jid: j.model_dump(mode="json") for jid, j in _jobs.items()},
    }
    tmp = QUEUE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(QUEUE_FILE)


def _load_from_disk() -> None:
    if not QUEUE_FILE.exists():
        return
    try:
        data = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return
    with _lock:
        for jid, j in data.get("jobs", {}).items():
            try:
                job = Job.model_validate(j)
            except Exception:
                continue
            # Any job left RUNNING from a previous process did NOT actually
            # finish — re-queue it so the worker can resume it.
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.QUEUED
            _jobs[jid] = job
        _order.clear()
        for jid in data.get("order", []):
            if jid in _jobs and _jobs[jid].status == JobStatus.QUEUED:
                _order.append(jid)


# ─── worker ───────────────────────────────────────────────────────────────


def _worker_loop() -> None:
    while not _shutdown.is_set():
        job_id = _next_queued_job_id()
        if not job_id:
            time.sleep(1.0)
            continue
        try:
            _run_job(job_id)
        except Exception as e:
            # Anything that escaped _run_job's own handlers — mark failed.
            with _lock:
                j = _jobs.get(job_id)
                if j:
                    j.status = JobStatus.FAILED
                    j.error_message = str(e)
                    j.error_traceback = traceback.format_exc()
                    j.completed_at = datetime.now()
                    _save_to_disk_locked()


def _next_queued_job_id() -> str | None:
    with _lock:
        while _order:
            jid = _order[0]
            j = _jobs.get(jid)
            if j and j.status == JobStatus.QUEUED:
                return jid
            _order.popleft()
        return None


def _log(job: Job, line: str) -> None:
    job.log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {line}")
    if len(job.log_lines) > LOG_LINE_CAP:
        # Keep the head note + the tail so the user sees both the start
        # of the run and the most recent activity.
        job.log_lines = job.log_lines[:5] + ["… (older lines truncated) …"] + \
                         job.log_lines[-(LOG_LINE_CAP - 6):]


def _check_cancel(job_id: str) -> bool:
    with _lock:
        return job_id in _cancel_request


# ─── the actual pipeline ──────────────────────────────────────────────────


def _run_job(job_id: str) -> None:
    """End-to-end render of one job. Heavily commented because this is the
    integration point — every external service touches here."""
    global _current_job_id

    with _lock:
        job = _jobs[job_id]
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        _current_job_id = job_id
        _save_to_disk_locked()

    req = job.request
    cfg = config.load()
    profile = next(
        (p for p in cfg.voice_profiles if p.id == req.voice_profile_id), None
    )
    if not profile:
        _fail(job, f"Voice profile '{req.voice_profile_id}' not found.")
        return

    # 1. Detect + parse the script. Freeform requires Claude normalization.
    _log(job, f"Detecting script format for '{req.title}'…")
    fmt = script_parser.detect_format(req.script)
    job.detected_format = fmt
    _log(job, f"Detected format: {fmt.value}")

    style = styles.get(req.style_key)
    canvas = hyperframes.canvas_for(req.canvas_key)
    script_text = req.script

    if fmt == ScriptFormat.FREEFORM:
        _log(job, "Normalizing freeform script via Claude…")
        try:
            script_text = claude.normalize_script(
                raw_text=req.script,
                style=style,
                anthropic_api_key=cfg.anthropic_api_key,
                model=req.anthropic_model,
            )
            fmt = ScriptFormat.TAGGED
        except Exception as e:
            _fail(job, f"Script normalization failed: {e}")
            return

    try:
        scenes = script_parser.parse(script_text, fmt)
    except Exception as e:
        _fail(job, f"Script parse failed: {e}")
        return

    total = len(scenes)
    job.progress.total_scenes = total
    _log(job, f"Parsed {total} scene(s). Canvas: {canvas.label}.")

    # 2. Reserve unique output paths and set up staging.
    output_folder = Path(req.output_folder).expanduser()
    output_folder.mkdir(parents=True, exist_ok=True)
    final_mp4, staging = paths.reserve_unique_paths(output_folder, req.title)

    # If a previous run with the same script + style + canvas + title is
    # staged here, we'd resume. But because reserve_unique_paths just
    # bumped the suffix, the staging folder is brand-new on disk — so
    # resume in this v2 always uses the SAME job rerun rather than a
    # collision-bumped sibling. (Retry via the API uses the original
    # job id, which uses the original staging folder.)
    hash_value = manifest.script_hash(script_text)
    can_resume, existing = manifest.is_resumable(
        staging,
        expected_hash=hash_value,
        expected_total=total,
        expected_style=req.style_key,
        expected_canvas=req.canvas_key.value,
    )
    if can_resume and existing:
        m = existing
        already = manifest.completed_indices(m)
        _log(job, f"Resuming: {len(already)}/{total} scene(s) cached.")
    else:
        if existing:
            _log(job, "Stale staging found — clearing and starting fresh.")
            manifest.cleanup(staging)
        m = manifest.init(
            script_hash_value=hash_value,
            total_scenes=total,
            title=req.title,
            style_key=req.style_key,
            canvas_key=req.canvas_key.value,
        )
        already = set()
        manifest.save(staging, m)

    (staging / "scenes").mkdir(parents=True, exist_ok=True)

    # 3. Per-scene pipeline.
    run_dir = WORKSPACE / job.id
    run_dir.mkdir(parents=True, exist_ok=True)
    final_scene_files: list[Path] = list(manifest.staged_scene_files(staging, m))
    start_time = time.monotonic()

    for pos, scene in enumerate(scenes, start=1):
        if _check_cancel(job.id):
            _log(job, "Cancellation requested — stopping after current scene.")
            break

        job.progress.current_scene = pos
        job.progress.elapsed_seconds = time.monotonic() - start_time
        if pos > 1:
            avg = job.progress.elapsed_seconds / max(pos - 1, 1)
            job.progress.eta_seconds = avg * (total - pos + 1)

        tag = f"Scene {scene.index}"

        if scene.index in already:
            job.progress.current_step = f"{tag}: cached, skipping"
            _log(job, f"{tag}: cached from prior run — skip API calls.")
            continue

        try:
            # --- audio ---------------------------------------------------
            job.progress.current_step = f"{tag}: generating audio"
            _log(job, job.progress.current_step)
            audio_path = run_dir / "audio" / f"scene_{scene.index}.mp3"
            tail_pad = max(0.5, req.transition_seconds + 0.3)
            # The TTS server accepts <break time="Ns"/> tags verbatim — we
            # don't auto-inject any. Append a trailing silent pad ourselves
            # by inserting a break tag at the end of the narration.
            narration_with_pad = (
                f"{scene.narration} <break time=\"{tail_pad:.2f}s\" />"
            )
            gen = tts.generate(
                profile, narration_with_pad, audio_path,
                speed=req.narration_speed, fmt="mp3",
            )
            _log(job, f"{tag}: audio {gen.duration_seconds:.2f}s")

            # --- claude HTML --------------------------------------------
            job.progress.current_step = f"{tag}: generating visuals (Claude)"
            _log(job, job.progress.current_step)
            scene_html = claude.generate_scene_html(
                anthropic_api_key=cfg.anthropic_api_key,
                model=req.anthropic_model,
                canvas=canvas,
                style=style,
                scene_index=pos,
                total_scenes=total,
                narration=scene.narration,
                visual_instructions=scene.visual,
                duration_seconds=gen.duration_seconds,
            )

            # --- compose into full HyperFrames doc -----------------------
            full_html = hyperframes.build_single_scene_composition(
                scene_body_html=scene_html.body_html,
                timeline_animations_js=scene_html.timeline_js,
                duration_seconds=gen.duration_seconds,
                canvas=canvas,
            )

            # --- render ---------------------------------------------------
            job.progress.current_step = f"{tag}: rendering (HyperFrames)"
            _log(job, job.progress.current_step)
            project = run_dir / "scenes" / f"scene_{scene.index}"
            hyperframes.init_project(project)
            hyperframes.write_composition(project, full_html)
            silent_mp4 = run_dir / "renders" / f"scene_{scene.index}.mp4"
            hyperframes.render(project, silent_mp4)

            # --- merge audio + video ------------------------------------
            job.progress.current_step = f"{tag}: merging audio + video"
            _log(job, job.progress.current_step)
            merged_mp4 = run_dir / "merged" / f"scene_{scene.index}.mp4"
            composer.merge_audio_video(silent_mp4, gen.path, merged_mp4)

            # --- stage to output folder (durable) -----------------------
            staged = manifest.scene_path(staging, scene.index)
            staged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(merged_mp4, staged)
            relative = staged.relative_to(staging).as_posix()
            manifest.mark_complete(m, scene.index, relative)
            manifest.save(staging, m)
            final_scene_files.append(staged)
            _log(job, f"{tag}: saved → {staged}")

        except Exception as e:
            tb = traceback.format_exc()
            _log(job, f"{tag} FAILED: {type(e).__name__}: {e}")
            if final_scene_files:
                _log(job,
                     f"Partial recovery: will finalize with "
                     f"{len(final_scene_files)} completed scene(s).")
                break
            _fail(job, f"{tag} failed: {e}", traceback_text=tb)
            return

    if not final_scene_files:
        _fail(job, "No scenes completed; nothing to export.")
        return

    # 4. Concat into the final mp4 with optional crossfades.
    job.progress.current_step = (
        f"Concatenating {len(final_scene_files)} scene(s)…"
    )
    _log(job, job.progress.current_step)
    final_tmp = staging / "_final_in_progress.mp4"
    try:
        composer.concat_scenes(
            final_scene_files, final_tmp,
            transition_seconds=req.transition_seconds,
            transition_name=req.transition_name,
        )
    except Exception as e:
        _fail(job, f"Final concat failed: {e}", traceback_text=traceback.format_exc())
        return

    # Atomic rename into place.
    if final_mp4.exists():
        final_mp4.unlink()
    shutil.move(str(final_tmp), str(final_mp4))
    _log(job, f"Saved: {final_mp4}")

    with _lock:
        job.status = (
            JobStatus.CANCELLED if job.id in _cancel_request
            else JobStatus.COMPLETED
        )
        job.result_path = str(final_mp4)
        job.completed_at = datetime.now()
        _cancel_request.discard(job.id)
        _save_to_disk_locked()


def _fail(job: Job, message: str, *, traceback_text: str | None = None) -> None:
    with _lock:
        job.status = JobStatus.FAILED
        job.error_message = message
        if traceback_text:
            job.error_traceback = traceback_text
        job.completed_at = datetime.now()
        _save_to_disk_locked()
