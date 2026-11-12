"""Merge the detections of all cameras from one door-close event into one snapshot of the fridge.

Several cameras can see the same product, so adding up their detections would count it more than
once. Without knowing where the cameras' views overlap, this first version takes, for each product,
the highest count any single camera saw: two cameras that each see one milk give one milk.

The known limitation is the opposite case: two milks on different shelves, each seen by a different
camera, also give one milk. Fixing that needs the overlap zones between the cameras once they are
mounted in their final positions.
"""
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


def merge_detections(detections_by_camera: dict[int, list[dict]]) -> dict[str, SnapshotItem]:
    """Merge per-camera detections (ImageAnalysis.detections) into one item per product.

    The quantity of a product is the highest number of it that any single camera detected.
    """
    snapshot: dict[str, SnapshotItem] = {}
    for camera_id, detections in detections_by_camera.items():
        counts = Counter(detection["class_name"] for detection in detections)
        for detection in detections:
            name = detection["class_name"]
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
            item.quantity = max(item.quantity, counts[name])
            item.confidence = max(item.confidence, detection["confidence"])
            item.camera_ids.add(camera_id)
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
