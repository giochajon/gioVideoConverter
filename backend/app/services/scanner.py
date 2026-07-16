import os
import re
from dataclasses import dataclass

from ..config import settings

_EPISODE_RE = re.compile(r"[Ss](\d{1,2})[Ee](\d{1,2})")
_CONVERTED_TAG_RE = re.compile(r"\[[^\[\]]*\]\s*$")


def is_video(name: str) -> bool:
    return name.lower().endswith(settings.video_extensions)


def is_already_converted(name: str) -> bool:
    """True if the filename stem ends in a `[...]` tag - the marker strip_and_tag()
    appends after a successful conversion, so these should never be re-batched."""
    stem, _ext = os.path.splitext(name)
    return bool(_CONVERTED_TAG_RE.search(stem))


@dataclass
class FileEntry:
    path: str
    name: str
    size: int


def list_movies(root: str | None = None) -> list[FileEntry]:
    root = root or settings.movie_dir
    entries: list[FileEntry] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if is_video(name) and not is_already_converted(name):
                full = os.path.join(dirpath, name)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                entries.append(FileEntry(path=full, name=name, size=size))
    return entries


def top_movies_over_threshold(count: int, min_size: int) -> list[FileEntry]:
    movies = [m for m in list_movies() if m.size >= min_size]
    movies.sort(key=lambda m: m.size, reverse=True)
    return movies[:count]


def _dir_size(path: str) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return total


_SEASON_RE = re.compile(r"^season\s*\d+", re.IGNORECASE)


def is_season_dir(name: str) -> bool:
    return bool(_SEASON_RE.match(name.strip()))


def list_season_dirs(root: str | None = None) -> list[str]:
    """Find every "Season NN"-named folder anywhere under root, regardless of
    how many category/show levels separate root from it."""
    root = root or settings.series_dir
    seasons = []
    for dirpath, dirnames, _filenames in os.walk(root):
        for name in dirnames:
            if is_season_dir(name):
                seasons.append(os.path.join(dirpath, name))
    return seasons


def largest_season_dir(root: str | None = None, exclude: set[str] | None = None) -> str | None:
    exclude = exclude or set()
    candidates = [s for s in list_season_dirs(root) if s not in exclude]
    if not candidates:
        return None
    return max(candidates, key=_dir_size)


def episodes_of(season_path: str) -> list[FileEntry]:
    entries = []
    if not os.path.isdir(season_path):
        return entries
    for fname in sorted(os.listdir(season_path)):
        fpath = os.path.join(season_path, fname)
        if (
            os.path.isfile(fpath)
            and is_video(fname)
            and not is_already_converted(fname)
            and _EPISODE_RE.search(fname)
        ):
            try:
                size = os.path.getsize(fpath)
            except OSError:
                continue
            entries.append(FileEntry(path=fpath, name=fname, size=size))
    return entries
