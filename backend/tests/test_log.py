"""Run inside the backend container: docker compose run --rm --no-deps web python -m unittest discover tests"""
import logging
import unittest

from log import FieldsFormatter, log


class FieldsFormatterTest(unittest.TestCase):
    def format(self, message: str, **fields) -> str:
        records = []
        logger = logging.getLogger("test_log")
        logger.handlers = [handler := logging.Handler()]
        logger.propagate = False
        logger.setLevel(logging.INFO)
        handler.emit = records.append
        log(logger, message, **fields)
        return FieldsFormatter("%(name)s: %(message)s").format(records[0])

    def test_fields_are_appended_as_key_value(self):
        self.assertEqual(self.format("image analyzed", camera_id=1, detections=7),
                         "test_log: image analyzed camera_id=1 detections=7")

    def test_lists_are_comma_separated(self):
        self.assertEqual(self.format("inventory updated", added=["carrot", "milk"]),
                         "test_log: inventory updated added=carrot,milk")

    def test_values_with_spaces_are_quoted(self):
        self.assertEqual(self.format("failed", error="black image"), 'test_log: failed error="black image"')

    def test_no_fields(self):
        self.assertEqual(self.format("door closed"), "test_log: door closed")


if __name__ == "__main__":
    unittest.main()
