"""Manual fixes the user makes to an inventory item in the app (SR-91).

Only the fields in InventoryItemUpdate change. Note that the cameras still own the quantity of the
rows they added: the next door event sets it back to what they see (inventory/update.py).
"""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from models import Inventory
from schemas import InventoryItemUpdate

# Same as main.LOCAL_TZ: the user picks days on an Israel calendar
LOCAL_TZ = ZoneInfo("Asia/Jerusalem")


class InvalidEdit(ValueError):
    """The requested change is not allowed (e.g. a date in the future)."""


def added_at_for(day: date) -> datetime:
    """Inventory.added_at (naive UTC) for a local day. Noon keeps it on the same day in any time zone
    the phone may be in, unlike midnight, which can fall on the previous day in UTC."""
    local_noon = datetime.combine(day, time(12), tzinfo=LOCAL_TZ)
    return local_noon.astimezone(timezone.utc).replace(tzinfo=None)


def apply_edit(row: Inventory, update: InventoryItemUpdate, today: date) -> None:
    """Apply the fields that were sent to the row. The caller commits."""
    if update.added_on is not None:
        if update.added_on > today:
            raise InvalidEdit("The date added can't be in the future")
        row.added_at = added_at_for(update.added_on)
    if update.category is not None:
        row.category = update.category.value
    if update.quantity is not None:
        row.quantity = update.quantity
