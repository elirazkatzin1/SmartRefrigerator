from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from vision.products import Category


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


class InventoryItemUpdate(BaseModel):
    """PATCH /api/v1/inventory/{id}: the fields the user can fix in the app. Omitted fields stay as they are."""
    model_config = ConfigDict(extra="forbid")

    # The local (Israel) day the product was put in the fridge; the app shows "N days in fridge" from it
    added_on: Optional[date] = None
    # The date printed on the package. Stored as a manual expiration, which no estimate overwrites
    expiration_date: Optional[date] = None
    category: Optional[Category] = None
    quantity: Optional[int] = Field(default=None, ge=1)


class ShoppingItemCreate(BaseModel):
    """POST /api/v1/shopping-list: an item the user typed."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=60)


class ShoppingItemUpdate(BaseModel):
    """PATCH /api/v1/shopping-list/{id}: check an item off as bought, or back."""
    model_config = ConfigDict(extra="forbid")

    checked: bool


class ShoppingItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    product_name: Optional[str] = None
    source: Literal["manual", "auto"]
    checked: bool
    created_at: datetime


class FridgeStateResponse(BaseModel):
    """GET /api/v1/fridge/state: what the server last heard from the fridge, for the Settings screen (SR-95).
    The cameras send no heartbeat, so their latest activity is the best sign that they work."""
    # The latest door status the fridge sent, and when (UTC). None before the first one
    door_open: Optional[bool] = None
    last_door_event_at: Optional[datetime] = None
    # When the latest camera photo arrived (UTC)
    last_image_at: Optional[datetime] = None
    expected_cameras: int
    # Cameras whose photo was missing from the last door event
    offline_cameras: list[int]
