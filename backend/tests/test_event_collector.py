"""Run inside the backend container: docker compose run --rm --no-deps web python -m unittest discover tests"""
import asyncio
import unittest

from inventory.event_collector import EventCollector, ReadyEvent

# Short enough to keep the tests fast, long enough that "before the timeout" is reliable
TIMEOUT_S = 0.2


class EventCollectorTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ready: list[ReadyEvent] = []

        async def on_ready(event: ReadyEvent) -> None:
            self.ready.append(event)

        self.collector = EventCollector(on_ready, expected_cameras=3, timeout_s=TIMEOUT_S)

    async def test_released_when_all_cameras_arrive(self):
        for camera_id in (1, 2, 3):
            await self.collector.image_analyzed("event1", camera_id)

        self.assertEqual(self.ready, [ReadyEvent("event1", {1, 2, 3}, timed_out=False)])

    async def test_not_released_before_all_cameras_or_timeout(self):
        await self.collector.image_analyzed("event1", 1)
        await self.collector.image_analyzed("event1", 2)

        self.assertEqual(self.ready, [])

    async def test_released_by_timeout_with_the_cameras_that_arrived(self):
        await self.collector.image_analyzed("event1", 1)
        await self.collector.image_analyzed("event1", 3)
        await asyncio.sleep(TIMEOUT_S * 2)

        self.assertEqual(self.ready, [ReadyEvent("event1", {1, 3}, timed_out=True)])

    async def test_timer_is_cancelled_when_all_cameras_arrive(self):
        for camera_id in (1, 2, 3):
            await self.collector.image_analyzed("event1", camera_id)
        await asyncio.sleep(TIMEOUT_S * 2)

        self.assertEqual(len(self.ready), 1)

    async def test_resent_image_counts_once(self):
        # The camera's upload queue re-sends an image when no response arrived
        await self.collector.image_analyzed("event1", 1)
        await self.collector.image_analyzed("event1", 1)
        await self.collector.image_analyzed("event1", 2)

        self.assertEqual(self.ready, [])

    async def test_late_image_does_not_release_the_event_again(self):
        await self.collector.image_analyzed("event1", 1)
        await asyncio.sleep(TIMEOUT_S * 2)
        await self.collector.image_analyzed("event1", 2)
        await asyncio.sleep(TIMEOUT_S * 2)

        self.assertEqual(self.ready, [ReadyEvent("event1", {1}, timed_out=True)])

    async def test_events_are_independent(self):
        await self.collector.image_analyzed("event1", 1)
        for camera_id in (1, 2, 3):
            await self.collector.image_analyzed("event2", camera_id)

        self.assertEqual(self.ready, [ReadyEvent("event2", {1, 2, 3}, timed_out=False)])
        await asyncio.sleep(TIMEOUT_S * 2)
        self.assertEqual(self.ready[1], ReadyEvent("event1", {1}, timed_out=True))


if __name__ == "__main__":
    unittest.main()
