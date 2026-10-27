from dataclasses import dataclass
from pathlib import Path

from vision.detector import Detection


@dataclass
class ProductResult:
    detection: Detection
    brand: str | None


def analyze_image(path: str | Path) -> list[ProductResult]:
    """Run the full pipeline on one uploaded image: preprocess -> detect -> crop -> OCR.

    Black or corrupted images are logged and return an empty list instead of raising.
    """
    raise NotImplementedError
