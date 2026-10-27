import logging
from pathlib import Path

import cv2
import numpy as np

from vision.errors import ImageRejectedError

logger = logging.getLogger(__name__)

JPEG_START = b"\xff\xd8"
JPEG_END = b"\xff\xd9"
# ESP32-CAM frames are 640x480 or 800x600; anything much smaller is not a real frame
MIN_WIDTH = 160
MIN_HEIGHT = 120
# Grayscale thresholds (0-255), calibrated on real ESP32-CAM images: normal frames have
# mean brightness ~125-245 and standard deviation (contrast) 20-75
BLACK_MEAN_THRESHOLD = 15
# A frame with almost no variation is one solid color: black, or white when the flash
# blows out a close object (measured: mean 254, std 0.1)
BLANK_STD_THRESHOLD = 3


def _reject(path: Path, reason: str) -> None:
    logger.warning("Rejected image %s: %s", path.name, reason)
    raise ImageRejectedError(f"{path.name}: {reason}")


def load_image(path: str | Path) -> np.ndarray:
    """Read an image file and return it as a BGR array, or raise ImageRejectedError.

    Every rejection is logged with its reason.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        _reject(path, f"cannot read file ({error.strerror})")

    if not data:
        _reject(path, "empty file")
    # An upload cut off mid-transfer leaves a JPEG without its end marker. OpenCV would still
    # decode it, with the missing part filled in gray, so this has to be checked explicitly
    if data.startswith(JPEG_START) and not data.rstrip(b"\x00").endswith(JPEG_END):
        _reject(path, "truncated JPEG (missing end marker)")

    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        _reject(path, "not a decodable image")

    validate_image(image, path)
    return image


def validate_image(image: np.ndarray, path: Path) -> None:
    """Reject frames that are too small, black, or a single solid color."""
    height, width = image.shape[:2]
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        _reject(path, f"too small ({width}x{height})")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean, std = (float(value[0][0]) for value in cv2.meanStdDev(gray))
    if mean < BLACK_MEAN_THRESHOLD:
        _reject(path, f"black image (mean brightness {mean:.1f})")
    if std < BLANK_STD_THRESHOLD:
        _reject(path, f"blank image, single solid color (mean {mean:.1f}, contrast {std:.1f})")


def preprocess(path: str | Path) -> np.ndarray:
    """Load an ESP32-CAM image and return it cleaned and enhanced for detection.

    Raises ImageRejectedError for black or corrupted images.
    """
    image = load_image(path)
    # Enhancement (lighting / contrast correction) is the next step of this story
    return image
