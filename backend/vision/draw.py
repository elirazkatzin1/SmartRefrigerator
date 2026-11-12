"""Draw detections on an image, for debugging and for showing what the cameras saw in the app."""
import cv2
import numpy as np

from vision.products import Category

# BGR, one color per category so products of the same kind look alike
CATEGORY_COLORS = {
    Category.DAIRY.value: (255, 180, 60),
    Category.VEGETABLES.value: (60, 200, 60),
    Category.FRUIT.value: (0, 200, 255),
    Category.MEAT.value: (60, 60, 230),
    Category.DRINKS.value: (200, 80, 200),
    Category.SPREADS_AND_SAUCES.value: (40, 120, 220),
    Category.BAKERY.value: (90, 160, 200),
}
UNKNOWN_COLOR = (200, 200, 200)
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.5
LINE_WIDTH = 2


def draw_detections(image: np.ndarray, detections: list[dict]) -> np.ndarray:
    """A copy of the image with a box and an "name 0.93" label for each detection.

    detections are ImageAnalysis.detections dicts. Labels are in English: OpenCV can't draw Hebrew.
    """
    image = image.copy()
    for detection in detections:
        x1, y1, x2, y2 = detection["bbox"]
        color = CATEGORY_COLORS.get(detection.get("category"), UNKNOWN_COLOR)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, LINE_WIDTH)

        label = f"{detection['class_name']} {detection['confidence']:.2f}"
        (text_width, text_height), baseline = cv2.getTextSize(label, FONT, FONT_SCALE, 1)
        # Above the box, or inside it when the box touches the top of the image
        top = y1 - text_height - baseline if y1 - text_height - baseline >= 0 else y1
        cv2.rectangle(image, (x1, top), (x1 + text_width + 4, top + text_height + baseline), color, cv2.FILLED)
        cv2.putText(image, label, (x1 + 2, top + text_height), FONT, FONT_SCALE, (0, 0, 0), 1, cv2.LINE_AA)
    return image
