"""Door-event scenarios through the whole inventory update: merge -> diff -> quantities -> removals.

These run against a separate PostgreSQL database, fridge_inventory_test, on the same server as the
app's database (created if missing, emptied after every test), so the app's data is never touched.
Run with the database up:
    docker compose up -d db
    docker compose run --rm web python -m unittest discover tests
Without a reachable database these tests are skipped.
"""
import asyncio
import os
import unittest
from dataclasses import asdict
from datetime import datetime, timedelta

import asyncpg
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url

from database import Base
from inventory.diff import current_quantities, diff_inventory
from inventory.merge import build_snapshot, merge_detections
from inventory.update import apply_quantities, apply_removals
from models import AnalysisStatus, ImageAnalysis, Inventory, InventorySource

APP_DATABASE_URL = make_url(os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/fridge_inventory"))
TEST_DATABASE_URL = APP_DATABASE_URL.set(database=f"{APP_DATABASE_URL.database}_test")
# Set by the first test that can't reach the database, so the others skip without waiting again
_database_error: str | None = None


async def ensure_test_database() -> None:
    # CREATE DATABASE can't run inside a transaction, so this uses a plain asyncpg connection
    server = APP_DATABASE_URL.set(drivername="postgresql", database="postgres")
    connection = await asyncpg.connect(server.render_as_string(hide_password=False), timeout=5)
    try:
        exists = await connection.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DATABASE_URL.database)
        if not exists:
            await connection.execute(f'CREATE DATABASE "{TEST_DATABASE_URL.database}"')
    finally:
        await connection.close()


def detection(class_name: str, confidence: float = 0.9) -> dict:
    return {"class_name": class_name, "category": None, "confidence": confidence, "bbox": [0, 0, 10, 10]}


class InventoryFlowTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        global _database_error
        if _database_error is None:
            try:
                await ensure_test_database()
            # On Python 3.10 asyncio.TimeoutError is not the built-in TimeoutError
            except (OSError, asyncio.TimeoutError, asyncpg.PostgresError) as error:
                _database_error = str(error) or type(error).__name__
        if _database_error:
            self.skipTest(f"test database not reachable: {_database_error}")
        self.engine = create_async_engine(TEST_DATABASE_URL)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        self.db = async_sessionmaker(self.engine, expire_on_commit=False)()
        self.event_time = datetime(2026, 11, 12, 12, 0)

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()

    async def door_event(self, detections_by_camera: dict[int, list[dict]]) -> dict[str, int]:
        """Run one door event through the update and return the quantity of each product after it."""
        self.event_time += timedelta(minutes=10)
        snapshot = merge_detections(detections_by_camera)
        changes = diff_inventory(snapshot, await current_quantities(self.db))
        await apply_quantities(self.db, snapshot, changes, self.event_time)
        await apply_removals(self.db, changes, self.event_time)
        await self.db.commit()
        return dict(await current_quantities(self.db))

    async def add_row(self, name: str, quantity: int = 1, source: InventorySource = InventorySource.AI, **fields):
        self.db.add(Inventory(product_name=name, quantity=quantity, source=source.value, **fields))
        await self.db.commit()

    # Adding

    async def test_new_product_is_added(self):
        self.assertEqual(await self.door_event({1: [detection("milk")]}), {"milk": 1})

        row = (await self.db.execute(select(Inventory))).scalar_one()
        self.assertEqual((row.source, row.category, row.confidence), ("ai", "Dairy", 0.9))
        self.assertEqual(row.last_seen_at, self.event_time)

    async def test_empty_fridge_stays_empty(self):
        self.assertEqual(await self.door_event({1: [], 2: []}), {})

    # Quantity changes

    async def test_quantity_follows_the_detected_count(self):
        self.assertEqual(await self.door_event({1: [detection("yogurt")] * 3}), {"yogurt": 3})
        self.assertEqual(await self.door_event({1: [detection("yogurt")] * 2}), {"yogurt": 2})
        self.assertEqual(await self.door_event({1: [detection("yogurt")] * 4}), {"yogurt": 4})

    async def test_fewer_items_are_taken_from_the_earliest_expiration(self):
        await self.add_row("yogurt", 2, expiration_date=datetime(2026, 11, 30).date())
        await self.add_row("yogurt", 1, expiration_date=datetime(2026, 11, 20).date())

        await self.door_event({1: [detection("yogurt")] * 2})

        remaining = (await self.db.execute(select(Inventory).where(Inventory.removed_at.is_(None)))).scalars().all()
        self.assertEqual([(row.quantity, str(row.expiration_date)) for row in remaining], [(2, "2026-11-30")])

    # Removing and hidden products

    async def test_product_is_removed_after_two_events_without_it(self):
        await self.door_event({1: [detection("milk"), detection("lemon")]})

        self.assertEqual(await self.door_event({1: [detection("lemon")]}), {"milk": 1, "lemon": 1})
        self.assertEqual(await self.door_event({1: [detection("lemon")]}), {"lemon": 1})

        removed = (await self.db.execute(select(Inventory).where(Inventory.product_name == "milk"))).scalar_one()
        self.assertEqual(removed.removed_at, self.event_time)

    async def test_hidden_product_that_reappears_is_kept(self):
        await self.door_event({1: [detection("milk")]})

        await self.door_event({1: []})  # hidden behind another product
        self.assertEqual(await self.door_event({1: [detection("milk")]}), {"milk": 1})
        await self.door_event({1: []})  # hidden again: the count started over
        self.assertEqual(await current_quantities(self.db), {"milk": 1})

    async def test_removed_product_bought_again_is_a_new_row(self):
        await self.door_event({1: [detection("milk")]})
        await self.door_event({1: []})
        await self.door_event({1: []})

        self.assertEqual(await self.door_event({1: [detection("milk")]}), {"milk": 1})
        rows = (await self.db.execute(select(Inventory).order_by(Inventory.id))).scalars().all()
        self.assertEqual([row.removed_at is None for row in rows], [False, True])

    # Several cameras

    async def test_product_seen_by_several_cameras_is_counted_once(self):
        quantities = await self.door_event({1: [detection("milk")], 2: [detection("milk")], 3: [detection("milk")]})

        self.assertEqual(quantities, {"milk": 1})

    async def test_cameras_see_different_products(self):
        quantities = await self.door_event({
            1: [detection("milk"), detection("yogurt"), detection("yogurt")],
            2: [detection("yogurt"), detection("yogurt"), detection("yogurt"), detection("carrot")],
        })

        self.assertEqual(quantities, {"milk": 1, "yogurt": 3, "carrot": 1})

    async def test_product_seen_by_one_camera_only_is_not_missing(self):
        await self.door_event({1: [detection("milk")], 2: [detection("lemon")]})

        # Camera 1 no longer sees the milk, but camera 2 now does
        self.assertEqual(await self.door_event({1: [detection("lemon")], 2: [detection("milk")]}),
                         {"milk": 1, "lemon": 1})

    # A missing camera image

    async def test_failed_camera_image_is_left_out_of_the_snapshot(self):
        self.db.add_all([
            ImageAnalysis(filename="e1/cam1.jpg", camera_id=1, event_id="e1", status=AnalysisStatus.DONE.value,
                          detections=[detection("milk")]),
            ImageAnalysis(filename="e1/cam2.jpg", camera_id=2, event_id="e1", status=AnalysisStatus.FAILED.value,
                          error="black image"),
        ])
        await self.db.commit()

        snapshot = await build_snapshot(self.db, "e1")

        self.assertEqual(set(snapshot), {"milk"})
        self.assertEqual(snapshot["milk"].camera_ids, {1})

    async def test_event_with_a_camera_missing_keeps_what_only_that_camera_saw(self):
        await self.door_event({1: [detection("milk")], 2: [detection("lemon")]})

        # Camera 2's image never arrived: the lemon only it sees counts as one miss, not a removal
        self.assertEqual(await self.door_event({1: [detection("milk")]}), {"milk": 1, "lemon": 1})

    # Manual entries

    async def test_manual_entry_is_never_removed(self):
        await self.add_row("jam", source=InventorySource.MANUAL)

        for _ in range(3):
            await self.door_event({1: []})

        self.assertEqual(await current_quantities(self.db), {"jam": 1})

    async def test_lower_count_is_taken_only_from_camera_rows(self):
        await self.add_row("milk", source=InventorySource.MANUAL)
        await self.door_event({1: [detection("milk")] * 3})  # 1 manual + 2 detected

        self.assertEqual(await self.door_event({1: [detection("milk")]}), {"milk": 1})
        remaining = (await self.db.execute(select(Inventory).where(Inventory.removed_at.is_(None)))).scalar_one()
        self.assertEqual(remaining.source, "manual")


if __name__ == "__main__":
    unittest.main()
