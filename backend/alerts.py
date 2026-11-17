"""Real-time fridge alerts for the app's Home screen (SR-92), sent over a WebSocket.

The server keeps the active alerts and sends the whole list to every connected app whenever it
changes: {"type": "alerts", "alerts": [...]}. Sending the full list (instead of add/remove messages)
means an app that reconnects after a dropped connection is up to date right away.

Alert types:
- door_open (warning): the door has been open for DOOR_OPEN_ALERT_S. Cleared when it closes.
- camera_offline (critical): a camera's photo was missing from the last door-close event (it was
  merged after the timeout without it). Cleared once that camera's photo arrives for an event again.
  The cameras send no heartbeat, so a missing photo is the only sign that a camera is down.
- long_in_fridge (info): a product has been in the fridge more than LONG_IN_FRIDGE_DAYS days.
  Computed from the inventory each time the list is sent, so it follows edits and new days.

Door and camera alerts are kept in memory: after a server restart they are empty until the next event.
"""
import asyncio
import logging
import os
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import WebSocket
from sqlalchemy import select

from database import AsyncSessionLocal
from inventory.event_collector import EXPECTED_CAMERAS
from log import log
from models import Inventory

logger = logging.getLogger(__name__)

DOOR_OPEN_ALERT_S = float(os.getenv("DOOR_OPEN_ALERT_S", "120"))
# Same as FRESH_MAX_DAYS in mobile-app/src/theme.js: past it the item turns yellow in the app
LONG_IN_FRIDGE_DAYS = 5
# long_in_fridge alerts change when the day rolls over, without any event, so the list is resent this often
REFRESH_INTERVAL_S = 600
# The days in the fridge are counted on an Israel calendar, like in the app
LOCAL_TZ = ZoneInfo("Asia/Jerusalem")

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


@dataclass
class Alert:
    # Stable per alert, e.g. "camera_offline:3", so the app can keep its place in the list
    id: str
    type: str  # door_open | camera_offline | long_in_fridge
    severity: str  # info | warning | critical
    message: str
    created_at: str  # ISO 8601 in UTC


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local_day(utc_naive: datetime) -> date:
    return utc_naive.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).date()


def _display_name(product_name: str) -> str:
    # "cottage_cheese" -> "Cottage cheese", like formatProductName in the app
    return product_name.replace("_", " ").strip().capitalize()


def item_alerts(rows: Iterable[Inventory], today: date) -> list[Alert]:
    """A long_in_fridge alert for every product in the fridge more than LONG_IN_FRIDGE_DAYS days."""
    alerts = []
    for row in rows:
        if row.added_at is None:
            continue
        days = (today - _local_day(row.added_at)).days
        if days > LONG_IN_FRIDGE_DAYS:
            alerts.append(Alert(
                id=f"long_in_fridge:{row.id}",
                type="long_in_fridge",
                severity="info",
                message=f"{_display_name(row.product_name)} has been in the fridge for {days} days",
                created_at=row.added_at.replace(tzinfo=timezone.utc).isoformat(),
            ))
    return alerts


def missing_cameras(reported: Iterable[int], expected: int) -> set[int]:
    """The camera ids (1..expected) that did not send a photo of an event."""
    return set(range(1, expected + 1)) - set(reported)


def sort_alerts(alerts: list[Alert]) -> list[Alert]:
    """Most severe first; within a severity, the newest first."""
    newest_first = sorted(alerts, key=lambda alert: alert.created_at, reverse=True)
    return sorted(newest_first, key=lambda alert: SEVERITY_ORDER[alert.severity])


async def _load_inventory() -> list[Inventory]:
    async with AsyncSessionLocal() as db:
        return list((await db.execute(select(Inventory).where(Inventory.removed_at.is_(None)))).scalars().all())


class AlertHub:
    """Keeps the active alerts and the connected apps, and sends every app the list when it changes."""

    def __init__(self, load_inventory: Callable[[], Awaitable[list[Inventory]]] = _load_inventory,
                 door_open_alert_s: float = DOOR_OPEN_ALERT_S, expected_cameras: int = EXPECTED_CAMERAS):
        self._load_inventory = load_inventory
        self._door_open_alert_s = door_open_alert_s
        self._expected_cameras = expected_cameras
        self._clients: set[WebSocket] = set()
        # door_open and camera_offline alerts; long_in_fridge ones are computed when sending
        self._alerts: dict[str, Alert] = {}
        self._door_timer: asyncio.Task | None = None

    async def current_alerts(self) -> list[dict]:
        alerts = list(self._alerts.values())
        try:
            alerts += item_alerts(await self._load_inventory(), datetime.now(LOCAL_TZ).date())
        except Exception:
            # E.g. the database is down: still send the door and camera alerts
            logger.exception("could not load the inventory for alerts")
        return [asdict(alert) for alert in sort_alerts(alerts)]

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        await websocket.send_json({"type": "alerts", "alerts": await self.current_alerts()})
        log(logger, "app connected to alerts", clients=len(self._clients))

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self) -> None:
        """Send the current list to every connected app."""
        if not self._clients:
            return
        message = {"type": "alerts", "alerts": await self.current_alerts()}
        for websocket in list(self._clients):
            try:
                await websocket.send_json(message)
            except Exception:
                # The app went away without closing the connection
                self._clients.discard(websocket)

    async def door_changed(self, door_open: bool) -> None:
        """Called on every door status. Starts the door-open timer, or clears it and the alert."""
        if self._door_timer is not None:
            self._door_timer.cancel()
            self._door_timer = None
        if door_open:
            self._door_timer = asyncio.create_task(self._alert_when_door_left_open())
        elif self._alerts.pop("door_open", None) is not None:
            await self.broadcast()

    async def _alert_when_door_left_open(self) -> None:
        await asyncio.sleep(self._door_open_alert_s)
        self._door_timer = None
        minutes = max(1, round(self._door_open_alert_s / 60))
        self._alerts["door_open"] = Alert(
            id="door_open",
            type="door_open",
            severity="warning",
            message=f"The fridge door has been open for over {minutes} minute{'s' if minutes > 1 else ''}",
            created_at=_now_iso(),
        )
        log(logger, "door left open", seconds=self._door_open_alert_s)
        await self.broadcast()

    async def event_merged(self, camera_ids: Iterable[int]) -> None:
        """Called after a door-close event was merged into the inventory (camera_ids = the photos that arrived)."""
        missing = missing_cameras(camera_ids, self._expected_cameras)
        for camera_id in range(1, self._expected_cameras + 1):
            key = f"camera_offline:{camera_id}"
            if camera_id not in missing:
                self._alerts.pop(key, None)
            elif key not in self._alerts:
                self._alerts[key] = Alert(
                    id=key,
                    type="camera_offline",
                    severity="critical",
                    message=f"Camera {camera_id} didn't send a photo of the last door event",
                    created_at=_now_iso(),
                )
        if missing:
            log(logger, "cameras missing from event", logging.WARNING, cameras=sorted(missing))
        # The inventory changed too, so the long_in_fridge alerts may have
        await self.broadcast()

    async def refresh_forever(self) -> None:
        """Resend the list periodically, so long_in_fridge alerts follow the date. Run as a task."""
        while True:
            await asyncio.sleep(REFRESH_INTERVAL_S)
            await self.broadcast()


alert_hub = AlertHub()
