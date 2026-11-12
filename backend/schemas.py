from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class DoorStatusCreate(BaseModel):
    # Matches the JSON body sent by the ESP32-CAM firmware (sendDoorStatus)
    event: Literal["door"] = "door"
    door_open: bool
    uptime_ms: int = Field(ge=0, description="Device uptime (millis()) when the event occurred")


class DoorStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    door_open: bool
    uptime_ms: int
    created_at: datetime


class DetectionResponse(BaseModel):
    class_name: str
    category: Optional[str] = None
    confidence: float
    # Pixels: top-left (x1, y1), bottom-right (x2, y2)
    bbox: list[int]


class ImageAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    filename: str
    status: Literal["pending", "processing", "done", "failed"]
    processing_time_ms: Optional[int] = None
    detections: Optional[list[DetectionResponse]] = None
    error: Optional[str] = None


class SnapshotItemResponse(BaseModel):
    product_name: str
    category: Optional[str] = None
    quantity: int
    confidence: float
    camera_ids: list[int]


class InventoryChangeResponse(BaseModel):
    product_name: str
    # removed: taken out of the inventory; missing: not seen this time, kept since it may be hidden
    change: Literal["added", "quantity_changed", "removed", "missing"]
    old_quantity: int
    new_quantity: int


class EventAnalysisResponse(BaseModel):
    event_id: str
    analyzed_at: datetime
    camera_ids: list[int]
    timed_out: bool
    images: list[ImageAnalysisResponse]
    # The merged detections of all cameras: one item per product
    detections: list[SnapshotItemResponse]
    changes: list[InventoryChangeResponse]
    # Set when updating the inventory failed: it was left unchanged, and detections/changes are empty
    error: Optional[str] = None


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_name: str
    category: Optional[str] = None
    expiration_date: Optional[date] = None
    added_at: datetime
    quantity: int
    confidence: Optional[float] = None
    last_seen_at: Optional[datetime] = None
    source: Literal["ai", "manual"]
    expiration_source: Optional[Literal["ocr", "estimated", "manual"]] = None
    removed_at: Optional[datetime] = None
