"""Product detection with the YOLO model trained by scripts/train_detector.py."""
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from ultralytics import YOLO

from vision.products import PRODUCTS_BY_NAME, Category

logger = logging.getLogger(__name__)

# Written by scripts/train_detector.py. Not in git (storage/ is ignored)
DETECTOR_WEIGHTS = Path(__file__).resolve().parent.parent / "storage" / "models" / "detector.pt"


@dataclass
class Detection:
    # Product name from vision/products.py, e.g. "milk"
    class_name: str
    # None only if the model knows a class that was later removed from products.py
    category: Category | None
    confidence: float
    # Bounding box in pixels: top-left (x1, y1), bottom-right (x2, y2)
    bbox: tuple[int, int, int, int]


@lru_cache(maxsize=1)
def _load_model() -> YOLO:
    if not DETECTOR_WEIGHTS.exists():
        raise FileNotFoundError(
            f"No trained model at {DETECTOR_WEIGHTS}. Train one with `python -m scripts.train_detector`"
        )
    logger.info("Loading detector weights from %s", DETECTOR_WEIGHTS)
    return YOLO(str(DETECTOR_WEIGHTS))


def detect(image: np.ndarray) -> list[Detection]:
    """Find the products in a BGR image (as loaded by OpenCV) with the trained YOLO model.

    The model is loaded on the first call and reused afterwards.
    """
    model = _load_model()
    result = model.predict(image, verbose=False)[0]

    detections = []
    for class_id, confidence, box in zip(result.boxes.cls.tolist(), result.boxes.conf.tolist(),
                                         result.boxes.xyxy.tolist()):
        class_name = model.names[int(class_id)]
        product = PRODUCTS_BY_NAME.get(class_name)
        x1, y1, x2, y2 = (round(value) for value in box)
        detections.append(Detection(
            class_name=class_name,
            category=product.category if product else None,
            confidence=confidence,
            bbox=(x1, y1, x2, y2),
        ))
    return detections
