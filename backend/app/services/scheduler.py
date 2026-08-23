import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import settings
from . import queue_manager, scanner

logger = logging.getLogger(__name__)

SERIES_PROGRESS_KEY = "state:series_progress"
JOB_ID = "build_tonight_queue"

_scheduler: AsyncIOScheduler | None = None


async def _build_movie_batch() -> None:
    current = await queue_manager.get_settings()
    entries = scanner.top_movies_over_threshold(settings.movie_batch_count, settings.movie_min_size_bytes)
    if entries:
        await queue_manager.enqueue_batch([e.path for e in entries], current["preset"])
        logger.info("Queued %d movie(s) for nightly batch", len(entries))


async def _build_series_batch() -> None:
    current = await queue_manager.get_settings()
    redis_client = await queue_manager.get_redis()
    processed = await redis_client.smembers(SERIES_PROGRESS_KEY)

    season_path = scanner.largest_season_dir(exclude=processed)
    if not season_path:
        # every known season has been converted already; start a fresh rotation
        await redis_client.delete(SERIES_PROGRESS_KEY)
        season_path = scanner.largest_season_dir()
        if not season_path:
            return

    episodes = scanner.episodes_of(season_path)
    if not episodes:
        # nothing matches SxxExx here (e.g. an "Extras" folder) - don't retry it every night
        logger.warning("season %s has no matching episode files, skipping", season_path)
        await redis_client.sadd(SERIES_PROGRESS_KEY, season_path)
        return

    await queue_manager.enqueue_batch([e.path for e in episodes], current["preset"])
    await redis_client.sadd(SERIES_PROGRESS_KEY, season_path)
    logger.info("Queued season %s (%d episodes) for nightly batch", season_path, len(episodes))


async def preview_series_batch() -> list:
    """Read-only preview of what the next series batch run would pick, with no side effects."""
    redis_client = await queue_manager.get_redis()
    processed = await redis_client.smembers(SERIES_PROGRESS_KEY)
    season_path = scanner.largest_season_dir(exclude=processed)
    if not season_path:
        season_path = scanner.largest_season_dir()
    if not season_path:
        return []
    return scanner.episodes_of(season_path)


async def recalculate_batch_queue() -> int:
    """Manually rebuild the batch queue from a fresh filesystem scan. Drops any
    stale entries (e.g. files that vanished when a share got remounted) and
    clears a halt, then re-applies the current target so the queue reflects
    what's actually on disk right now."""
    current = await queue_manager.get_settings()
    await queue_manager.clear_batch_queue()
    await queue_manager.resume()
    if current["batch_target"] == "movies":
        await _build_movie_batch()
    elif current["batch_target"] == "series":
        await _build_series_batch()
    status = await queue_manager.get_status()
    return status["queue_batch_len"]


async def build_tonight_queue() -> None:
    current = await queue_manager.get_settings()
    if not current["batch_enabled"]:
        return
    if await queue_manager.is_halted():
        return
    if current["batch_target"] == "movies":
        await _build_movie_batch()
    elif current["batch_target"] == "series":
        await _build_series_batch()


async def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    current = await queue_manager.get_settings()
    hour, minute = (int(p) for p in current["batch_start_time"].split(":"))

    _scheduler = AsyncIOScheduler(timezone=settings.tz)
    _scheduler.add_job(
        build_tonight_queue,
        CronTrigger(hour=hour, minute=minute, timezone=settings.tz),
        id=JOB_ID,
    )
    _scheduler.start()
    return _scheduler


async def reschedule_start_time(batch_start_time: str) -> None:
    """Move the nightly cron to a new time without requiring a restart."""
    if _scheduler is None:
        return
    hour, minute = (int(p) for p in batch_start_time.split(":"))
    _scheduler.reschedule_job(JOB_ID, trigger=CronTrigger(hour=hour, minute=minute, timezone=settings.tz))
