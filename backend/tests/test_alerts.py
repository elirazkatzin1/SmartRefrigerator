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


def row(row_id: int, name: str, expires: date | None, source: str = "manual") -> Inventory:
    return Inventory(id=row_id, product_name=name, quantity=1, added_at=datetime(2026, 11, 10, 10, 0),
                     expiration_date=expires, expiration_source=source if expires else None)


class ItemAlertsTest(unittest.TestCase):
    def test_only_products_within_two_days_of_expiry_or_expired(self):
        rows = [
            row(1, "milk", date(2026, 11, 20)),  # 3 days left: no alert yet
            row(2, "cottage_cheese", date(2026, 11, 19)),  # 2 days left
            row(3, "yogurt", date(2026, 11, 15)),  # expired
            row(4, "ketchup", None),  # no date: no alert
        ]

        alerts = {alert.id: alert for alert in item_alerts(rows, TODAY)}

        self.assertEqual(set(alerts), {"expiry:2", "expiry:3"})
        self.assertEqual((alerts["expiry:2"].type, alerts["expiry:2"].severity), ("expiring_soon", "info"))
        self.assertEqual((alerts["expiry:3"].type, alerts["expiry:3"].severity), ("expired", "warning"))
        self.assertEqual(alerts["expiry:2"].expires_on, "2026-11-19")

    def test_messages_for_a_date_the_user_entered(self):
        messages = [alert.message for alert in item_alerts([
            row(1, "milk", date(2026, 11, 17)),
            row(2, "milk", date(2026, 11, 18)),
            row(3, "milk", date(2026, 11, 19)),
            row(4, "milk", date(2026, 11, 16)),
            row(5, "milk", date(2026, 11, 14)),
        ], TODAY)]

        self.assertEqual(messages, [
            "Milk expires today",
            "Milk expires tomorrow",
            "Milk expires in 2 days",
            "Milk expired yesterday",
            "Milk expired 3 days ago",
        ])

    def test_estimated_dates_say_probably(self):
        messages = [alert.message for alert in item_alerts([
            row(1, "cottage_cheese", date(2026, 11, 18), source="estimated"),
            row(2, "cottage_cheese", date(2026, 11, 10), source="estimated"),
        ], TODAY)]

        self.assertEqual(messages, ["Cottage cheese probably expires tomorrow", "Cottage cheese has probably expired"])


class HelpersTest(unittest.TestCase):
    def test_missing_cameras(self):
        self.assertEqual(missing_cameras({1, 3}, 4), {2, 4})
        self.assertEqual(missing_cameras({1, 2}, 2), set())

    def test_most_severe_first_then_events_then_soonest_expiry(self):
        alerts = [
            Alert("later", "expiring_soon", "info", "", "2026-11-17T09:00:00+00:00", "2026-11-19"),
            Alert("expired", "expired", "warning", "", "2026-11-17T09:00:00+00:00", "2026-11-15"),
            Alert("door", "door_open", "warning", "", "2026-11-17T08:00:00+00:00"),
            Alert("camera", "camera_offline", "critical", "", "2026-11-17T07:00:00+00:00"),
            Alert("sooner", "expiring_soon", "info", "", "2026-11-17T09:00:00+00:00", "2026-11-17"),
        ]

        self.assertEqual([alert.id for alert in sort_alerts(alerts)], ["camera", "door", "expired", "sooner", "later"])


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

    async def test_offline_cameras_lists_the_missing_ones(self):
        self.assertEqual(self.hub.offline_cameras(), [])

        await self.hub.event_merged({2})
        self.assertEqual(self.hub.offline_cameras(), [1, 3])

        await self.hub.event_merged({1, 2, 3})
        self.assertEqual(self.hub.offline_cameras(), [])

    async def test_camera_alert_keeps_its_time_while_still_missing(self):
        await self.hub.event_merged({1, 3})
        first = self.app.messages[-1]["alerts"][0]["created_at"]
        await self.hub.event_merged({1, 3})

        self.assertEqual(self.app.messages[-1]["alerts"][0]["created_at"], first)

    async def test_item_alerts_come_from_the_inventory(self):
        self.inventory = [row(7, "yogurt", date(2026, 1, 1))]

        await self.hub.broadcast()

        self.assertEqual(self.app.last_types(), ["expired"])

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
