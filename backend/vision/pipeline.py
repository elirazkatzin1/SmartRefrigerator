from pathlib import Path

from vision.calibration import undistort
from vision.detector import Detection, detect
from vision.preprocess import load_image


def analyze_image(path: str | Path, camera_id: int | None = None) -> list[Detection]:
    """Run the pipeline on one uploaded image: load and validate -> correct the lens -> detect.

    Detection runs on the image before preprocess.enhance: the detector is trained on raw images, and
    a model trained on enhanced images did worse (docs/model_evaluation.md). Reading brands or dates
    with OCR is left out for now, since it could not read them from fridge images.

    Raises ImageRejectedError for black or corrupted images.
    """
    image = undistort(load_image(path), camera_id)
    return detect(image)
