"""Run inside the backend container: docker compose run --rm --no-deps web python -m unittest discover tests"""
import unittest
from datetime import date, datetime

from inventory.update import RowQuantity, take_from_rows


class TakeFromRowsTest(unittest.TestCase):
    def test_takes_from_the_row_that_expires_first(self):
        rows = [RowQuantity(1, 2, date(2026, 11, 30), None), RowQuantity(2, 2, date(2026, 11, 20), None)]

        self.assertEqual(take_from_rows(rows, 1), {2: 1})

    def test_empties_a_row_and_continues_to_the_next(self):
        rows = [RowQuantity(1, 2, date(2026, 11, 30), None), RowQuantity(2, 1, date(2026, 11, 20), None)]

        self.assertEqual(take_from_rows(rows, 2), {2: 0, 1: 1})

    def test_rows_without_expiration_date_go_last(self):
        rows = [RowQuantity(1, 1, None, None), RowQuantity(2, 1, date(2026, 12, 31), None)]

        self.assertEqual(take_from_rows(rows, 1), {2: 0})

    def test_same_date_takes_the_oldest_row_first(self):
        rows = [RowQuantity(1, 1, None, datetime(2026, 11, 10)), RowQuantity(2, 1, None, datetime(2026, 11, 1))]

        self.assertEqual(take_from_rows(rows, 1), {2: 0})

    def test_taking_everything(self):
        rows = [RowQuantity(1, 3, None, None)]

        self.assertEqual(take_from_rows(rows, 3), {1: 0})


if __name__ == "__main__":
    unittest.main()
