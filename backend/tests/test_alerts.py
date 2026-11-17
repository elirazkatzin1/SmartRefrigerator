"""Run inside the backend container: docker compose run --rm --no-deps web python -m unittest discover tests"""
import asyncio
import unittest
from datetime import date, datetime

from alerts import AlertHub, Alert, item_alerts, missing_cameras, sort_alerts
from models import Inventory

TODAY = date(2026, 11, 17)


class FakeApp:
    """Stands in for a connected app's WebSocket and keeps every message it was sent."""

    def __init__(self, fail: bool = False):
        self.messages = []
        self.fail = fail

    async def accept(self):
        pass

    async def send_json(self, message):
        if self.fail:
            raise ConnectionError("app went away")
        self.messages.append(message)

    def last_types(self):
        return [alert["type"] for alert in self.messages[-1]["alerts"]]


def row(row_id: int, name: str, added_at: datetime) -> Inventory:
    return Inventory(id=row_id, product_name=name, quantity=1, added_at=added_at)


class ItemAlertsTest(unittest.TestCase):
    def test_only_products_in_the_fridge_more_than_five_days(self):
        rows = [
            row(1, "milk", datetime(2026, 11, 12, 10, 0)),  # 5 days: still fine
            row(2, "cottage_cheese", datetime(2026, 11, 11, 10, 0)),  # 6 days
        ]

        alerts = item_alerts(rows, TODAY)

        self.assertEqual([alert.id for alert in alerts], ["long_in_fridge:2"])
        self.assertEqual(alerts[0].message, "Cottage cheese has been in the fridge for 6 days")
        self.assertEqual(alerts[0].severity, "info")

    def test_days_are_counted_on_the_israel_calendar(self):
        # 22:30 UTC on Nov 10 is already Nov 11 in Israel, so it is 6 days, not 7
        alerts = item_alerts([row(1, "milk", datetime(2026, 11, 10, 22, 30))], TODAY)

        self.assertIn("for 6 days", alerts[0].message)


class HelpersTest(unittest.TestCase):
    def test_missing_cameras(self):
        self.assertEqual(missing_cameras({1, 3}, 4), {2, 4})
        self.assertEqual(missing_cameras({1, 2}, 2), set())

    def test_most_severe_first_then_newest(self):
        alerts = [
            Alert("a", "long_in_fridge", "info", "", "2026-11-17T09:00:00+00:00"),
            Alert("b", "door_open", "warning", "", "2026-11-17T08:00:00+00:00"),
            Alert("c", "camera_offline", "critical", "", "2026-11-17T07:00:00+00:00"),
            Alert("d", "long_in_fridge", "info", "", "2026-11-17T10:00:00+00:00"),
        ]

        self.assertEqual([alert.id for alert in sort_alerts(alerts)], ["c", "b", "d", "a"])


class AlertHubTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.inventory = []

        async def load_inventory():
            return self.inventory

        self.hub = AlertHub(load_inventory=load_inventory, door_open_alert_s=0.05, expected_cameras=3)
        self.app = FakeApp()
        await self.hub.connect(self.app)

    async def test_a_new_app_gets_the_current_list_right_away(self):
        self.assertEqual(self.app.messages, [{"type": "alerts", "alerts": []}])

    async def test_door_left_open_raises_an_alert_and_closing_clears_it(self):
        await self.hub.door_changed(True)
        await asyncio.sleep(0.1)
        self.assertEqual(self.app.last_types(), ["door_open"])

        await self.hub.door_changed(False)
        self.assertEqual(self.app.last_types(), [])

    async def test_door_closed_in_time_raises_nothing(self):
        await self.hub.door_changed(True)
        await self.hub.door_changed(False)
        await asyncio.sleep(0.1)

        self.assertEqual(len(self.app.messages), 1)

    async def test_missing_camera_raises_an_alert_until_it_reports_again(self):
        await self.hub.event_merged({1, 3})
        alerts = self.app.messages[-1]["alerts"]
        self.assertEqual([alert["id"] for alert in alerts], ["camera_offline:2"])
        self.assertEqual(alerts[0]["severity"], "critical")

        await self.hub.event_merged({1, 2, 3})
        self.assertEqual(self.app.last_types(), [])

    async def test_camera_alert_keeps_its_time_while_still_missing(self):
        await self.hub.event_merged({1, 3})
        first = self.app.messages[-1]["alerts"][0]["created_at"]
        await self.hub.event_merged({1, 3})

        self.assertEqual(self.app.messages[-1]["alerts"][0]["created_at"], first)

    async def test_item_alerts_come_from_the_inventory(self):
        self.inventory = [row(7, "yogurt", datetime(2026, 1, 1, 10, 0))]

        await self.hub.broadcast()

        self.assertEqual(self.app.last_types(), ["long_in_fridge"])

    async def test_inventory_failure_still_sends_the_other_alerts(self):
        async def broken():
            raise ConnectionError("database down")

        self.hub._load_inventory = broken
        with self.assertLogs("alerts", level="ERROR"):
            await self.hub.event_merged({1})

        self.assertEqual(self.app.last_types(), ["camera_offline", "camera_offline"])

    async def test_an_app_that_went_away_is_dropped(self):
        gone = FakeApp(fail=True)
        self.hub._clients.add(gone)

        await self.hub.broadcast()

        self.assertNotIn(gone, self.hub._clients)
        self.assertIn(self.app, self.hub._clients)


if __name__ == "__main__":
    unittest.main()
