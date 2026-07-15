import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .routers import batch, browse, queue, settings as settings_router
from .services import permissions, queue_manager
from .services.scheduler import start_scheduler

logger = logging.getLogger(__name__)

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "static")


def _check_folder_permissions() -> None:
    for name, path in (
        ("MOVIE_DIR", settings.movie_dir),
        ("SERIES_DIR", settings.series_dir),
        ("INTERACTIVE_DIR", settings.interactive_dir),
    ):
        perm = permissions.check_dir(path)
        if not perm.ok:
            logger.warning(
                "%s (%s) is missing required access: exists=%s readable=%s writable=%s",
                name, path, perm.exists, perm.readable, perm.writable,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_folder_permissions()
    queue_manager.start_worker()
    scheduler = await start_scheduler()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="gioVideoConvert", lifespan=lifespan)

app.include_router(browse.router)
app.include_router(queue.router)
app.include_router(settings_router.router)
app.include_router(batch.router)

if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # React Router uses real browser paths (BrowserRouter), so a refresh on
        # e.g. /batch is a real GET to the server - hand back index.html and
        # let the client-side router resolve it. Unmatched /api/* requests
        # should stay real 404s rather than being masked as an HTML 200.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
