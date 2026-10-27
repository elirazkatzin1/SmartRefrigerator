from pathlib import Path

import numpy as np


def preprocess(path: str | Path) -> np.ndarray:
    """Load an ESP32-CAM image and return it cleaned and enhanced for detection.

    Raises ImageRejectedError for black or corrupted images.
    """
    raise NotImplementedError
