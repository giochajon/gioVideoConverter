import os

from fastapi import APIRouter, HTTPException, Query

from ..config import settings
from ..services import permissions
from ..services.scanner import is_video

router = APIRouter(prefix="/api/browse", tags=["browse"])

ROOTS = {
    "interactive": lambda: settings.interactive_dir,
    "movies": lambda: settings.movie_dir,
    "series": lambda: settings.series_dir,
}


def _root_path(root: str) -> str:
    if root not in ROOTS:
        raise HTTPException(status_code=400, detail="unknown root")
    return ROOTS[root]()


def _safe_join(root: str, rel_path: str) -> str:
    target = os.path.normpath(os.path.join(root, rel_path.lstrip("/")))
    if not (target == root or target.startswith(root + os.sep)):
        raise HTTPException(status_code=400, detail="invalid path")
    return target


@router.get("/roots")
async def roots():
    """Configured folders plus a live read/write permission check for each."""
    result = {}
    for key, getter in ROOTS.items():
        path = getter()
        perm = permissions.check_dir(path)
        result[key] = {"path": path, "readable": perm.readable, "writable": perm.writable}
    return result


@router.get("/{root}")
async def browse(root: str, path: str = Query(default="")):
    """List immediate contents of <root>/path: directories and video files."""
    root_path = _root_path(root)
    perm = permissions.check_dir(root_path)
    if not perm.ok:
        raise HTTPException(
            status_code=503,
            detail=f"{root} folder is not accessible (readable={perm.readable}, writable={perm.writable})",
        )

    target = _safe_join(root_path, path)
    if not os.path.isdir(target):
        raise HTTPException(status_code=404, detail="folder not found")

    dirs, files = [], []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        rel = os.path.relpath(full, root_path)
        if os.path.isdir(full):
            dirs.append({"name": name, "path": rel})
        elif is_video(name):
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            files.append({"name": name, "path": full, "size": size})
    return {"cwd": path, "dirs": dirs, "files": files}
