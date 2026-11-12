"""Run inside the backend container: docker compose run --rm --no-deps web python -m unittest discover tests"""
import unittest

from inventory.diff import ChangeType, ProductChange, diff_inventory
from inventory.merge import SnapshotItem


def snapshot(**quantities: int) -> dict[str, SnapshotItem]:
    return {
        name: SnapshotItem(product_name=name, category=None, quantity=quantity, confidence=0.9, camera_ids={1})
        for name, quantity in quantities.items()
    }


class DiffInventoryTest(unittest.TestCase):
    def test_new_product_is_added(self):
        changes = diff_inventory(snapshot(milk=1), {})

        self.assertEqual(changes, [ProductChange("milk", ChangeType.ADDED, 0, 1)])

    def test_missing_product_is_removed(self):
        changes = diff_inventory(snapshot(), {"milk": 1})

        self.assertEqual(changes, [ProductChange("milk", ChangeType.REMOVED, 1, 0)])

    def test_different_quantity_is_quantity_changed(self):
        self.assertEqual(diff_inventory(snapshot(yogurt=2), {"yogurt": 3}),
                         [ProductChange("yogurt", ChangeType.QUANTITY_CHANGED, 3, 2)])
        self.assertEqual(diff_inventory(snapshot(yogurt=4), {"yogurt": 3}),
                         [ProductChange("yogurt", ChangeType.QUANTITY_CHANGED, 3, 4)])

    def test_same_quantity_is_unchanged(self):
        changes = diff_inventory(snapshot(milk=1), {"milk": 1})

        self.assertEqual(changes, [ProductChange("milk", ChangeType.UNCHANGED, 1, 1)])

    def test_every_product_is_classified(self):
        changes = diff_inventory(snapshot(milk=1, carrot=2, lemon=1), {"milk": 1, "carrot": 1, "eggs": 1})

        self.assertEqual({change.product_name: change.change for change in changes}, {
            "carrot": ChangeType.QUANTITY_CHANGED,
            "eggs": ChangeType.REMOVED,
            "lemon": ChangeType.ADDED,
            "milk": ChangeType.UNCHANGED,
        })

    def test_empty_fridge_and_inventory(self):
        self.assertEqual(diff_inventory(snapshot(), {}), [])


if __name__ == "__main__":
    unittest.main()
