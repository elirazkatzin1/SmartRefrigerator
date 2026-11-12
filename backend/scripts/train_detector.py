"""Fine-tune a small YOLO model on the fridge products dataset.

Run inside the backend container, after `scripts.split_dataset`:
    docker compose run --rm --no-deps web python -m scripts.train_detector [--epochs 100] [--model yolo11n.pt]

Starts from pretrained COCO weights and trains on storage/yolo/data.yaml. The run (weights, plots,
metrics) goes to storage/runs/<name>, then the best weights are evaluated on the test set and copied to
storage/models/detector.pt. The container has CPU-only PyTorch, which is fine for a few dozen images;
for a larger dataset run the same script on Google Colab with a GPU (--device 0).
"""
import argparse
import random
import shutil
from pathlib import Path

import cv2

from ultralytics import YOLO
from ultralytics.data import YOLODataset
from ultralytics.models.yolo.detect import DetectionTrainer

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
DATA_YAML = STORAGE_DIR / "yolo" / "data.yaml"
RUNS_DIR = STORAGE_DIR / "runs"
MODELS_DIR = STORAGE_DIR / "models"
DETECTOR_WEIGHTS = MODELS_DIR / "detector.pt"

# Lighting: the fridge light, the camera flash and the door closing change the brightness a lot
HSV_VALUE = 0.5
# Rotation in degrees: the cameras are mounted at slightly different angles
ROTATION_DEGREES = 10
BLUR_PROBABILITY = 0.3


class RandomBlur:
    """Blur some training images, like an out-of-focus or moving ESP32-CAM shot.

    Ultralytics only blurs through the albumentations package (not installed, and only 1% of images),
    so this is added to the training transforms. It runs on the {"img": ...} dict Ultralytics passes
    between transforms and doesn't move anything, so the boxes stay valid.
    """

    def __call__(self, labels: dict) -> dict:
        if random.random() < BLUR_PROBABILITY:
            kernel = random.choice((3, 5, 7))
            labels["img"] = cv2.GaussianBlur(labels["img"], (kernel, kernel), 0)
        return labels


class BlurYOLODataset(YOLODataset):
    def build_transforms(self, hyp=None):
        # Ultralytics calls this again when it turns off mosaic for the last epochs, so the blur
        # is part of every rebuild. It goes right before the last transform (Format), which turns
        # the image into a tensor. Validation images (augment=False) are not blurred
        transforms = super().build_transforms(hyp)
        if self.augment:
            transforms.insert(-1, RandomBlur())
        return transforms


class BlurDetectionTrainer(DetectionTrainer):
    def build_dataset(self, img_path, mode="train", batch=None):
        dataset = super().build_dataset(img_path, mode, batch)
        if mode == "train":
            # Before the data loader exists, so its worker processes get the blur too
            dataset.__class__ = BlurYOLODataset
            dataset.transforms = dataset.build_transforms(hyp=self.args)
        return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="yolo11n.pt", help="pretrained weights: yolo11n.pt or yolov8n.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="cpu", help="'cpu', or '0' for the first GPU (Colab)")
    parser.add_argument("--name", default="detector", help="run name under storage/runs")
    args = parser.parse_args()

    if not DATA_YAML.exists():
        raise SystemExit(f"No {DATA_YAML.relative_to(STORAGE_DIR.parent)}. Run `python -m scripts.split_dataset` first")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    # Keep the downloaded pretrained weights in storage/models, not in the backend source folder
    model = YOLO(str(MODELS_DIR / args.model))
    model.train(
        trainer=BlurDetectionTrainer,
        data=str(DATA_YAML),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        # Ultralytics updates the weights once per 64 images (nbs) by default, accumulating batches.
        # With a few dozen images that is a handful of updates per run and the model learns nothing,
        # so update after every batch instead
        nbs=args.batch,
        device=args.device,
        project=str(RUNS_DIR),
        name=args.name,
        hsv_v=HSV_VALUE,
        degrees=ROTATION_DEGREES,
    )

    best = Path(model.trainer.best)
    print(f"\nEvaluating {best.relative_to(STORAGE_DIR.parent)} on the test set")
    trained = YOLO(str(best))
    metrics = trained.val(data=str(DATA_YAML), split="test", device=args.device,
                          project=str(RUNS_DIR), name=f"{args.name}_test")
    print(f"test mAP50: {metrics.box.map50:.3f}   mAP50-95: {metrics.box.map:.3f}")

    shutil.copy2(best, DETECTOR_WEIGHTS)
    print(f"\nSaved the trained model to {DETECTOR_WEIGHTS.relative_to(STORAGE_DIR.parent)}")


if __name__ == "__main__":
    main()
