from datetime import datetime
from typing import Literal

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
