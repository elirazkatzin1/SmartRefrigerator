"""Compare the merged snapshot of a door-close event with the current inventory.

Every product that is in either one is classified as added, removed, quantity_changed or unchanged.
This only classifies; applying the changes to the Inventory table (with the removal tolerance and the
protection of manual entries) is a separate step.
"""
from collections import Counter
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.merge import SnapshotItem
from models import Inventory


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    QUANTITY_CHANGED = "quantity_changed"
    UNCHANGED = "unchanged"


@dataclass
class ProductChange:
    product_name: str
    change: ChangeType
    # 0 when the product was not in the inventory / is not in the snapshot
    old_quantity: int
    new_quantity: int


def diff_inventory(snapshot: dict[str, SnapshotItem], current: dict[str, int]) -> list[ProductChange]:
    """Classify every product in the snapshot or the current inventory.

    current maps a product name to its quantity in the inventory (see current_quantities).
    The result is sorted by product name.
    """
    changes = []
    for name in sorted(set(snapshot) | set(current)):
        old = current.get(name, 0)
        new = snapshot[name].quantity if name in snapshot else 0
        if old == 0:
            change = ChangeType.ADDED
        elif new == 0:
            change = ChangeType.REMOVED
        elif old != new:
            change = ChangeType.QUANTITY_CHANGED
        else:
            change = ChangeType.UNCHANGED
        changes.append(ProductChange(name, change, old, new))
    return changes


async def current_quantities(db: AsyncSession) -> dict[str, int]:
    """The quantity of each product in the inventory now (rows that were not removed).

    A product can have several rows, e.g. two milks with different expiration dates, so they are summed.
    """
    result = await db.execute(
        select(Inventory.product_name, func.sum(Inventory.quantity))
        .where(Inventory.removed_at.is_(None))
        .group_by(Inventory.product_name)
    )
    return Counter({name: int(total) for name, total in result.all()})
