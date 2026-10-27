from dataclasses import dataclass

import numpy as np


@dataclass
class Detection:
    label: str
    confidence: float
    # Bounding box in pixels: top-left (x1, y1), bottom-right (x2, y2)
    box: tuple[int, int, int, int]


def detect_products(image: np.ndarray) -> list[Detection]:
    """Find the products in a preprocessed image using YOLO."""
    raise NotImplementedError
