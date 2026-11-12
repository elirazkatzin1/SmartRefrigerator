"""Prepare images for labeling in Roboflow/CVAT, and import the labeled YOLO export back.

Run inside the backend container:
    docker compose run --rm --no-deps web python -m scripts.annotations prepare
    docker compose run --rm --no-deps web python -m scripts.annotations import storage/<export dir>

prepare: copies every camera image (storage/images/<event_id>/cam<N>.jpg) and converted phone photo
    (storage/phone_esp32) into storage/to_label with a unique flat name, and writes
    storage/to_label/classes.txt with the class names to create in the labeling tool.

import: reads an extracted YOLO export (Roboflow "YOLOv8", or CVAT "YOLO 1.1" / "Ultralytics YOLO")
    and writes storage/dataset/images and storage/dataset/labels. The labeling tool numbers the
    classes in its own order (Roboflow sorts them alphabetically), so every label is remapped by
    class name to its id in vision.products.PRODUCTS, which is the order the model is trained with.
"""
import argparse
import shutil
from collections import Counter
from pathlib import Path

import yaml

from vision.products import PRODUCTS, PRODUCTS_BY_NAME, yolo_class_names

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
CAMERA_IMAGES_DIR = STORAGE_DIR / "images"
PHONE_IMAGES_DIR = STORAGE_DIR / "phone_esp32"
TO_LABEL_DIR = STORAGE_DIR / "to_label"
DATASET_DIR = STORAGE_DIR / "dataset"
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")
# The minimum per class in SR-56
MIN_INSTANCES = 50


def prepare() -> None:
    TO_LABEL_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    # Every event directory has cam1.jpg, cam2.jpg..., so the event id goes into the name
    for path in sorted(CAMERA_IMAGES_DIR.glob("*/cam*")):
        if path.suffix.lower() in IMAGE_SUFFIXES:
            shutil.copy2(path, TO_LABEL_DIR / f"{path.parent.name}_{path.name}")
            copied += 1
    for path in sorted(PHONE_IMAGES_DIR.glob("*")):
        if path.suffix.lower() in IMAGE_SUFFIXES:
            shutil.copy2(path, TO_LABEL_DIR / f"phone_{path.name.replace(' ', '_')}")
            copied += 1

    (TO_LABEL_DIR / "classes.txt").write_text("\n".join(yolo_class_names()) + "\n", encoding="utf-8")
    print(f"Copied {copied} images to storage/{TO_LABEL_DIR.name}")
    print(f"Class names to create in the labeling tool: storage/{TO_LABEL_DIR.name}/classes.txt")


def normalize(name: str) -> str:
    """'Cottage Cheese' and 'cottage-cheese' both become 'cottage_cheese'."""
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def read_export_names(export_dir: Path) -> list[str]:
    """The class names of the export, in the export's own class-id order."""
    for yaml_path in export_dir.rglob("data.yaml"):
        names = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))["names"]
        # Ultralytics allows names as {id: name} as well as a list
        return [names[i] for i in sorted(names)] if isinstance(names, dict) else list(names)
    for names_path in [*export_dir.rglob("obj.names"), *export_dir.rglob("classes.txt")]:
        return [line for line in names_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    raise SystemExit(f"No data.yaml, obj.names or classes.txt in {export_dir}")


def remap_label(label_path: Path, id_map: dict[int, int]) -> list[str]:
    lines = []
    for number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            raise SystemExit(f"{label_path}:{number}: expected 'class x y w h', got '{line}'")
        coords = [float(value) for value in parts[1:]]
        if not all(0 <= value <= 1 for value in coords):
            raise SystemExit(f"{label_path}:{number}: coordinates must be normalized to 0-1, got '{line}'")
        lines.append(" ".join([str(id_map[int(parts[0])]), *parts[1:]]))
    return lines


def import_export(export_dir: Path) -> None:
    export_names = read_export_names(export_dir)
    unknown = [name for name in export_names if normalize(name) not in PRODUCTS_BY_NAME]
    if unknown:
        raise SystemExit(f"Classes not in vision/products.py: {unknown}. Rename them in the labeling tool")
    product_ids = {product.name: product_id for product_id, product in enumerate(PRODUCTS)}
    id_map = {export_id: product_ids[normalize(name)] for export_id, name in enumerate(export_names)}

    images_by_stem = {path.stem: path for path in export_dir.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES}
    images_out = DATASET_DIR / "images"
    labels_out = DATASET_DIR / "labels"
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)

    instances = Counter()
    imported = 0
    for stem, image_path in sorted(images_by_stem.items()):
        # Roboflow keeps labels in a sibling labels/ dir, CVAT YOLO 1.1 next to the image.
        # An image without a label file has no products in it, which is still a valid example
        candidates = [image_path.with_suffix(".txt"), image_path.parent.parent / "labels" / f"{stem}.txt"]
        label_path = next((path for path in candidates if path.exists()), None)
        lines = remap_label(label_path, id_map) if label_path else []
        instances.update(int(line.split()[0]) for line in lines)

        shutil.copy2(image_path, images_out / image_path.name)
        (labels_out / f"{stem}.txt").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        imported += 1

    print(f"Imported {imported} images to storage/{DATASET_DIR.name}\n")
    print(f"{'class':<20}{'instances':>10}")
    for product_id, product in enumerate(PRODUCTS):
        count = instances[product_id]
        print(f"{product.name:<20}{count:>10}{'' if count >= MIN_INSTANCES else '   < ' + str(MIN_INSTANCES)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare", help="copy the images to label into storage/to_label")
    import_parser = commands.add_parser("import", help="import an extracted YOLO export into storage/dataset")
    import_parser.add_argument("export_dir", type=Path)
    args = parser.parse_args()

    if args.command == "prepare":
        prepare()
    else:
        import_export(args.export_dir)


if __name__ == "__main__":
    main()
