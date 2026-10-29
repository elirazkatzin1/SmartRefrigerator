"""Lens distortion correction for the ESP32-CAMs.

The wide-angle OV2640 lenses bend straight lines (shelf edges, product sides) near the
corners of the frame. Each camera is calibrated once from checkerboard photos with
scripts/calibrate_camera.py, which saves calibration/camera_<id>.json. Cameras without a
saved calibration (because their distortion was not noticeable) are left uncorrected.
"""
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

CALIBRATION_DIR = Path(__file__).resolve().parent.parent / "calibration"
# Inner corners of the printed checkerboard (squares per row - 1, squares per column - 1)
CHECKERBOARD_SIZE = (9, 6)
# Distortion is "noticeable" when correcting it moves some pixel by more than this.
# Below ~2 px the bending is not visible and correcting it only costs time and resolution
NOTICEABLE_DISTORTION_PX = 2.0


@dataclass
class Calibration:
    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray
    # (width, height) of the frames the calibration was made from
    image_size: tuple[int, int]
    # Average error (pixels) between the detected and the model's checkerboard corners
    reprojection_error: float

    def max_displacement(self) -> float:
        """How far (in pixels) the lens moves the most-distorted point of the frame."""
        width, height = self.image_size
        # Points along the frame border, where distortion is strongest
        xs, ys = np.linspace(0, width - 1, 50), np.linspace(0, height - 1, 50)
        border = np.array(
            [(x, 0) for x in xs] + [(x, height - 1) for x in xs]
            + [(0, y) for y in ys] + [(width - 1, y) for y in ys],
            dtype=np.float64,
        )
        # Apply the lens model forward (where would the lens put each point). Going the other way
        # (cv2.undistortPoints) is iterative and diverges at the corners of strongly bent frames
        focal = np.array([self.camera_matrix[0, 0], self.camera_matrix[1, 1]])
        center = np.array([self.camera_matrix[0, 2], self.camera_matrix[1, 2]])
        normalized = np.column_stack([(border - center) / focal, np.ones(len(border))])
        distorted, _ = cv2.projectPoints(normalized, np.zeros(3), np.zeros(3), self.camera_matrix, self.dist_coeffs)
        return float(np.linalg.norm(distorted.reshape(-1, 2) - border, axis=1).max())

    def save(self, camera_id: int) -> Path:
        CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
        path = calibration_path(camera_id)
        path.write_text(json.dumps({
            "camera_matrix": self.camera_matrix.tolist(),
            "dist_coeffs": self.dist_coeffs.ravel().tolist(),
            "image_size": list(self.image_size),
            "reprojection_error": self.reprojection_error,
        }, indent=2))
        return path

    @classmethod
    def load(cls, path: Path) -> "Calibration":
        data = json.loads(path.read_text())
        return cls(
            camera_matrix=np.array(data["camera_matrix"], dtype=np.float64),
            dist_coeffs=np.array(data["dist_coeffs"], dtype=np.float64),
            image_size=tuple(data["image_size"]),
            reprojection_error=data["reprojection_error"],
        )


def calibration_path(camera_id: int) -> Path:
    return CALIBRATION_DIR / f"camera_{camera_id}.json"


def calibrate(images: list[np.ndarray]) -> tuple[Calibration, int]:
    """Compute a camera's calibration from checkerboard photos.

    Returns the calibration and how many of the photos had a detectable checkerboard.
    Raises ValueError if too few photos could be used.
    """
    columns, rows = CHECKERBOARD_SIZE
    # The board's corners in its own plane. The square size does not matter for undistortion
    board_points = np.zeros((rows * columns, 3), np.float32)
    board_points[:, :2] = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2)

    object_points, image_points = [], []
    image_size = None
    for image in images:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        size = (gray.shape[1], gray.shape[0])
        if image_size is None:
            image_size = size
        elif size != image_size:
            raise ValueError(f"All photos must have the same resolution ({image_size} vs {size})")

        found, corners = cv2.findChessboardCorners(gray, CHECKERBOARD_SIZE)
        if not found:
            continue
        corners = cv2.cornerSubPix(
            gray, corners, (11, 11), (-1, -1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
        )
        object_points.append(board_points)
        image_points.append(corners)

    # Fewer photos than this give an unreliable model, especially near the frame corners
    if len(image_points) < 5:
        raise ValueError(
            f"Checkerboard found in only {len(image_points)} of {len(images)} photos, need at least 5"
        )

    # FIX_K3: two radial terms are enough for these lenses. The third one overfits the photos and
    # explodes toward the frame corners, where the checkerboard rarely reaches
    error, camera_matrix, dist_coeffs, _, _ = cv2.calibrateCamera(
        object_points, image_points, image_size, None, None, flags=cv2.CALIB_FIX_K3
    )
    return Calibration(camera_matrix, dist_coeffs.ravel(), image_size, float(error)), len(image_points)


@lru_cache(maxsize=None)
def _undistort_maps(camera_id: int) -> tuple[np.ndarray, np.ndarray, tuple[int, int]] | None:
    """Load a camera's calibration and build its pixel remapping, once per camera."""
    path = calibration_path(camera_id)
    if not path.exists():
        return None
    calibration = Calibration.load(path)
    # alpha=0: crop to the area that is valid after correction, so no black curved borders remain
    new_matrix, _ = cv2.getOptimalNewCameraMatrix(
        calibration.camera_matrix, calibration.dist_coeffs, calibration.image_size, 0
    )
    map_x, map_y = cv2.initUndistortRectifyMap(
        calibration.camera_matrix, calibration.dist_coeffs, None, new_matrix,
        calibration.image_size, cv2.CV_16SC2,
    )
    return map_x, map_y, calibration.image_size


def undistort(image: np.ndarray, camera_id: int | None) -> np.ndarray:
    """Correct lens distortion using the camera's saved calibration.

    Returns the image unchanged if the camera is unknown or has no calibration.
    """
    if camera_id is None:
        return image
    maps = _undistort_maps(camera_id)
    if maps is None:
        return image

    map_x, map_y, calibrated_size = maps
    size = (image.shape[1], image.shape[0])
    if size != calibrated_size:
        logger.warning(
            "Camera %s: frame is %sx%s but calibration was made at %sx%s, skipping undistortion",
            camera_id, *size, *calibrated_size,
        )
        return image
    return cv2.remap(image, map_x, map_y, cv2.INTER_LINEAR)
