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
    """The real layout in inventory.camera_layout (event 0016_749423be91ecfe8a)."""

    def test_mustard_between_the_upper_cameras_is_one(self):
        snapshot = merge_detections({4: [detection("mustard", x=0.93)], 1: [detection("mustard", x=0.06)]})

        self.assertEqual(snapshot["mustard"].quantity, 1)

    def test_ketchup_between_the_lower_cameras_is_one(self):
        snapshot = merge_detections({2: [detection("ketchup", x=0.86)], 3: [detection("ketchup", x=0.05)]})

        self.assertEqual(snapshot["ketchup"].quantity, 1)

    def test_eggs_on_both_sides_of_the_upper_shelf_add_up(self):
        # Two eggs in camera 1's part, one in camera 4's part, none in the strip between them
        snapshot = merge_detections({1: [detection("eggs", x=0.3), detection("eggs", x=0.5)],
                                     4: [detection("eggs", x=0.7)]})

        self.assertEqual(snapshot["eggs"].quantity, 3)


if __name__ == "__main__":
    unittest.main()
