"""Save before/after images of the preprocessing step, to inspect what it does.

Run inside the backend container:
    docker compose run --rm --no-deps web python -m scripts.preview_preprocess [count]

For each of the newest `count` camera images (default 10) it writes
storage/preview/<name> with the original on the left and the preprocessed image on the right.
Rejected images are listed with the reason.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

from vision.errors import ImageRejectedError
from vision.preprocess import enhance, load_image

IMAGES_DIR = Path(__file__).resolve().parent.parent / "storage" / "images"
PREVIEW_DIR = IMAGES_DIR.parent / "preview"


def main(count: int) -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    # File names start with the upload time, so sorting by name puts the newest last
    images = sorted(path for path in IMAGES_DIR.iterdir() if path.suffix in (".jpg", ".png"))[-count:]
    if not images:
        print(f"No .jpg or .png images in {IMAGES_DIR}")
        return

    for path in images:
        try:
            original = load_image(path)
        except ImageRejectedError as error:
            print(f"REJECTED  {error}")
            continue
        side_by_side = np.hstack([original, enhance(original)])
        cv2.imwrite(str(PREVIEW_DIR / path.name), side_by_side)
        print(f"saved     {PREVIEW_DIR.name}/{path.name}")

    print(f"\nOpen backend/storage/preview to compare (left = original, right = preprocessed)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
