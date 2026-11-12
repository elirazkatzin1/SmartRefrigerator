from enum import Enum
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, Date, DateTime, Float
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from database import Base

class InventorySource(str, Enum):
    # Detected by the camera pipeline, or added by the user in the app
    AI = "ai"
    MANUAL = "manual"

class ExpirationSource(str, Enum):
    # Read from the package, estimated from the category's shelf life, or entered by the user
    OCR = "ocr"
    ESTIMATED = "estimated"
    MANUAL = "manual"

class AnalysisStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, index=True, nullable=False)
    category = Column(String, index=True)
    expiration_date = Column(Date)
    added_at = Column(DateTime, default=datetime.utcnow)
    quantity = Column(Integer, nullable=False, default=1, server_default="1")
    # Detection confidence (0-1) from the last door event that saw it. None for manual entries
    confidence = Column(Float, nullable=True)
    # The last door event in which the cameras saw it
    last_seen_at = Column(DateTime, nullable=True)
    # An InventorySource value. Rows from before this column existed were added by hand
    source = Column(String, nullable=False, default=InventorySource.MANUAL.value,
                    server_default=InventorySource.MANUAL.value)
    # An ExpirationSource value, or None when there is no expiration_date
    expiration_source = Column(String, nullable=True)
    # Set when the product is taken out. Removed rows are kept for history and not shown as inventory
    removed_at = Column(DateTime, nullable=True, index=True)

class ImageAnalysis(Base):
    """One row per uploaded camera image and the result of running the vision pipeline on it."""
    __tablename__ = "image_analysis"

    id = Column(Integer, primary_key=True, index=True)
    # Path under storage/images, e.g. "a3f09c1e7b2d4410/cam1.jpg". Unique: a camera that re-sends
    # an image (its upload queue retries when no response arrived) overwrites the same file
    filename = Column(String, nullable=False, unique=True)
    camera_id = Column(Integer, nullable=False)
    # Groups the images of all cameras from one door-close event
    event_id = Column(String, nullable=False, index=True)
    # An AnalysisStatus value
    status = Column(String, nullable=False, default=AnalysisStatus.PENDING.value,
                    server_default=AnalysisStatus.PENDING.value, index=True)
    processing_time_ms = Column(Integer, nullable=True)
    # The vision.detector.Detection list as JSON objects (dataclasses.asdict):
    # [{"class_name": "milk", "category": "Dairy", "confidence": 0.93, "bbox": [x1, y1, x2, y2]}, ...]
    detections = Column(JSONB, nullable=True)
    # Why the analysis failed, for status = failed (e.g. a black or corrupted image)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class FridgeState(Base):
    __tablename__ = "fridge_state"

    id = Column(Integer, primary_key=True, index=True)
    is_online = Column(Boolean, default=True)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    last_image_taken = Column(DateTime, nullable=True)

class DoorEvent(Base):
    __tablename__ = "door_events"

    id = Column(Integer, primary_key=True, index=True)
    door_open = Column(Boolean, nullable=False)
    # millis() on the ESP32 is an unsigned 32-bit value, which overflows a signed Integer
    uptime_ms = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
