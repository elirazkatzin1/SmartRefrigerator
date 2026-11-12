"""Apply the changes of a door-close event to the Inventory table.

The quantity in the inventory follows what the cameras saw: 3 yogurts detected -> quantity 3.
A product can have several rows (one per purchase, each with its own expiration date), so:
- More than before: the new items are a new row, since they are a new purchase with a later
  expiration date (filled in by the OCR step).
- Fewer than before: items are taken off the row that expires first, which is usually what gets
  used first. A row that reaches 0 is marked removed (removed_at), not deleted.

Products the cameras no longer see (ChangeType.REMOVED) are not removed right away: a product can be
hidden behind another one. It is removed only after it was missing from REMOVAL_TOLERANCE_EVENTS
door events in a row (apply_removals).
"""
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.diff import ChangeType, ProductChange
from inventory.merge import SnapshotItem
from models import Inventory, InventorySource

# A product the cameras don't see is removed only after this many door events in a row without it
REMOVAL_TOLERANCE_EVENTS = 2


@dataclass
class RowQuantity:
    row_id: int
    quantity: int
    expiration_date: date | None
    added_at: datetime | None


def take_from_rows(rows: list[RowQuantity], amount: int) -> dict[int, int]:
    """Take `amount` items off the rows, earliest expiration first. Returns {row_id: new quantity}
    for the rows that changed.

    Rows without an expiration date go last, and among equal dates the oldest row goes first.
    """
    order = sorted(rows, key=lambda row: (row.expiration_date is None, row.expiration_date or date.max,
                                          row.added_at or datetime.min))
    new_quantities = {}
    for row in order:
        if amount == 0:
            break
        taken = min(row.quantity, amount)
        new_quantities[row.row_id] = row.quantity - taken
        amount -= taken
    return new_quantities


async def apply_quantities(db: AsyncSession, snapshot: dict[str, SnapshotItem], changes: list[ProductChange],
                           seen_at: datetime) -> None:
    """Update the inventory to the snapshot's quantities. The caller commits."""
    for change in changes:
        if change.change == ChangeType.REMOVED:
            continue
        item = snapshot[change.product_name]
        rows = (await db.execute(
            select(Inventory).where(Inventory.product_name == change.product_name, Inventory.removed_at.is_(None))
        )).scalars().all()

        added = change.new_quantity - change.old_quantity
        if added > 0:
            rows.append(Inventory(
                product_name=item.product_name,
                category=item.category,
                quantity=added,
                source=InventorySource.AI.value,
                added_at=seen_at,
            ))
            db.add(rows[-1])
        elif added < 0:
            new_quantities = take_from_rows(
                [RowQuantity(row.id, row.quantity, row.expiration_date, row.added_at) for row in rows], -added
            )
            for row in rows:
                if row.id not in new_quantities:
                    continue
                if new_quantities[row.id] == 0:
                    # Keeps the quantity it had, as history; removed rows are not counted as inventory
                    row.removed_at = seen_at
                else:
                    row.quantity = new_quantities[row.id]

        # Seen in this event: every row still in the fridge, including a new one
        for row in rows:
            if row.removed_at is None:
                row.last_seen_at = seen_at
                row.confidence = item.confidence
                row.missed_events = 0


async def apply_removals(db: AsyncSession, changes: list[ProductChange], event_time: datetime) -> None:
    """Count one more miss for every product the cameras didn't see, and remove the products that
    were missing from REMOVAL_TOLERANCE_EVENTS events in a row. The caller commits.
    """
    for change in changes:
        if change.change != ChangeType.REMOVED:
            continue
        rows = (await db.execute(
            select(Inventory).where(Inventory.product_name == change.product_name, Inventory.removed_at.is_(None))
        )).scalars().all()
        for row in rows:
            row.missed_events += 1
            if row.missed_events >= REMOVAL_TOLERANCE_EVENTS:
                row.removed_at = event_time
