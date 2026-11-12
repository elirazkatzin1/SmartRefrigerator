"""A failing step must mark the analysis failed and leave the inventory unchanged, without crashing.

Runs against the test database, like test_inventory_flow (skipped when it isn't reachable):
    docker compose run --rm web python -m unittest discover tests
"""
import unittest
from unittest import mock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import analysis
import test_inventory_flow
from database import Base
from inventory.event_collector import ReadyEvent
from models import AnalysisStatus, EventAnalysis, ImageAnalysis, Inventory
from test_inventory_flow import TEST_DATABASE_URL, detection, ensure_test_database


class PipelineFailureTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if test_inventory_flow._database_error is None:
            try:
                await ensure_test_database()
            except Exception as error:
                test_inventory_flow._database_error = str(error) or type(error).__name__
        if test_inventory_flow._database_error:
            self.skipTest(f"test database not reachable: {test_inventory_flow._database_error}")

        self.engine = create_async_engine(TEST_DATABASE_URL)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        # The pipeline opens its own sessions; point them at the test database
        patcher = mock.patch.object(analysis, "AsyncSessionLocal", sessions)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.db = sessions()
        self.analyzed = []

        async def image_analyzed(event_id, camera_id):
            self.analyzed.append((event_id, camera_id))

        collector = mock.patch.object(analysis.collector, "image_analyzed", image_analyzed)
        collector.start()
        self.addCleanup(collector.stop)

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()

    async def add_analysis(self, camera_id=1, status=AnalysisStatus.PENDING, detections=None) -> ImageAnalysis:
        row = ImageAnalysis(filename=f"e1/cam{camera_id}.jpg", camera_id=camera_id, event_id="e1",
                            status=status.value, detections=detections)
        self.db.add(row)
        await self.db.commit()
        return row

    # Image analysis

    async def test_unexpected_error_marks_the_analysis_failed(self):
        row = await self.add_analysis()

        with mock.patch.object(analysis, "analyze_image", side_effect=RuntimeError("model crashed")), \
                self.assertLogs("analysis", level="ERROR"):
            await analysis.analyze_upload(row.id, "/nowhere.jpg")

        await self.db.refresh(row)
        self.assertEqual((row.status, row.error), ("failed", "RuntimeError: model crashed"))
        # The event still goes on with the other cameras
        self.assertEqual(self.analyzed, [("e1", 1)])

    async def test_missing_model_marks_the_analysis_failed(self):
        row = await self.add_analysis()

        with mock.patch.object(analysis, "analyze_image", side_effect=FileNotFoundError("No trained model")), \
                self.assertLogs("analysis", level="ERROR"):
            await analysis.analyze_upload(row.id, "/nowhere.jpg")

        await self.db.refresh(row)
        self.assertEqual(row.status, "failed")
        self.assertIn("No trained model", row.error)

    async def test_analysis_that_cannot_be_recorded_does_not_raise(self):
        # No such row: the task logs and returns instead of raising into the server
        with self.assertLogs("analysis", level="ERROR"):
            await analysis.analyze_upload(999, "/nowhere.jpg")

        self.assertEqual(self.analyzed, [])

    # Inventory update

    async def test_failed_update_leaves_the_inventory_unchanged(self):
        self.db.add(Inventory(product_name="milk", quantity=1, source="ai"))
        await self.db.commit()
        await self.add_analysis(status=AnalysisStatus.DONE, detections=[detection("carrot")])

        # Fails after the quantities were already changed in the session (carrot added)
        with mock.patch.object(analysis, "apply_removals", side_effect=RuntimeError("database lost")), \
                self.assertLogs("analysis", level="ERROR"):
            await analysis.sync_event(ReadyEvent("e1", {1}, timed_out=False))

        rows = (await self.db.execute(select(Inventory))).scalars().all()
        self.assertEqual([(row.product_name, row.quantity, row.missed_events) for row in rows], [("milk", 1, 0)])
        event = (await self.db.execute(select(EventAnalysis))).scalar_one()
        self.assertEqual((event.error, event.changes), ("RuntimeError: database lost", []))

    async def test_successful_update_has_no_error(self):
        await self.add_analysis(status=AnalysisStatus.DONE, detections=[detection("carrot")])

        await analysis.sync_event(ReadyEvent("e1", {1}, timed_out=False))

        event = (await self.db.execute(select(EventAnalysis))).scalar_one()
        self.assertIsNone(event.error)
        self.assertEqual(event.changes[0]["change"], "added")

    # Server restart

    async def test_restart_fails_unfinished_analyses(self):
        pending = await self.add_analysis(camera_id=1, status=AnalysisStatus.PENDING)
        processing = await self.add_analysis(camera_id=2, status=AnalysisStatus.PROCESSING)
        done = await self.add_analysis(camera_id=3, status=AnalysisStatus.DONE, detections=[])

        with self.assertLogs("analysis", level="WARNING"):
            await analysis.fail_interrupted_analyses()

        for row in (pending, processing, done):
            await self.db.refresh(row)
        self.assertEqual([pending.status, processing.status, done.status], ["failed", "failed", "done"])
        self.assertIn("restarted", pending.error)


if __name__ == "__main__":
    unittest.main()
