"""Run inside the backend container: docker compose run --rm --no-deps web python -m unittest discover tests"""
import unittest

from inventory.camera_layout import FRAME_WIDTH, Overlap
from inventory.merge import merge_detections

# Cameras 1 and 2 share the strip at camera 1's right edge and camera 2's left edge; camera 3 overlaps no one
OVERLAPS = (Overlap(zones={1: (0.8, 1.0), 2: (0.0, 0.2)}),)
MIDDLE = 0.5


def detection(class_name: str, x: float = MIDDLE, confidence: float = 0.9) -> dict:
    """A detection whose box is centered at x, a fraction of the image width (the merge uses only that)."""
    center = round(x * FRAME_WIDTH)
    return {"class_name": class_name, "category": None, "confidence": confidence,
            "bbox": [center - 20, 100, center + 20, 200]}


def quantities(detections_by_camera: dict[int, list[dict]]) -> dict[str, int]:
    return {name: item.quantity for name, item in merge_detections(detections_by_camera, OVERLAPS).items()}


class MergeDetectionsTest(unittest.TestCase):
    def test_one_camera(self):
        snapshot = merge_detections({1: [detection("milk"), detection("lemon"), detection("lemon")]}, OVERLAPS)

        self.assertEqual({name: item.quantity for name, item in snapshot.items()}, {"milk": 1, "lemon": 2})
        self.assertEqual(snapshot["milk"].category, "Dairy")

    def test_cameras_that_dont_overlap_are_added_up(self):
        # A milk on each shelf is two milks
        self.assertEqual(quantities({1: [detection("milk")], 3: [detection("milk")]}), {"milk": 2})

    def test_product_in_the_shared_strip_is_counted_once(self):
        snapshot = merge_detections({1: [detection("mustard", x=0.9)], 2: [detection("mustard", x=0.1)]}, OVERLAPS)

        self.assertEqual(snapshot["mustard"].quantity, 1)
        self.assertEqual(snapshot["mustard"].camera_ids, {1, 2})

    def test_shared_strip_takes_the_higher_count(self):
        # Camera 2 sees both mustards in the strip, camera 1 only one of them
        self.assertEqual(quantities({1: [detection("mustard", x=0.9)],
                                     2: [detection("mustard", x=0.05), detection("mustard", x=0.15)]}),
                         {"mustard": 2})

    def test_same_product_outside_the_strip_is_added(self):
        # One mustard in the shared strip, and another that only camera 2 sees
        self.assertEqual(quantities({1: [detection("mustard", x=0.9)],
                                     2: [detection("mustard", x=0.1), detection("mustard", x=0.6)]}),
                         {"mustard": 2})

    def test_strip_seen_by_only_one_camera_still_counts(self):
        # Camera 2's image is missing: what camera 1 sees in the strip is not lost
        self.assertEqual(quantities({1: [detection("mustard", x=0.9)]}), {"mustard": 1})

    def test_products_from_different_cameras_are_combined(self):
        snapshot = merge_detections({1: [detection("milk")], 2: [detection("carrot")]}, OVERLAPS)

        self.assertEqual(set(snapshot), {"milk", "carrot"})
        self.assertEqual(snapshot["carrot"].camera_ids, {2})

    def test_confidence_is_the_highest_detection(self):
        snapshot = merge_detections({1: [detection("milk", confidence=0.6)],
                                     3: [detection("milk", confidence=0.95)]}, OVERLAPS)

        self.assertEqual(snapshot["milk"].confidence, 0.95)

    def test_empty_or_missing_images(self):
        self.assertEqual(merge_detections({}, OVERLAPS), {})
        self.assertEqual(merge_detections({1: [], 2: []}, OVERLAPS), {})

    def test_unknown_product_has_no_category(self):
        snapshot = merge_detections({1: [detection("banana")]}, OVERLAPS)

        self.assertIsNone(snapshot["banana"].category)


class FridgeLayoutTest(unittest.TestCase):
    """The real layout in inventory.camera_layout (event 0032_98dec90b9e9481a4), positions as measured."""

    def test_products_between_the_upper_cameras_are_counted_once(self):
        snapshot = merge_detections({
            1: [detection("mustard", x=0.83), detection("butter", x=0.90), detection("mayonnaise", x=0.97)],
            4: [detection("mustard", x=0.05), detection("butter", x=0.09), detection("mayonnaise", x=0.21)],
        })

        self.assertEqual({name: item.quantity for name, item in snapshot.items()},
                         {"mustard": 1, "butter": 1, "mayonnaise": 1})

    def test_cucumbers_between_the_lower_cameras_take_the_higher_count(self):
        # Camera 2 sees all 3 cucumbers, camera 3 two of them
        snapshot = merge_detections({
            2: [detection("cucumber", x=0.08), detection("cucumber", x=0.15), detection("cucumber", x=0.22)],
            3: [detection("cucumber", x=0.80), detection("cucumber", x=0.92)],
        })

        self.assertEqual(snapshot["cucumber"].quantity, 3)

    def test_products_only_one_lower_camera_sees_add_up(self):
        # Peppers and milk only in camera 2, tomatoes only in camera 3
        snapshot = merge_detections({
            2: [detection("bell_pepper", x=0.33), detection("bell_pepper", x=0.50), detection("milk", x=0.66)],
            3: [detection("tomato", x=0.15), detection("tomato", x=0.40)],
        })

        self.assertEqual({name: item.quantity for name, item in snapshot.items()},
                         {"bell_pepper": 2, "milk": 1, "tomato": 2})

    def test_milk_on_both_shelves_is_two(self):
        snapshot = merge_detections({1: [detection("milk", x=0.5)], 2: [detection("milk", x=0.66)]})

        self.assertEqual(snapshot["milk"].quantity, 2)


if __name__ == "__main__":
    unittest.main()
