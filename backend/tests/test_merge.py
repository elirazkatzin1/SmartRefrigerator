"""Run inside the backend container: docker compose run --rm --no-deps web python -m unittest discover tests"""
import unittest

from inventory.merge import merge_detections


def detection(class_name: str, confidence: float = 0.9) -> dict:
    # The shape stored in ImageAnalysis.detections; bbox is not used by the merge
    return {"class_name": class_name, "category": None, "confidence": confidence, "bbox": [0, 0, 10, 10]}


class MergeDetectionsTest(unittest.TestCase):
    def test_one_camera(self):
        snapshot = merge_detections({1: [detection("milk"), detection("lemon"), detection("lemon")]})

        self.assertEqual(snapshot["milk"].quantity, 1)
        self.assertEqual(snapshot["lemon"].quantity, 2)
        self.assertEqual(snapshot["milk"].category, "Dairy")

    def test_product_seen_by_two_cameras_is_counted_once(self):
        snapshot = merge_detections({1: [detection("milk")], 2: [detection("milk")]})

        self.assertEqual(snapshot["milk"].quantity, 1)
        self.assertEqual(snapshot["milk"].camera_ids, {1, 2})

    def test_quantity_is_the_highest_count_of_any_camera(self):
        # Camera 2 sees all three yogurts, camera 1 only two of them
        snapshot = merge_detections({
            1: [detection("yogurt"), detection("yogurt")],
            2: [detection("yogurt"), detection("yogurt"), detection("yogurt")],
        })

        self.assertEqual(snapshot["yogurt"].quantity, 3)

    def test_products_from_different_cameras_are_combined(self):
        snapshot = merge_detections({1: [detection("milk")], 2: [detection("carrot")]})

        self.assertEqual(set(snapshot), {"milk", "carrot"})
        self.assertEqual(snapshot["carrot"].camera_ids, {2})

    def test_confidence_is_the_highest_detection(self):
        snapshot = merge_detections({1: [detection("milk", 0.6)], 2: [detection("milk", 0.95)]})

        self.assertEqual(snapshot["milk"].confidence, 0.95)

    def test_empty_or_missing_images(self):
        self.assertEqual(merge_detections({}), {})
        self.assertEqual(merge_detections({1: [], 2: []}), {})

    def test_unknown_product_has_no_category(self):
        snapshot = merge_detections({1: [detection("banana")]})

        self.assertIsNone(snapshot["banana"].category)


if __name__ == "__main__":
    unittest.main()
