import asyncio
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..models import RemoveLogEntryRequest
from ..services import batch_logger, queue_manager, scanner, scheduler

router = APIRouter(prefix="/api/batch", tags=["batch"])

# The preview scan below walks the whole movie/series library over the network
# share, which can take several seconds - caching it means the Batch page's
# 5-second poll doesn't re-trigger that scan on every tick.
_PREVIEW_TTL_SECONDS = 30
_preview_cache: dict = {"at": 0.0, "target": None, "entries": []}


@router.get("/tonight")
async def tonight():
    job_ids = await queue_manager.preview_batch_queue()
    if job_ids:
        redis_client = await queue_manager.get_redis()
        jobs = []
        for job_id in job_ids:
            data = await redis_client.hgetall(f"job:{job_id}")
            if data:
                jobs.append(data)
        return {"queued": True, "jobs": jobs}

    # Nothing has actually been queued yet (the nightly cron hasn't fired) -
    # show a live, read-only preview of what it would pick right now instead
    # of leaving the page blank until 2 AM.
    current = await queue_manager.get_settings()
    if not current["batch_enabled"]:
        return {"queued": False, "jobs": []}

    target = current["batch_target"]
    now = time.monotonic()
    if target == _preview_cache["target"] and now - _preview_cache["at"] < _PREVIEW_TTL_SECONDS:
        entries = _preview_cache["entries"]
    else:
        if target == "movies":
            entries = await asyncio.to_thread(
                scanner.top_movies_over_threshold, settings.movie_batch_count, settings.movie_min_size_bytes
            )
        elif target == "series":
            entries = await scheduler.preview_series_batch()
        else:
            entries = []
        _preview_cache.update(at=now, target=target, entries=entries)

    preview = [{"source_path": e.path, "initial_size": str(e.size), "status": "preview"} for e in entries]
    return {"queued": False, "jobs": preview}


@router.post("/recalculate")
async def recalculate():
    queued = await scheduler.recalculate_batch_queue()
    return {"queued": queued}


@router.delete("/queue/{job_id}")
async def remove_queue_item(job_id: str):
    ok = await queue_manager.remove_batch_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found in the batch queue")
    return {"ok": True}


@router.get("/log")
async def log(limit: int = 200):
    return batch_logger.read_entries(limit)


@router.post("/log/remove")
async def remove_log_entry(req: RemoveLogEntryRequest):
    ok = batch_logger.remove_entry(req.started_at)
    if not ok:
        raise HTTPException(status_code=404, detail="log entry not found")
    return {"ok": True}


@router.post("/log/prune")
async def prune_log():
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    removed = batch_logger.remove_older_than(cutoff)
    return {"removed": removed}
