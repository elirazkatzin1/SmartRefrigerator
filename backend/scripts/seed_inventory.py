"""Add sample products to the inventory so the app has something to show during development.

Expiration dates are relative to today, so every freshness color (fresh, expiring soon,
expired, no date) always appears. The items use real product names and categories from
vision/products.py and are stored as manual entries, so door events don't remove them.
Run inside the backend container:
    docker compose exec web python -m scripts.seed_inventory          # add the sample items
    docker compose exec web python -m scripts.seed_inventory --clear  # remove them again

--clear deletes only manual rows named like the sample items, never camera detections.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete

from database import AsyncSessionLocal
from models import ExpirationSource, Inventory, InventorySource
from vision.products import category_of

# Same as main.LOCAL_TZ: expiration dates are Israel-local dates
LOCAL_TZ = ZoneInfo("Asia/Jerusalem")

# (product_name from vision/products.py, quantity,
#  days until expiration or None for no date, days since it was put in the fridge)
SAMPLE_ITEMS = [
    ("milk", 1, 2, 5),
    ("cottage_cheese", 2, 6, 1),
    ("yellow_cheese", 1, 12, 3),
    ("yogurt", 4, -1, 5),
    ("eggs", 12, 20, 7),
    ("tomato", 6, 5, 2),
    ("cucumber", 4, 3, 4),
    ("lettuce", 1, 0, 6),
    ("lemon", 3, 8, 10),
    ("hummus", 1, -3, 9),
    ("ketchup", 1, None, 30),
    ("tortillas", 1, 1, 0),
]
SAMPLE_NAMES = [name for name, *_ in SAMPLE_ITEMS]


async def clear_samples(db):
    await db.execute(
        delete(Inventory).where(
            Inventory.product_name.in_(SAMPLE_NAMES),
            Inventory.source == InventorySource.MANUAL.value,
        )
    )


async def seed():
    today = datetime.now(LOCAL_TZ).date()
    # added_at is stored in naive UTC, like models.Inventory's default
    now_utc = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        # Replace earlier sample rows instead of piling up duplicates
        await clear_samples(db)
        for name, quantity, days, days_in_fridge in SAMPLE_ITEMS:
            category = category_of(name)
            expiration = today + timedelta(days=days) if days is not None else None
            db.add(Inventory(
                product_name=name,
                category=category.value if category else None,
                quantity=quantity,
                added_at=now_utc - timedelta(days=days_in_fridge),
                expiration_date=expiration,
                expiration_source=ExpirationSource.MANUAL.value if expiration else None,
                source=InventorySource.MANUAL.value,
            ))
        await db.commit()
    print(f"Added {len(SAMPLE_ITEMS)} sample items.")


async def clear():
    async with AsyncSessionLocal() as db:
        await clear_samples(db)
        await db.commit()
    print("Removed the sample items.")


if __name__ == "__main__":
    asyncio.run(clear() if "--clear" in sys.argv else seed())
