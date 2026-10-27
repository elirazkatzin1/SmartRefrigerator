import numpy as np


def read_brand(image: np.ndarray) -> str | None:
    """Read the brand name (Hebrew or English) from a cropped product image with Tesseract.

    Returns None when no readable text is found.
    """
    raise NotImplementedError
