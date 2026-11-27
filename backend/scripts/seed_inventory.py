"""Add sample products to the inventory (and a few shopping list items) so the app has something to
show during development.

Expiration dates are relative to today, so every freshness color (fresh, expiring soon,
expired, no date) always appears. The items use real product names and categories from
vision/products.py and are stored as manual entries, so door events don't remove them.
Run inside the backend container:
    docker compose exec web python -m scripts.seed_inventory          # add the sample items
    docker compose exec web python -m scripts.seed_inventory --clear  # remove them again

--clear deletes only manual rows named like the sample items, never camera detections, and only
the shopping list items named like the sample ones.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete

from database import AsyncSessionLocal
from models import ExpirationSource, Inventory, InventorySource, ShoppingItem, ShoppingItemSource
from vision.products import category_of

# Same as main.LOCAL_TZ: expiration dates are Israel-local dates
LOCAL_TZ = ZoneInfo("Asia/Jerusalem")

# (product_name from vision/products.py, quantity,
#  days until expiration or None for no date, days since it was put in the fridge)
SAMPLE_ITEMS = [
    ("milk", 1, 2, 5),
    ("white_cheese", 2, 6, 1),
    ("yellow_cheese", 1, 12, 3),
    ("cream_cheese", 4, -1, 5),
    ("eggs", 12, 20, 7),
    ("tomato", 6, 5, 2),
    ("cucumber", 4, 3, 4),
    ("lettuce", 1, 0, 6),
    ("lemon", 3, 8, 10),
    ("garlic_sauce", 1, -3, 9),
    ("ketchup", 1, None, 30),
    ("whipping_cream", 1, 1, 0),
]
SAMPLE_NAMES = [name for name, *_ in SAMPLE_ITEMS]
# These have a date "copied from the package"; the rest have an estimated one, as the cameras' products will (SR-123)
MANUAL_DATES = {"milk", "cream_cheese"}

# Shopping list samples (SR-94): (name, catalog product_name or None, source)
SAMPLE_SHOPPING = [
    ("Bread", None, ShoppingItemSource.MANUAL),
    ("Olive oil", None, ShoppingItemSource.MANUAL),
    ("Mayonnaise", "mayonnaise", ShoppingItemSource.AUTO),
]


async def clear_samples(db):
    await db.execute(
        delete(Inventory).where(
            Inventory.product_name.in_(SAMPLE_NAMES),
            Inventory.source == InventorySource.MANUAL.value,
        )
    )
    await db.execute(delete(ShoppingItem).where(ShoppingItem.name.in_([name for name, *_ in SAMPLE_SHOPPING])))


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
                expiration_source=(None if expiration is None
                                   else ExpirationSource.MANUAL.value if name in MANUAL_DATES
                                   else ExpirationSource.ESTIMATED.value),
                source=InventorySource.MANUAL.value,
            ))
        for name, product_name, source in SAMPLE_SHOPPING:
            db.add(ShoppingItem(name=name, product_name=product_name, source=source.value))
        await db.commit()
    print(f"Added {len(SAMPLE_ITEMS)} sample items and {len(SAMPLE_SHOPPING)} shopping list items.")


async def clear():
    async with AsyncSessionLocal() as db:
        await clear_samples(db)
        await db.commit()
    print("Removed the sample items.")


if __name__ == "__main__":
    asyncio.run(clear() if "--clear" in sys.argv else seed())
