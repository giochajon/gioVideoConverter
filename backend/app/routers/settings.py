from fastapi import APIRouter

from ..config import settings as app_settings
from ..models import SettingsUpdate
from ..services import queue_manager, scheduler

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings():
    current = await queue_manager.get_settings()
    return {
        **current,
        "movie_dir": app_settings.movie_dir,
        "series_dir": app_settings.series_dir,
        "interactive_dir": app_settings.interactive_dir,
    }


@router.put("")
async def put_settings(update: SettingsUpdate):
    batch_target = update.batch_target.value if update.batch_target else None
    result = await queue_manager.update_settings(
        update.preset, update.batch_enabled, batch_target,
        update.batch_start_time, update.batch_stop_time,
    )
    if update.batch_start_time is not None:
        await scheduler.reschedule_start_time(update.batch_start_time)
    return result


@router.get("/presets")
async def presets():
    return await queue_manager.available_presets()
