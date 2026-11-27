"""The shopping list (SR-94): items the user adds, and products added automatically when they run out.

Automatic adding is a simple first rule, kept in one place so it can be replaced by smarter habit
learning later: when a product runs out of the fridge (the inventory sync removed its last row) and it
was bought at least MIN_PURCHASES_TO_SUGGEST times, it is added to the list as an "auto" item.
"""
import logging
import re

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from log import log
from models import Inventory, ShoppingItem, ShoppingItemSource
from vision.products import PRODUCTS, PRODUCTS_BY_NAME

logger = logging.getLogger(__name__)

# How many times a product must have been put in the fridge before its running out adds it to the list.
# Each purchase the cameras see is its own Inventory row (removed rows are kept as history)
MIN_PURCHASES_TO_SUGGEST = 2

_PRODUCTS_BY_HEBREW = {product.name_he: product for product in PRODUCTS}


class DuplicateItem(ValueError):
    """The item is already on the list and not checked off yet."""


def display_name(product_name: str) -> str:
    # "cottage_cheese" -> "Cottage cheese", like formatProductName in the app
    return product_name.replace("_", " ").strip().capitalize()


def clean_name(name: str) -> str:
    """The typed name with spaces trimmed and runs of spaces collapsed."""
    return re.sub(r"\s+", " ", name).strip()


def catalog_name(name: str) -> str | None:
    """The catalog product a typed name refers to, in English ("Cottage cheese") or Hebrew ("קוטג'"), if any."""
    cleaned = clean_name(name)
    key = cleaned.lower().replace(" ", "_")
    if key in PRODUCTS_BY_NAME:
        return key
    product = _PRODUCTS_BY_HEBREW.get(cleaned)
    return product.name if product else None


async def list_items(db: AsyncSession) -> list[ShoppingItem]:
    """Items still to buy first (oldest first, in the order they were added), then the bought ones."""
    result = await db.execute(select(ShoppingItem).order_by(ShoppingItem.checked, ShoppingItem.created_at, ShoppingItem.id))
    return list(result.scalars().all())


async def _open_duplicate(db: AsyncSession, name: str, product_name: str | None) -> ShoppingItem | None:
    """An item for the same thing that is still to buy: same product, or the same typed name."""
    same = (ShoppingItem.product_name == product_name) if product_name else (func.lower(ShoppingItem.name) == name.lower())
    result = await db.execute(select(ShoppingItem).where(same, ShoppingItem.checked.is_(False)).limit(1))
    return result.scalar_one_or_none()


async def add_manual(db: AsyncSession, name: str) -> ShoppingItem:
    """Add an item the user typed. Raises DuplicateItem when it is already on the list. Commits."""
    cleaned = clean_name(name)
    if not cleaned:
        raise ValueError("The name is empty")
    product_name = catalog_name(cleaned)
    if await _open_duplicate(db, cleaned, product_name) is not None:
        raise DuplicateItem(f"{cleaned} is already on the list")
    item = ShoppingItem(name=cleaned, product_name=product_name, source=ShoppingItemSource.MANUAL.value)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def add_ran_out_products(db: AsyncSession, product_names: set[str]) -> list[str]:
    """Add the products that just ran out and are bought regularly. Commits. Returns the names added."""
    added = []
    for product_name in sorted(product_names):
        # Another row of it is still in the fridge (e.g. a manual one): it hasn't run out
        still_in = await db.scalar(select(func.count()).select_from(Inventory).where(
            Inventory.product_name == product_name, Inventory.removed_at.is_(None)))
        if still_in:
            continue
        purchases = await db.scalar(select(func.count()).select_from(Inventory).where(
            Inventory.product_name == product_name))
        if purchases < MIN_PURCHASES_TO_SUGGEST:
            continue
        if await _open_duplicate(db, display_name(product_name), product_name) is not None:
            continue
        db.add(ShoppingItem(name=display_name(product_name), product_name=product_name,
                            source=ShoppingItemSource.AUTO.value))
        added.append(product_name)
    await db.commit()
    if added:
        log(logger, "added to the shopping list", products=added)
    return added


async def set_checked(db: AsyncSession, item: ShoppingItem, checked: bool) -> ShoppingItem:
    item.checked = checked
    await db.commit()
    await db.refresh(item)
    return item


async def clear_checked(db: AsyncSession) -> int:
    """Delete every bought item. Commits. Returns how many were deleted."""
    result = await db.execute(delete(ShoppingItem).where(ShoppingItem.checked.is_(True)))
    await db.commit()
    return result.rowcount
