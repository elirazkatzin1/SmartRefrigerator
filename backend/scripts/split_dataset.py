"""Split the imported dataset into train/val/test (70/20/10) for YOLO training.

Run inside the backend container, after `scripts.annotations import`:
    docker compose run --rm --no-deps web python -m scripts.split_dataset

Reads storage/dataset/images and labels and writes storage/yolo/{train,val,test}/{images,labels}
plus storage/yolo/data.yaml. storage/yolo is rebuilt from scratch on every run, so run it again
after importing more images.

With --enhance, every image goes through vision.preprocess.enhance (denoise, lighting, sharpen),
the same step the pipeline runs before detection, so the model is trained on what it will see.

Every class should appear in all three sets. Images are assigned rarest class first, each to the set
missing the most of its classes, before the 70/20/10 ratio is considered. A class with fewer than
3 images cannot be in all three sets, so the classes still missing from a set are listed.
All the images of one door-close event (the cameras' views of the same scene) go to the same set,
otherwise the model is evaluated on scenes it was trained on.
"""
import argparse
import random
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import yaml

from vision.preprocess import enhance, load_image
from vision.products import PRODUCTS, yolo_class_names

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
DATASET_DIR = STORAGE_DIR / "dataset"
YOLO_DIR = STORAGE_DIR / "yolo"
SPLITS = {"train": 0.7, "val": 0.2, "test": 0.1}
# Fixed so that running the script again on the same images gives the same split
SEED = 0
# Camera images are named <event_id>_cam<N> by `annotations prepare`
EVENT_ID = re.compile(r"^([0-9a-f]{16})_cam\d")
# Enhanced images are saved as JPEG again: high quality, so the compression adds little
ENHANCED_JPEG_QUALITY = 95


def group_key(image: Path) -> str:
    """Images with the same key show the same scene: the event id, or the image itself for phone photos."""
    match = EVENT_ID.match(image.name)
    return match.group(1) if match else image.stem


def read_classes(label: Path) -> Counter:
    return Counter(int(line.split()[0]) for line in label.read_text(encoding="utf-8").splitlines() if line.strip())


def choose_split(classes: Counter, have: dict, images_per_split: Counter, total_images: int,
                 class_totals: Counter, class_groups: Counter) -> str:
    # Coverage first: the set that is missing the most of this image's classes, rare classes
    # counting more since fewer images are left to cover them. Ties go to train, then val, then test.
    # A class in only 1 or 2 images can't reach all three sets, so it only counts for train (and val)
    gains = {
        split: sum(
            1 / class_groups[class_id]
            for class_id in classes
            if have[split][class_id] == 0 and index < class_groups[class_id]
        )
        for index, split in enumerate(SPLITS)
    }
    best = max(gains.values())
    if best > 0:
        return next(split for split in SPLITS if gains[split] == best)
    if classes:
        # Every set has all of them: the set furthest below its share of the rarest class
        rarest = min(classes, key=lambda class_id: class_groups[class_id])
        return max(SPLITS, key=lambda split: SPLITS[split] * class_totals[rarest] - have[split][rarest])
    # No products in the image: only the image ratio matters
    return max(SPLITS, key=lambda split: SPLITS[split] * total_images - images_per_split[split])


def repair_coverage(assignment: dict, group_classes: dict, groups: dict, have: dict,
                    images_per_split: Counter, class_groups: Counter) -> None:
    """Fix classes the greedy pass left out of a set although they are in enough images.

    An image can hold several classes, so placing it for its rarest class can leave another class
    out of a set. Moves a group into the set missing the class, but only from a set that keeps at
    least one other image of every class the group holds, so the move never uncovers anything.
    """
    def images_with(split: str, class_id: int) -> int:
        return sum(1 for key, s in assignment.items() if s == split and class_id in group_classes[key])

    for class_id in sorted(class_groups, key=lambda c: class_groups[c]):
        for index, split in enumerate(SPLITS):
            if index >= class_groups[class_id] or have[split][class_id] > 0:
                continue
            for key, source in assignment.items():
                if source == split or class_id not in group_classes[key]:
                    continue
                if all(images_with(source, c) >= 2 for c in group_classes[key]):
                    assignment[key] = split
                    have[source] -= group_classes[key]
                    have[split] += group_classes[key]
                    images_per_split[source] -= len(groups[key])
                    images_per_split[split] += len(groups[key])
                    break


def copy_image(source: Path, target: Path, enhanced: bool) -> None:
    if not enhanced:
        shutil.copy2(source, target)
        return
    # Lens correction (undistort) is not applied: it moves pixels, so the boxes labeled on the
    # raw image would no longer match. enhance() only changes pixel values
    image = enhance(load_image(source))
    cv2.imwrite(str(target.with_suffix(".jpg")), image, [cv2.IMWRITE_JPEG_QUALITY, ENHANCED_JPEG_QUALITY])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--enhance", action="store_true", help="run vision.preprocess.enhance on every image")
    args = parser.parse_args()

    images = sorted(path for path in (DATASET_DIR / "images").iterdir() if path.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if not images:
        print(f"No images in storage/{DATASET_DIR.name}/images. Run `python -m scripts.annotations import` first")
        return

    groups = defaultdict(list)
    for image in images:
        groups[group_key(image)].append(image)
    group_classes = {
        key: sum((read_classes(DATASET_DIR / "labels" / f"{image.stem}.txt") for image in members), Counter())
        for key, members in groups.items()
    }
    class_totals = sum(group_classes.values(), Counter())
    # In how many groups each class appears: what limits how many sets it can be in
    class_groups = Counter(class_id for classes in group_classes.values() for class_id in classes)

    # Rarest class first, so the rare classes are placed while every set still lacks them
    keys = list(groups)
    random.Random(SEED).shuffle(keys)
    keys.sort(key=lambda key: min((class_groups[c] for c in group_classes[key]), default=float("inf")))

    have = {split: Counter() for split in SPLITS}
    images_per_split = Counter()
    assignment = {}
    for key in keys:
        split = choose_split(group_classes[key], have, images_per_split, len(images), class_totals, class_groups)
        assignment[key] = split
        have[split] += group_classes[key]
        images_per_split[split] += len(groups[key])

    repair_coverage(assignment, group_classes, groups, have, images_per_split, class_groups)

    shutil.rmtree(YOLO_DIR, ignore_errors=True)
    for key, split in assignment.items():
        for image in groups[key]:
            for kind in ("images", "labels"):
                (YOLO_DIR / split / kind).mkdir(parents=True, exist_ok=True)
            copy_image(image, YOLO_DIR / split / "images" / image.name, args.enhance)
            label = DATASET_DIR / "labels" / f"{image.stem}.txt"
            shutil.copy2(label, YOLO_DIR / split / "labels" / label.name)

    # No `path` key: Ultralytics then resolves train/val/test relative to this file,
    # so the folder can be uploaded to Colab as is
    data = {split: f"{split}/images" for split in SPLITS}
    data["names"] = dict(enumerate(yolo_class_names()))
    # Not used by Ultralytics: records how the images were prepared, so the pipeline can match it
    data["enhanced"] = args.enhance
    (YOLO_DIR / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    print(f"Wrote storage/{YOLO_DIR.name}{' (enhanced)' if args.enhance else ''}: " + ", ".join(
        f"{split} {images_per_split[split]} images ({images_per_split[split] / len(images):.0%})" for split in SPLITS
    ))
    print(f"\n{'class':<20}" + "".join(f"{split:>8}" for split in SPLITS))
    missing = []
    for class_id, product in enumerate(PRODUCTS):
        counts = [have[split][class_id] for split in SPLITS]
        print(f"{product.name:<20}" + "".join(f"{count:>8}" for count in counts))
        if 0 < sum(counts) and 0 in counts:
            missing.append(product.name)
    unlabeled = [product.name for class_id, product in enumerate(PRODUCTS) if class_totals[class_id] == 0]
    if missing:
        print(f"\nNot in all three sets (need more images): {', '.join(missing)}")
    if unlabeled:
        print(f"Not labeled in any image: {', '.join(unlabeled)}")


if __name__ == "__main__":
    main()
