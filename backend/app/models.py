from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

_TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class Mode(str, Enum):
    interactive = "interactive"
    batch = "batch"


class BatchTarget(str, Enum):
    none = "none"
    movies = "movies"
    series = "series"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class EnqueueRequest(BaseModel):
    paths: list[str]


class QueueItem(BaseModel):
    id: str
    mode: Mode
    source_path: str
    dest_path: Optional[str] = None
    status: JobStatus
    progress: float = 0.0
    preset: str
    initial_size: Optional[int] = None
    final_size: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None


class SettingsUpdate(BaseModel):
    preset: Optional[str] = None
    batch_enabled: Optional[bool] = None
    batch_target: Optional[BatchTarget] = None
    batch_start_time: Optional[str] = Field(default=None, pattern=_TIME_PATTERN)
    batch_stop_time: Optional[str] = Field(default=None, pattern=_TIME_PATTERN)


class SettingsResponse(BaseModel):
    preset: str
    batch_enabled: bool
    batch_target: BatchTarget
    batch_start_time: str
    batch_stop_time: str
    movie_dir: str
    series_dir: str
    interactive_dir: str


class BatchLogEntry(BaseModel):
    started_at: str
    filename: str
    initial_size: int
    final_size: Optional[int] = None
    status: str
