"""Runs after an image upload: analyze the image, and once a door event is complete, update the inventory.

    upload_image -> analyze_upload (background) -> ImageAnalysis row -> EventCollector
                 -> sync_event (when all cameras are in, or after the timeout) -> Inventory
"""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import update

from database import AsyncSessionLocal
from log import log
from inventory.diff import ChangeType, ProductChange, current_quantities, diff_inventory
from inventory.event_collector import EventCollector, ReadyEvent
from inventory.merge import build_snapshot
from inventory.update import apply_quantities, apply_removals
from models import AnalysisStatus, EventAnalysis, ImageAnalysis
from vision.errors import ImageRejectedError
from vision.pipeline import analyze_image

logger = logging.getLogger(__name__)

# The image analysis (YOLO inference) is CPU-bound, so it runs off the event loop to keep the server
# answering other requests. It runs in one dedicated thread, one image at a time: an Ultralytics model
# is not safe to use from several threads at once, and the cameras of a door event upload together.
# Images wait in this executor's queue; at ~0.2 s each, a 5-camera event takes about a second
_analysis_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")


def _recorded_change(change: ProductChange, removed: set[str]) -> dict:
    # A product the cameras didn't see is only removed after the tolerance, so the record tells
    # "removed" (taken out of the inventory now) apart from "missing" (kept for now)
    kind = change.change.value
    if change.change == ChangeType.REMOVED and change.product_name not in removed:
        kind = "missing"
    return {"product_name": change.product_name, "change": kind,
            "old_quantity": change.old_quantity, "new_quantity": change.new_quantity}


def _describe(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


async def sync_event(event: ReadyEvent) -> None:
    """Merge the analyzed images of a door event, apply the changes to the inventory and record them.

    If any step fails, nothing of the inventory update is committed (the session rolls back), so the
    existing inventory doesn't change, and the event is recorded with the error instead.
    """
    try:
        await _update_inventory(event)
    except Exception as error:
        logger.exception("inventory update failed, inventory left unchanged",
                         extra={"fields": {"event_id": event.event_id, "error": _describe(error)}})
        try:
            async with AsyncSessionLocal() as db:
                db.add(EventAnalysis(event_id=event.event_id, camera_ids=sorted(event.camera_ids),
                                     timed_out=event.timed_out, snapshot=[], changes=[], error=_describe(error)))
                await db.commit()
        except Exception:
            # E.g. the database itself is down: the log above is all that can be done
            logger.exception("could not record the failed event", extra={"fields": {"event_id": event.event_id}})


async def _update_inventory(event: ReadyEvent) -> None:
    async with AsyncSessionLocal() as db:
        snapshot = await build_snapshot(db, event.event_id)
        changes = diff_inventory(snapshot, await current_quantities(db))
        event_time = datetime.utcnow()
        await apply_quantities(db, snapshot, changes, event_time)
        removed = await apply_removals(db, changes, event_time)
        recorded = [_recorded_change(change, removed) for change in changes if change.change != ChangeType.UNCHANGED]
        db.add(EventAnalysis(
            event_id=event.event_id,
            camera_ids=sorted(event.camera_ids),
            timed_out=event.timed_out,
            snapshot=[{**asdict(item), "camera_ids": sorted(item.camera_ids)} for item in snapshot.values()],
            changes=recorded,
            created_at=event_time,
        ))
        await db.commit()

    # One field per kind of change, listing its products, e.g. added=carrot,milk quantity_changed=lemon:2->1
    by_kind = {}
    for change in recorded:
        entry = change["product_name"]
        if change["change"] == "quantity_changed":
            entry += f":{change['old_quantity']}->{change['new_quantity']}"
        by_kind.setdefault(change["change"], []).append(entry)
    log(logger, "inventory updated", event_id=event.event_id, cameras=sorted(event.camera_ids),
        timed_out=event.timed_out, products=len(snapshot), **by_kind)


collector = EventCollector(sync_event)


def _timed_analyze(path: str, camera_id: int) -> tuple[list, int]:
    # Timed inside the analysis thread, so the time an image waited in the queue isn't included
    start = time.perf_counter()
    detections = analyze_image(path, camera_id)
    return detections, round((time.perf_counter() - start) * 1000)


async def analyze_upload(analysis_id: int, path: str) -> None:
    """Analyze one uploaded image and record the result in its ImageAnalysis row.

    Runs as a background task, so it never raises: a failed analysis is marked failed with the error,
    and the door event goes on with the other cameras.
    """
    try:
        event_id, camera_id = await _analyze(analysis_id, path)
    except Exception:
        # The row itself couldn't be read or saved (e.g. the database is down). The event is still
        # merged from the other cameras after the timeout
        logger.exception("image analysis could not be run or recorded", extra={"fields": {"analysis_id": analysis_id}})
        return
    await collector.image_analyzed(event_id, camera_id)


async def _analyze(analysis_id: int, path: str) -> tuple[str, int]:
    async with AsyncSessionLocal() as db:
        analysis = await db.get(ImageAnalysis, analysis_id)
        analysis.status = AnalysisStatus.PROCESSING.value
        await db.commit()

        try:
            detections, analysis.processing_time_ms = await asyncio.get_running_loop().run_in_executor(
                _analysis_executor, _timed_analyze, path, analysis.camera_id
            )
            analysis.detections = [asdict(detection) for detection in detections]
            analysis.status = AnalysisStatus.DONE.value
        except ImageRejectedError as error:
            # A black or corrupted image (already logged by preprocess)
            analysis.error = str(error)
            analysis.status = AnalysisStatus.FAILED.value
        except Exception as error:
            # Anything else, e.g. no trained model or an OpenCV error. The traceback goes to the log
            logger.exception("image analysis crashed", extra={"fields": {"analysis_id": analysis_id}})
            analysis.error = _describe(error)
            analysis.status = AnalysisStatus.FAILED.value
        await db.commit()

        log(logger, "image analyzed", logging.INFO if analysis.status == AnalysisStatus.DONE.value else logging.WARNING,
            event_id=analysis.event_id, camera_id=analysis.camera_id, status=analysis.status,
            processing_ms=analysis.processing_time_ms if analysis.processing_time_ms is not None else "-",
            detections=len(analysis.detections or []),
            **({"error": analysis.error} if analysis.error else {}))
        return analysis.event_id, analysis.camera_id


async def fail_interrupted_analyses() -> None:
    """Mark analyses left pending or processing by a server restart as failed, so none stay stuck.

    Called on startup, before new images arrive.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(ImageAnalysis)
            .where(ImageAnalysis.status.in_([AnalysisStatus.PENDING.value, AnalysisStatus.PROCESSING.value]))
            .values(status=AnalysisStatus.FAILED.value, error="The server restarted before the analysis finished")
        )
        await db.commit()
    if result.rowcount:
        log(logger, "analyses interrupted by a restart marked failed", logging.WARNING, count=result.rowcount)
