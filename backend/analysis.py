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

from database import AsyncSessionLocal
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


async def sync_event(event: ReadyEvent) -> None:
    """Merge the analyzed images of a door event, apply the changes to the inventory and record them."""
    async with AsyncSessionLocal() as db:
        snapshot = await build_snapshot(db, event.event_id)
        changes = diff_inventory(snapshot, await current_quantities(db))
        event_time = datetime.utcnow()
        await apply_quantities(db, snapshot, changes, event_time)
        removed = await apply_removals(db, changes, event_time)
        db.add(EventAnalysis(
            event_id=event.event_id,
            camera_ids=sorted(event.camera_ids),
            timed_out=event.timed_out,
            snapshot=[{**asdict(item), "camera_ids": sorted(item.camera_ids)} for item in snapshot.values()],
            changes=[_recorded_change(change, removed) for change in changes if change.change != ChangeType.UNCHANGED],
            created_at=event_time,
        ))
        await db.commit()
    print(f"Event {event.event_id}: inventory updated from cameras {sorted(event.camera_ids)}", flush=True)


collector = EventCollector(sync_event)


def _timed_analyze(path: str, camera_id: int) -> tuple[list, int]:
    # Timed inside the analysis thread, so the time an image waited in the queue isn't included
    start = time.perf_counter()
    detections = analyze_image(path, camera_id)
    return detections, round((time.perf_counter() - start) * 1000)


async def analyze_upload(analysis_id: int, path: str) -> None:
    """Analyze one uploaded image and record the result in its ImageAnalysis row."""
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
            # A black or corrupted image: the event is still merged from the other cameras
            analysis.error = str(error)
            analysis.status = AnalysisStatus.FAILED.value
        await db.commit()
        event_id, camera_id = analysis.event_id, analysis.camera_id

    await collector.image_analyzed(event_id, camera_id)
