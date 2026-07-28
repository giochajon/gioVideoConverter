import json
import os
from datetime import datetime, timezone

from ..config import settings

_LOG_PATH = os.path.join(settings.log_dir, "batch_log.jsonl")


def append_entry(
    started_at: str,
    finished_at: str,
    filename: str,
    initial_size: int,
    final_size: int | None,
    status: str,
) -> None:
    os.makedirs(settings.log_dir, exist_ok=True)
    duration_seconds = (datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)).total_seconds()
    entry = {
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
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


def remove_entry(started_at: str) -> bool:
    """Remove the single log entry with this started_at timestamp (unique per job)."""
    if not os.path.exists(_LOG_PATH):
        return False
    with open(_LOG_PATH) as f:
        lines = f.readlines()
    kept = []
    removed = False
    for line in lines:
        if not removed and json.loads(line).get("started_at") == started_at:
            removed = True
            continue
        kept.append(line)
    if removed:
        with open(_LOG_PATH, "w") as f:
            f.writelines(kept)
    return removed


def remove_older_than(cutoff_iso: str) -> int:
    """Remove all log entries with started_at before cutoff_iso. Returns count removed."""
    if not os.path.exists(_LOG_PATH):
        return 0
    cutoff = datetime.fromisoformat(cutoff_iso)
    with open(_LOG_PATH) as f:
        lines = f.readlines()
    kept = []
    removed = 0
    for line in lines:
        entry = json.loads(line)
        if datetime.fromisoformat(entry["started_at"]) < cutoff:
            removed += 1
            continue
        kept.append(line)
    if removed:
        with open(_LOG_PATH, "w") as f:
            f.writelines(kept)
    return removed


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
