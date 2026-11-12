"""Product detection with the YOLO model trained by scripts/train_detector.py."""
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from ultralytics import YOLO

from vision.products import PRODUCTS_BY_NAME, Category

logger = logging.getLogger(__name__)

# Written by scripts/train_detector.py. Not in git (storage/ is ignored)
DETECTOR_WEIGHTS = Path(__file__).resolve().parent.parent / "storage" / "models" / "detector.pt"
# Detections below this confidence are dropped. Can be set with DETECTION_CONFIDENCE (0-1)
DEFAULT_CONFIDENCE = float(os.getenv("DETECTION_CONFIDENCE", "0.5"))
# NMS: of two boxes overlapping by more than this IoU, only the more confident one is kept.
# Ultralytics' default of 0.7 kept duplicate boxes of one product at 0.6-0.65 IoU
NMS_IOU = float(os.getenv("DETECTION_NMS_IOU", "0.5"))
# NMS across classes too: the model sometimes gives one product two classes in the same place
# (mustard + pesto at 0.81 IoU, cooking_cream + hummus at 0.97), which per-class NMS keeps both of
NMS_ACROSS_CLASSES = True


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
def load_model() -> YOLO:
    """Load the weights once and keep them. Called by the server on startup (main.lifespan).

    Also runs one prediction on a blank image: the first prediction sets up the model and takes
    several seconds, which would otherwise delay the first real image.
    """
    if not DETECTOR_WEIGHTS.exists():
        raise FileNotFoundError(
            f"No trained model at {DETECTOR_WEIGHTS}. Train one with `python -m scripts.train_detector`"
        )
    logger.info("Loading detector weights from %s", DETECTOR_WEIGHTS)
    model = YOLO(str(DETECTOR_WEIGHTS))
    model.predict(np.zeros((480, 640, 3), dtype=np.uint8), verbose=False)
    return model


def detect(image: np.ndarray, confidence: float = DEFAULT_CONFIDENCE) -> list[Detection]:
    """Find the products in a BGR image (as loaded by OpenCV) with the trained YOLO model.

    Detections below `confidence` are dropped, and duplicate boxes are removed with NMS.
    The server loads the model on startup; outside the server it is loaded on the first call.
    """
    model = load_model()
    result = model.predict(image, conf=confidence, iou=NMS_IOU, agnostic_nms=NMS_ACROSS_CLASSES, verbose=False)[0]

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
