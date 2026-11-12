"""Make phone photos look like ESP32-CAM images, to add them to the training dataset.

Put the phone photos (.jpg/.png) in storage/phone, then run inside the backend container:
    docker compose run --rm --no-deps web python -m scripts.degrade_phone_photos

Each photo is cropped to 4:3, scaled down to the ESP32-CAM frame size (800x600, FRAMESIZE_SVGA
in the firmware), slightly blurred and noised like the OV2640 sensor, and saved as a heavily
compressed JPEG in storage/phone_esp32/<name>.jpg. The originals are not changed.
"""
from pathlib import Path

import cv2
import numpy as np

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
PHONE_DIR = STORAGE_DIR / "phone"
OUTPUT_DIR = STORAGE_DIR / "phone_esp32"

# The camera's frame size, landscape. Portrait photos get the same size rotated (600x800)
FRAME_WIDTH, FRAME_HEIGHT = 800, 600
# OpenCV's 0-100 scale, roughly what the camera's jpeg_quality = 12 produces
JPEG_QUALITY = 60
# Standard deviation of the sensor noise, in 0-255 pixel values
NOISE_SIGMA = 6


def crop_to_4_3(image: np.ndarray) -> np.ndarray:
    """Center-crop to 4:3 (or 3:4 for a portrait photo), the aspect ratio of the camera."""
    height, width = image.shape[:2]
    long_side, short_side = max(width, height), min(width, height)
    target_long = min(long_side, short_side * 4 // 3)
    target_short = target_long * 3 // 4
    target_w, target_h = (target_long, target_short) if width >= height else (target_short, target_long)
    x = (width - target_w) // 2
    y = (height - target_h) // 2
    return image[y:y + target_h, x:x + target_w]


def degrade(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    image = crop_to_4_3(image)
    size = (FRAME_WIDTH, FRAME_HEIGHT) if image.shape[1] >= image.shape[0] else (FRAME_HEIGHT, FRAME_WIDTH)
    image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    # The OV2640 lens is soft compared to a phone camera
    image = cv2.GaussianBlur(image, (3, 3), 0)
    noise = rng.normal(0, NOISE_SIGMA, image.shape)
    return np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def main() -> None:
    photos = sorted(path for path in PHONE_DIR.glob("*") if path.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if not photos:
        print(f"No .jpg or .png photos in {PHONE_DIR}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng()
    for path in photos:
        # imread applies the EXIF orientation, so photos taken in portrait stay upright
        image = cv2.imread(str(path))
        if image is None:
            print(f"SKIPPED   {path.name}: not a readable image")
            continue
        output = OUTPUT_DIR / f"{path.stem}.jpg"
        cv2.imwrite(str(output), degrade(image, rng), [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        print(f"saved     {OUTPUT_DIR.name}/{output.name}")

    print(f"\nOpen backend/storage/{OUTPUT_DIR.name} to check the results")


if __name__ == "__main__":
    main()
