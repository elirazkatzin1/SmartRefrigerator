"""Run inside the backend container: docker compose run --rm --no-deps web python -m unittest discover tests"""
import unittest
from datetime import date, datetime

from pydantic import ValidationError

from inventory.edit import InvalidEdit, added_at_for, apply_edit
from models import Inventory
from schemas import InventoryItemUpdate

TODAY = date(2026, 11, 17)


def item(**fields) -> Inventory:
    defaults = dict(product_name="milk", category="Dairy", quantity=1, added_at=datetime(2026, 11, 15, 8, 0))
    return Inventory(**(defaults | fields))


class ApplyEditTest(unittest.TestCase):
    def test_changes_only_the_fields_that_were_sent(self):
        row = item()

        apply_edit(row, InventoryItemUpdate(quantity=3), TODAY)

        self.assertEqual(row.quantity, 3)
        self.assertEqual(row.category, "Dairy")
        self.assertEqual(row.added_at, datetime(2026, 11, 15, 8, 0))

    def test_category_is_stored_as_its_display_value(self):
        row = item()

        apply_edit(row, InventoryItemUpdate(category="Spreads & Sauces"), TODAY)

        self.assertEqual(row.category, "Spreads & Sauces")

    def test_added_on_sets_added_at_to_that_local_day(self):
        row = item()

        apply_edit(row, InventoryItemUpdate(added_on=date(2026, 11, 12)), TODAY)

        # Noon in Israel (UTC+2 in November) is 10:00 UTC
        self.assertEqual(row.added_at, datetime(2026, 11, 12, 10, 0))

    def test_added_on_today_is_allowed(self):
        row = item()

        apply_edit(row, InventoryItemUpdate(added_on=TODAY), TODAY)

        self.assertEqual(row.added_at.date(), TODAY)

    def test_added_on_in_the_future_is_rejected_and_nothing_changes(self):
        row = item()

        with self.assertRaises(InvalidEdit):
            apply_edit(row, InventoryItemUpdate(added_on=date(2026, 11, 18), quantity=5), TODAY)

        self.assertEqual(row.quantity, 1)
        self.assertEqual(row.added_at, datetime(2026, 11, 15, 8, 0))

    def test_expiration_date_is_stored_as_manual(self):
        row = item(expiration_date=date(2026, 11, 20), expiration_source="estimated")

        apply_edit(row, InventoryItemUpdate(expiration_date=date(2026, 11, 25)), TODAY)

        self.assertEqual(row.expiration_date, date(2026, 11, 25))
        self.assertEqual(row.expiration_source, "manual")

    def test_expiration_date_in_the_past_is_allowed(self):
        row = item()

        apply_edit(row, InventoryItemUpdate(expiration_date=date(2026, 11, 1)), TODAY)

        self.assertEqual(row.expiration_date, date(2026, 11, 1))

    def test_added_at_for_summer_time(self):
        # Israel is UTC+3 in summer
        self.assertEqual(added_at_for(date(2026, 7, 1)), datetime(2026, 7, 1, 9, 0))


class InventoryItemUpdateTest(unittest.TestCase):
    def test_quantity_must_be_at_least_one(self):
        with self.assertRaises(ValidationError):
            InventoryItemUpdate(quantity=0)

    def test_unknown_category_is_rejected(self):
        with self.assertRaises(ValidationError):
            InventoryItemUpdate(category="Snacks")

    def test_unknown_field_is_rejected(self):
        with self.assertRaises(ValidationError):
            InventoryItemUpdate(product_name="beer")


if __name__ == "__main__":
    unittest.main()
