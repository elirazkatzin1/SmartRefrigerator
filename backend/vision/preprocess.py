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

# Lighting normalization: frames whose average brightness is outside this range are
# gamma-corrected toward TARGET_MEAN_BRIGHTNESS before local contrast is equalized
DARK_MEAN_THRESHOLD = 90
BRIGHT_MEAN_THRESHOLD = 170
TARGET_MEAN_BRIGHTNESS = 128
# Limits how strongly gamma may brighten (<1) or darken (>1), so noise and blown-out
# areas are not exaggerated
MIN_GAMMA = 0.4
MAX_GAMMA = 2.5
# CLAHE (adaptive histogram equalization): evens out the flash hot-spot in the middle and the
# dark edges. A higher clip limit gives more contrast but also amplifies sensor noise
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID = (8, 8)


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


def _gamma_correct(lightness: np.ndarray, mean: float) -> np.ndarray:
    # Solves (mean/255) ** gamma == target/255, so the average brightness moves to the target
    gamma = np.log(TARGET_MEAN_BRIGHTNESS / 255) / np.log(mean / 255)
    gamma = float(np.clip(gamma, MIN_GAMMA, MAX_GAMMA))
    lookup = ((np.arange(256) / 255) ** gamma * 255).round().astype(np.uint8)
    return cv2.LUT(lightness, lookup)


def normalize_lighting(image: np.ndarray) -> np.ndarray:
    """Even out the uneven, flash-lit lighting of a fridge frame.

    Works only on the lightness channel (LAB color space), so product colors are kept:
    1. Global: frames that are too dark or too bright are gamma-corrected toward mid-gray.
    2. Local: CLAHE equalizes contrast per region, fixing the bright flash spot in the
       center and the dark corners.
    """
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, a, b = cv2.split(lab)

    mean = float(lightness.mean())
    if mean < DARK_MEAN_THRESHOLD or mean > BRIGHT_MEAN_THRESHOLD:
        lightness = _gamma_correct(lightness, mean)

    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID)
    lightness = clahe.apply(lightness)

    return cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2BGR)


def preprocess(path: str | Path) -> np.ndarray:
    """Load an ESP32-CAM image and return it cleaned and enhanced for detection.

    Raises ImageRejectedError for black or corrupted images.
    """
    image = load_image(path)
    return normalize_lighting(image)
