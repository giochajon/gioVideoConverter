import json
import os
from datetime import datetime, timezone

from ..config import settings

_LOG_PATH = os.path.join(settings.log_dir, "batch_log.jsonl")


def append_entry(started_at: str, filename: str, initial_size: int, final_size: int | None, status: str) -> None:
    os.makedirs(settings.log_dir, exist_ok=True)
    entry = {
        "started_at": started_at,
        "filename": filename,
        "initial_size": initial_size,
        "final_size": final_size,
        "status": status,
    }
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_entries(limit: int = 200) -> list[dict]:
    if not os.path.exists(_LOG_PATH):
        return []
    with open(_LOG_PATH) as f:
        lines = f.readlines()
    entries = [json.loads(line) for line in lines[-limit:]]
    entries.reverse()
    return entries


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
