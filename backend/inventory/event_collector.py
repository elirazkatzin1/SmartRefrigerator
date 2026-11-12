"""Group the analyzed images of one door-close event before merging them into one fridge snapshot.

All cameras photograph the fridge on the same door-close event (the same event_id), but their images
arrive one by one: the cameras upload only once the door opens again and WiFi is back, and each image
is analyzed separately. The event is ready when every expected camera's image has been analyzed, or
after a timeout from the first one, so a camera that failed or whose image never arrives doesn't hold
the event back forever.
"""
import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from log import log

logger = logging.getLogger(__name__)

# How many cameras the fridge has. The design is 5; set EXPECTED_CAMERAS while fewer are installed,
# otherwise every event waits for the full timeout
EXPECTED_CAMERAS = int(os.getenv("EXPECTED_CAMERAS", "5"))
# Seconds from the first analyzed image of an event until it is merged with whatever has arrived
EVENT_TIMEOUT_S = float(os.getenv("EVENT_TIMEOUT_S", "15"))


@dataclass
class ReadyEvent:
    event_id: str
    # The cameras whose image was analyzed (successfully or not) before the event was released
    camera_ids: set[int]
    # True when released by the timeout instead of by all cameras arriving
    timed_out: bool


@dataclass
class _PendingEvent:
    camera_ids: set[int] = field(default_factory=set)
    timer: asyncio.Task | None = None


class EventCollector:
    """Calls on_ready once per event_id, when all cameras are in or the timeout has passed.

    State is kept in memory: events still waiting when the server restarts are not released.
    """

    def __init__(self, on_ready: Callable[[ReadyEvent], Awaitable[None]],
                 expected_cameras: int = EXPECTED_CAMERAS, timeout_s: float = EVENT_TIMEOUT_S):
        self._on_ready = on_ready
        self._expected_cameras = expected_cameras
        self._timeout_s = timeout_s
        self._pending: dict[str, _PendingEvent] = {}
        # Events already handed to on_ready, so a late or re-sent image doesn't release them again
        self._released: set[str] = set()

    async def image_analyzed(self, event_id: str, camera_id: int) -> None:
        """Report that one camera's image of this event has been analyzed (done or failed)."""
        if event_id in self._released:
            log(logger, "image arrived after its event was merged, ignored", logging.WARNING,
                event_id=event_id, camera_id=camera_id)
            return

        pending = self._pending.setdefault(event_id, _PendingEvent())
        pending.camera_ids.add(camera_id)
        if pending.timer is None:
            pending.timer = asyncio.create_task(self._release_after_timeout(event_id))

        if len(pending.camera_ids) >= self._expected_cameras:
            pending.timer.cancel()
            await self._release(event_id, timed_out=False)

    async def _release_after_timeout(self, event_id: str) -> None:
        await asyncio.sleep(self._timeout_s)
        pending = self._pending.get(event_id)
        if pending is not None:
            log(logger, "event timed out, merging the cameras that arrived", logging.WARNING, event_id=event_id,
                cameras=sorted(pending.camera_ids), expected=self._expected_cameras)
            await self._release(event_id, timed_out=True)

    async def _release(self, event_id: str, timed_out: bool) -> None:
        pending = self._pending.pop(event_id, None)
        if pending is None:
            return
        self._released.add(event_id)
        await self._on_ready(ReadyEvent(event_id, pending.camera_ids, timed_out))
