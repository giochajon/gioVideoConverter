from fastapi import APIRouter

from ..config import settings
from ..services import batch_logger, queue_manager, scanner, scheduler

router = APIRouter(prefix="/api/batch", tags=["batch"])


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

    if current["batch_target"] == "movies":
        entries = scanner.top_movies_over_threshold(settings.movie_batch_count, settings.movie_min_size_bytes)
    elif current["batch_target"] == "series":
        entries = await scheduler.preview_series_batch()
    else:
        entries = []

    preview = [{"source_path": e.path, "initial_size": str(e.size), "status": "preview"} for e in entries]
    return {"queued": False, "jobs": preview}


@router.get("/log")
async def log(limit: int = 200):
    return batch_logger.read_entries(limit)
