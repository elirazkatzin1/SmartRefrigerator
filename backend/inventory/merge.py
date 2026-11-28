"""Merge the detections of all cameras from one door-close event into one snapshot of the fridge.

Each camera sees its own part of the fridge, so the counts of different cameras are added up: a milk
on the upper shelf and a milk on the lower shelf are two milks. Where two cameras' views overlap
(inventory.camera_layout), a product can be seen by both, so inside that strip only the higher count
of the two cameras is taken: the mustard seen by both upper-shelf cameras is one mustard.
"""
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.camera_layout import CAMERA_OVERLAPS, FRAME_WIDTH, Overlap
from models import AnalysisStatus, ImageAnalysis
from vision.products import PRODUCTS_BY_NAME


@dataclass
class SnapshotItem:
    product_name: str
    category: str | None
    quantity: int
    # The highest confidence of any detection of this product, in any camera
    confidence: float
    # The cameras that saw it
    camera_ids: set[int]


def _overlap_of(camera_id: int, detection: dict, overlaps: tuple[Overlap, ...]) -> int | None:
    """The index of the overlap whose strip this detection is in, or None if only this camera sees it."""
    x1, _, x2, _ = detection["bbox"]
    center = (x1 + x2) / 2 / FRAME_WIDTH
    for index, overlap in enumerate(overlaps):
        zone = overlap.zones.get(camera_id)
        if zone and zone[0] <= center <= zone[1]:
            return index
    return None


def merge_detections(detections_by_camera: dict[int, list[dict]],
                     overlaps: tuple[Overlap, ...] = CAMERA_OVERLAPS) -> dict[str, SnapshotItem]:
    """Merge per-camera detections (ImageAnalysis.detections) into one item per product.

    A product's quantity is the sum of what each camera saw outside the overlap strips, plus, for
    each overlap, the higher of the two cameras' counts inside it.
    """
    snapshot: dict[str, SnapshotItem] = {}
    only_here = Counter()
    # {(overlap index, camera_id): Counter of products in that camera's part of the strip}
    in_overlap: dict[tuple[int, int], Counter] = {}
    for camera_id, detections in detections_by_camera.items():
        for detection in detections:
            name = detection["class_name"]
            overlap = _overlap_of(camera_id, detection, overlaps)
            if overlap is None:
                only_here[name] += 1
            else:
                in_overlap.setdefault((overlap, camera_id), Counter())[name] += 1

            item = snapshot.get(name)
            if item is None:
                product = PRODUCTS_BY_NAME.get(name)
                item = snapshot[name] = SnapshotItem(
                    product_name=name,
                    category=product.category.value if product else None,
                    quantity=0,
                    confidence=0.0,
                    camera_ids=set(),
                )
            item.confidence = max(item.confidence, detection["confidence"])
            item.camera_ids.add(camera_id)

    for name, item in snapshot.items():
        item.quantity = only_here[name] + sum(
            max((counts[name] for (index, _), counts in in_overlap.items() if index == overlap), default=0)
            for overlap in range(len(overlaps))
        )
    return snapshot


async def build_snapshot(db: AsyncSession, event_id: str) -> dict[str, SnapshotItem]:
    """The merged snapshot of one door-close event, from its successfully analyzed images.

    Failed images (black, corrupted) are left out: they say nothing about what is in the fridge.
    """
    result = await db.execute(
        select(ImageAnalysis).where(
            ImageAnalysis.event_id == event_id,
            ImageAnalysis.status == AnalysisStatus.DONE.value,
        )
    )
    return merge_detections({analysis.camera_id: analysis.detections or [] for analysis in result.scalars()})
