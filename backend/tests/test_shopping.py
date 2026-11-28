"""Shopping list (SR-94). The database tests use the separate test database, like test_inventory_flow.py:
    docker compose up -d db
    docker compose run --rm web python -m unittest discover tests
Without a reachable database those tests are skipped.
"""
import asyncio
import unittest
from datetime import datetime

import asyncpg
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shopping
from database import Base
from models import Inventory, InventorySource
from tests.test_inventory_flow import TEST_DATABASE_URL, ensure_test_database

_database_error: str | None = None


class NamesTest(unittest.TestCase):
    def test_typed_names_are_matched_to_the_catalog(self):
        self.assertEqual(shopping.catalog_name("White cheese"), "white_cheese")
        self.assertEqual(shopping.catalog_name("  MILK "), "milk")
        self.assertEqual(shopping.catalog_name("גבינה לבנה"), "white_cheese")
        self.assertIsNone(shopping.catalog_name("Toilet paper"))

    def test_clean_name(self):
        self.assertEqual(shopping.clean_name("  olive   oil "), "olive oil")


class ShoppingListTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        global _database_error
        if _database_error is None:
            try:
                await ensure_test_database()
            except (OSError, asyncio.TimeoutError, asyncpg.PostgresError) as error:
                _database_error = str(error) or type(error).__name__
        if _database_error:
            self.skipTest(f"test database not reachable: {_database_error}")
        self.engine = create_async_engine(TEST_DATABASE_URL)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        self.db = async_sessionmaker(self.engine, expire_on_commit=False)()

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()

    async def purchase(self, name: str, removed: bool = True):
        """One past purchase of a product; removed=True means it has since been used up."""
        self.db.add(Inventory(product_name=name, quantity=1, source=InventorySource.AI.value,
                              removed_at=datetime(2026, 11, 10) if removed else None))
        await self.db.commit()

    async def names(self):
        return [(item.name, item.source, item.checked) for item in await shopping.list_items(self.db)]

    # Adding by hand

    async def test_typed_item_is_added_and_linked_to_the_catalog(self):
        item = await shopping.add_manual(self.db, " white  cheese ")

        self.assertEqual((item.name, item.product_name, item.source), ("white cheese", "white_cheese", "manual"))

    async def test_the_same_item_can_not_be_added_twice(self):
        await shopping.add_manual(self.db, "Olive oil")

        with self.assertRaises(shopping.DuplicateItem):
            await shopping.add_manual(self.db, "olive OIL")

    async def test_an_item_can_be_added_again_once_bought(self):
        item = await shopping.add_manual(self.db, "Olive oil")
        await shopping.set_checked(self.db, item, True)

        await shopping.add_manual(self.db, "Olive oil")

        self.assertEqual(await self.names(), [("Olive oil", "manual", False), ("Olive oil", "manual", True)])

    # Adding automatically

    async def test_a_product_bought_twice_is_added_when_it_runs_out(self):
        await self.purchase("milk")
        await self.purchase("milk")

        added = await shopping.add_ran_out_products(self.db, {"milk"})

        self.assertEqual(added, ["milk"])
        self.assertEqual(await self.names(), [("Milk", "auto", False)])

    async def test_a_product_bought_once_is_not_added(self):
        await self.purchase("mustard")

        self.assertEqual(await shopping.add_ran_out_products(self.db, {"mustard"}), [])

    async def test_a_product_still_in_the_fridge_is_not_added(self):
        await self.purchase("milk")
        await self.purchase("milk", removed=False)

        self.assertEqual(await shopping.add_ran_out_products(self.db, {"milk"}), [])

    async def test_a_product_already_on_the_list_is_not_added_again(self):
        await self.purchase("milk")
        await self.purchase("milk")
        await shopping.add_manual(self.db, "חלב")

        self.assertEqual(await shopping.add_ran_out_products(self.db, {"milk"}), [])
        self.assertEqual(await self.names(), [("חלב", "manual", False)])

    # Order and clearing

    async def test_items_to_buy_come_before_bought_ones(self):
        first = await shopping.add_manual(self.db, "Bread")
        await shopping.add_manual(self.db, "Olive oil")
        await shopping.set_checked(self.db, first, True)

        self.assertEqual(await self.names(), [("Olive oil", "manual", False), ("Bread", "manual", True)])

    async def test_clear_checked_deletes_only_bought_items(self):
        bread = await shopping.add_manual(self.db, "Bread")
        await shopping.add_manual(self.db, "Olive oil")
        await shopping.set_checked(self.db, bread, True)

        self.assertEqual(await shopping.clear_checked(self.db), 1)
        self.assertEqual(await self.names(), [("Olive oil", "manual", False)])


if __name__ == "__main__":
    unittest.main()
