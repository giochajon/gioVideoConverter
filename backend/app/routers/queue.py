from fastapi import APIRouter, HTTPException

from ..models import EnqueueRequest
from ..services import queue_manager

router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.post("/enqueue")
async def enqueue(req: EnqueueRequest):
    try:
        job_ids = await queue_manager.enqueue_interactive(req.paths)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"job_ids": job_ids}


@router.get("/status")
async def status():
    return await queue_manager.get_status()


@router.post("/stop-all")
async def stop_all():
    await queue_manager.stop_all()
    return {"ok": True}


@router.post("/resume")
async def resume():
    await queue_manager.resume()
    return {"ok": True}
