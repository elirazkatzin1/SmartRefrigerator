"""Run inside the backend container: docker compose run --rm --no-deps web python -m unittest discover tests"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import main
from scripts.split_dataset import group_key

EVENT_A = "a3f09c1e7b2d4410"
EVENT_B = "0b0a72c9147734d3"


class EventFolderTest(unittest.TestCase):
    def setUp(self):
        self.images = Path(tempfile.mkdtemp())
        patcher = mock.patch.object(main, "IMAGES_DIR", self.images)
        patcher.start()
        self.addCleanup(patcher.stop)

    def folder(self, event_id: str) -> str:
        name = main._find_or_number_event_folder(event_id)
        (self.images / name).mkdir(exist_ok=True)
        return name

    def test_first_event_is_number_one(self):
        self.assertEqual(self.folder(EVENT_A), f"0001_{EVENT_A}")

    def test_next_event_gets_the_next_number(self):
        self.folder(EVENT_A)

        self.assertEqual(self.folder(EVENT_B), f"0002_{EVENT_B}")

    def test_more_images_of_an_event_use_its_folder(self):
        self.folder(EVENT_A)
        self.folder(EVENT_B)

        self.assertEqual(self.folder(EVENT_A), f"0001_{EVENT_A}")

    def test_numbering_continues_after_the_highest(self):
        (self.images / f"0041_{EVENT_A}").mkdir()
        # Folders from before the numbering are ignored
        (self.images / "1c1e93c6c021f1b8").mkdir()

        self.assertEqual(self.folder(EVENT_B), f"0042_{EVENT_B}")

    def test_empty_images_folder_starts_again_at_one(self):
        self.images.rmdir()

        self.assertEqual(main._find_or_number_event_folder(EVENT_A), f"0001_{EVENT_A}")

    def test_split_groups_cameras_of_a_numbered_event(self):
        self.assertEqual(group_key(Path(f"0007_{EVENT_A}_cam1_jpg.rf.abc.jpg")), EVENT_A)
        self.assertEqual(group_key(Path(f"{EVENT_A}_cam2_jpg.rf.def.jpg")), EVENT_A)


if __name__ == "__main__":
    unittest.main()
