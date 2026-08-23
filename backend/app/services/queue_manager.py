import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import redis.asyncio as redis

from ..config import settings
from . import batch_logger
from .handbrake import Transcode, list_presets
from .renamer import strip_and_tag

logger = logging.getLogger(__name__)

QUEUE_INTERACTIVE = "queue:interactive"
QUEUE_BATCH = "queue:batch"
JOB_IDS_KEY = "jobs:recent"
SETTINGS_KEY = "settings:global"
HALTED_KEY = "state:halted"

_redis: redis.Redis = redis.from_url(settings.redis_url, decode_responses=True)
_current_transcode: Transcode | None = None
_current_job_id: str | None = None
_worker_task: asyncio.Task | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_redis() -> redis.Redis:
    return _redis


# ---------------- settings ----------------

_DEFAULT_START_TIME = f"{settings.batch_start_hour:02d}:{settings.batch_start_minute:02d}"
_DEFAULT_STOP_TIME = f"{settings.batch_stop_hour:02d}:{settings.batch_stop_minute:02d}"


async def get_settings() -> dict:
    data = await _redis.hgetall(SETTINGS_KEY)
    return {
        "preset": data.get("preset", settings.default_preset),
        "batch_enabled": data.get("batch_enabled", "0") == "1",
        "batch_target": data.get("batch_target", "none"),
        "batch_start_time": data.get("batch_start_time", _DEFAULT_START_TIME),
        "batch_stop_time": data.get("batch_stop_time", _DEFAULT_STOP_TIME),
    }


async def update_settings(
    preset: str | None,
    batch_enabled: bool | None,
    batch_target: str | None,
    batch_start_time: str | None = None,
    batch_stop_time: str | None = None,
) -> dict:
    current = await get_settings()
    new_preset = preset if preset is not None else current["preset"]
    new_enabled = batch_enabled if batch_enabled is not None else current["batch_enabled"]
    new_target = batch_target if batch_target is not None else current["batch_target"]
    new_start = batch_start_time if batch_start_time is not None else current["batch_start_time"]
    new_stop = batch_stop_time if batch_stop_time is not None else current["batch_stop_time"]
    if new_target == "none":
        new_enabled = False
    await _redis.hset(SETTINGS_KEY, mapping={
        "preset": new_preset,
        "batch_enabled": "1" if new_enabled else "0",
        "batch_target": new_target,
        "batch_start_time": new_start,
        "batch_stop_time": new_stop,
    })
    return await get_settings()


async def available_presets() -> list[str]:
    return await list_presets()


# ---------------- halted state ----------------

async def is_halted() -> dict | None:
    raw = await _redis.get(HALTED_KEY)
    return json.loads(raw) if raw else None


async def _set_halted(job_id: str, error: str) -> None:
    await _redis.set(HALTED_KEY, json.dumps({"job_id": job_id, "error": error, "at": _now()}))
    await update_settings(preset=None, batch_enabled=False, batch_target=None)


async def resume() -> None:
    await _redis.delete(HALTED_KEY)


# ---------------- job helpers ----------------

async def _create_job(mode: str, source_path: str, preset: str) -> str:
    job_id = str(uuid.uuid4())
    await _redis.hset(f"job:{job_id}", mapping={
        "id": job_id,
        "mode": mode,
        "source_path": source_path,
        "status": "queued",
        "progress": "0",
        "preset": preset,
        "initial_size": str(os.path.getsize(source_path)) if os.path.exists(source_path) else "0",
    })
    await _redis.lpush(JOB_IDS_KEY, job_id)
    await _redis.ltrim(JOB_IDS_KEY, 0, 199)
    return job_id


def _allowed_roots() -> list[str]:
    return [
        os.path.normpath(settings.movie_dir),
        os.path.normpath(settings.series_dir),
        os.path.normpath(settings.interactive_dir),
    ]


def _validate_source_path(path: str) -> None:
    normalized = os.path.normpath(path)
    for root in _allowed_roots():
        if normalized == root or normalized.startswith(root + os.sep):
            return
    raise ValueError(f"path is outside the configured folders: {path}")


async def _pending_source_paths() -> set[str]:
    """Source paths that are already queued or actively processing, across both
    queues - used to keep the same file from ever being enqueued twice."""
    paths: set[str] = set()
    for queue_key in (QUEUE_INTERACTIVE, QUEUE_BATCH):
        for job_id in await _redis.lrange(queue_key, 0, -1):
            path = await _redis.hget(f"job:{job_id}", "source_path")
            if path:
                paths.add(path)
    if _current_job_id is not None:
        path = await _redis.hget(f"job:{_current_job_id}", "source_path")
        if path:
            paths.add(path)
    return paths


async def enqueue_interactive(paths: list[str]) -> list[str]:
    current = await get_settings()
    pending = await _pending_source_paths()
    job_ids = []
    for path in paths:
        _validate_source_path(path)
        if path in pending:
            continue
        pending.add(path)
        job_id = await _create_job("interactive", path, current["preset"])
        await _redis.rpush(QUEUE_INTERACTIVE, job_id)
        job_ids.append(job_id)
    return job_ids


async def enqueue_batch(paths: list[str], preset: str) -> list[str]:
    pending = await _pending_source_paths()
    job_ids = []
    for path in paths:
        if path in pending:
            continue
        pending.add(path)
        job_id = await _create_job("batch", path, preset)
        await _redis.rpush(QUEUE_BATCH, job_id)
        job_ids.append(job_id)
    return job_ids


async def remove_batch_job(job_id: str) -> bool:
    removed = await _redis.lrem(QUEUE_BATCH, 0, job_id)
    if removed:
        await _redis.delete(f"job:{job_id}")
    return bool(removed)


async def clear_batch_queue() -> int:
    """Drop every queued (not yet running) batch job and its hash - used to wipe
    out stale entries (e.g. left over from a remounted share) before a rebuild."""
    job_ids = await _redis.lrange(QUEUE_BATCH, 0, -1)
    if job_ids:
        await _redis.delete(*[f"job:{job_id}" for job_id in job_ids])
    await _redis.delete(QUEUE_BATCH)
    return len(job_ids)


async def get_status() -> dict:
    ids = await _redis.lrange(JOB_IDS_KEY, 0, 199)
    jobs = []
    for job_id in ids:
        data = await _redis.hgetall(f"job:{job_id}")
        if data:
            jobs.append(data)
    return {
        "jobs": jobs,
        "queue_interactive_len": await _redis.llen(QUEUE_INTERACTIVE),
        "queue_batch_len": await _redis.llen(QUEUE_BATCH),
        "halted": await is_halted(),
    }


async def preview_batch_queue() -> list[str]:
    return await _redis.lrange(QUEUE_BATCH, 0, -1)


# ---------------- stop all ----------------

async def stop_all() -> None:
    ids = await _redis.lrange(QUEUE_INTERACTIVE, 0, -1)
    for job_id in ids:
        await _redis.hset(f"job:{job_id}", mapping={"status": "cancelled"})
    await _redis.delete(QUEUE_INTERACTIVE)
    if _current_transcode is not None and _current_job_id is not None:
        await _redis.hset(f"job:{_current_job_id}", mapping={"status": "cancelled"})
        _current_transcode.kill()


# ---------------- worker loop ----------------

def _parse_hhmm(value: str) -> tuple[int, int]:
    hour, minute = value.split(":")
    return int(hour), int(minute)


def _in_batch_window(start_time: str, stop_time: str) -> bool:
    now = datetime.now(ZoneInfo(settings.tz))
    now_minutes = now.hour * 60 + now.minute
    start_hour, start_minute = _parse_hhmm(start_time)
    stop_hour, stop_minute = _parse_hhmm(stop_time)
    start_minutes = start_hour * 60 + start_minute
    stop_minutes = stop_hour * 60 + stop_minute
    return start_minutes <= now_minutes < stop_minutes


async def _process_job(job_id: str) -> None:
    global _current_transcode, _current_job_id
    job_key = f"job:{job_id}"
    job = await _redis.hgetall(job_key)
    source_path = job["source_path"]
    preset = job["preset"]

    if not os.path.exists(source_path):
        await _redis.hset(job_key, mapping={"status": "failed", "error": "source file not found"})
        await _set_halted(job_id, "source file not found")
        return

    initial_size = os.path.getsize(source_path)
    started_at = _now()
    directory = os.path.dirname(source_path)
    new_name = strip_and_tag(os.path.basename(source_path), preset)
    dest_path = os.path.join(directory, new_name)
    tmp_dest = dest_path + ".transcoding.tmp"

    await _redis.hset(job_key, mapping={
        "status": "running",
        "started_at": started_at,
        "initial_size": str(initial_size),
        "dest_path": dest_path,
    })

    transcode = Transcode(source_path=source_path, dest_path=tmp_dest, preset=preset)
    _current_transcode = transcode
    _current_job_id = job_id
    try:
        try:
            async for progress in transcode.run():
                await _redis.hset(job_key, mapping={"progress": str(progress)})
        except Exception as exc:
            transcode.kill()
            if os.path.exists(tmp_dest):
                os.remove(tmp_dest)
            if (await _redis.hget(job_key, "status")) == "cancelled":
                return
            logger.exception("job %s crashed mid-transcode", job_id)
            error = f"{type(exc).__name__}: {exc}"
            finished_at = _now()
            await _redis.hset(job_key, mapping={"status": "failed", "error": error, "finished_at": finished_at})
            batch_logger.append_entry(started_at, finished_at, os.path.basename(source_path), initial_size, None, "failed")
            await _set_halted(job_id, error)
            return
    finally:
        _current_transcode = None
        _current_job_id = None

    result = transcode.result
    cancelled = (await _redis.hget(job_key, "status")) == "cancelled"

    if cancelled:
        if os.path.exists(tmp_dest):
            os.remove(tmp_dest)
        return

    if result is None or result.exit_code != 0:
        if os.path.exists(tmp_dest):
            os.remove(tmp_dest)
        error = result.stderr_tail if result else "process did not complete"
        finished_at = _now()
        await _redis.hset(job_key, mapping={"status": "failed", "error": error, "finished_at": finished_at})
        batch_logger.append_entry(started_at, finished_at, os.path.basename(source_path), initial_size, None, "failed")
        await _set_halted(job_id, error)
        return

    os.replace(tmp_dest, dest_path)
    os.remove(source_path)
    final_size = os.path.getsize(dest_path)
    finished_at = _now()
    await _redis.hset(job_key, mapping={
        "status": "done",
        "progress": "100",
        "final_size": str(final_size),
        "finished_at": finished_at,
    })
    batch_logger.append_entry(started_at, finished_at, os.path.basename(dest_path), initial_size, final_size, "done")


async def _worker_loop() -> None:
    while True:
        try:
            if await is_halted():
                await asyncio.sleep(2)
                continue

            job_id = await _redis.lpop(QUEUE_INTERACTIVE)
            if not job_id:
                current = await get_settings()
                if current["batch_enabled"] and _in_batch_window(current["batch_start_time"], current["batch_stop_time"]):
                    job_id = await _redis.lpop(QUEUE_BATCH)

            if not job_id:
                await asyncio.sleep(2)
                continue

            await _process_job(job_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("worker loop iteration failed")
            await asyncio.sleep(2)


def start_worker() -> None:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())
