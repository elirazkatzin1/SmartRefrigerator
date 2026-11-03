"""Calibrate one ESP32-CAM's lens from checkerboard photos.

1. Print a checkerboard with 10x7 squares (9x6 inner corners) and tape it to something flat.
2. Take 10-20 photos of it with the camera being calibrated, at the resolution it uses
   in the fridge. Vary the angle and position, and include photos with the board near the
   edges and corners of the frame, where the distortion is strongest.
3. Copy the photos to storage/calibration/camera_<id>/ and run inside the backend container:
       docker compose run --rm --no-deps web python -m scripts.calibrate_camera <camera_id> [--force]

If the distortion is noticeable, the calibration is saved to calibration/camera_<id>.json and
preprocess() corrects that camera's images from then on. Otherwise nothing is saved, unless
--force is given. Either way, a before/after image is written to storage/calibration/.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

from vision.calibration import NOTICEABLE_DISTORTION_PX, calibrate, calibration_path

PHOTOS_ROOT = Path(__file__).resolve().parent.parent / "storage" / "calibration"


def main(camera_id: int, force: bool) -> None:
    photos_dir = PHOTOS_ROOT / f"camera_{camera_id}"
    paths = sorted(path for path in photos_dir.glob("*") if path.suffix.lower() in (".jpg", ".png"))
    if not paths:
        print(f"No .jpg or .png photos in {photos_dir}")
        return

    images = [cv2.imread(str(path)) for path in paths]
    try:
        calibration, used = calibrate(images)
    except ValueError as error:
        print(f"Calibration failed: {error}")
        return

    displacement = calibration.max_displacement()
    print(f"Checkerboard found in {used} of {len(paths)} photos")
    # Below ~0.5 px the model fits the photos well; above ~1 px some photos are blurry or misdetected
    print(f"Reprojection error: {calibration.reprojection_error:.2f} px")
    print(f"Max distortion at the frame edges: {displacement:.1f} px")

    # Before/after of the first photo, for a visual check
    undistorted = cv2.undistort(images[0], calibration.camera_matrix, calibration.dist_coeffs)
    comparison_path = PHOTOS_ROOT / f"camera_{camera_id}_undistorted.jpg"
    cv2.imwrite(str(comparison_path), np.hstack([images[0], undistorted]))
    print(f"Before/after saved to storage/calibration/{comparison_path.name}")

    if displacement < NOTICEABLE_DISTORTION_PX and not force:
        print(f"\nDistortion is not noticeable (< {NOTICEABLE_DISTORTION_PX} px), calibration NOT saved.")
        print("Run with --force to save it anyway.")
        if calibration_path(camera_id).exists():
            print(f"Note: an older {calibration_path(camera_id).name} exists and is still used.")
        return

    path = calibration.save(camera_id)
    print(f"\nSaved {path.parent.name}/{path.name}, camera {camera_id} images will be undistorted")


if __name__ == "__main__":
    args = [arg for arg in sys.argv[1:] if arg != "--force"]
    if len(args) != 1 or not args[0].isdigit():
        print("Usage: python -m scripts.calibrate_camera <camera_id> [--force]")
        sys.exit(1)
    main(int(args[0]), "--force" in sys.argv)
