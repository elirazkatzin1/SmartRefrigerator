from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import DoorEvent, FridgeState, Inventory
from schemas import DoorStatusCreate, DoorStatusResponse, InventoryItemResponse

# Initializing the FastAPI application
app = FastAPI(title="VISION Smart Refrigerator API")

# Images are stored next to this file, so in Docker they land in backend/storage/images on the host
IMAGES_DIR = Path(__file__).parent / "storage" / "images"
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}
# The fridge is designed for 5 cameras (camera_id 1-5 in the firmware), even while fewer are installed
MAX_CAMERA_ID = 5
# generateEventId() in the firmware: 16 lowercase hex characters
EVENT_ID_PATTERN = r"^[0-9a-f]{16}$"
# There is one fridge, so fridge_state holds a single row
FRIDGE_STATE_ID = 1
# Expiration dates are local dates, so "today" is computed in Israel time, not the server's UTC
LOCAL_TZ = ZoneInfo("Asia/Jerusalem")

#בדיקה שהשרת רץ
@app.get("/")
async def root():
    return {"message": "VISION Smart Refrigerator API is running successfully!"}

#בדיקת תקינות health check
@app.get("/api/health")
async def health_check():
    # This matches the health check requirement for our first sprint task
    return {"status": "ok"}

#מקבל את מצב הדלת ושומר בטבלה door_events
@app.post("/api/v1/fridge/status", response_model=DoorStatusResponse, status_code=201)
async def update_door_status(status: DoorStatusCreate, db: AsyncSession = Depends(get_db)):
    event = DoorEvent(door_open=status.door_open, uptime_ms=status.uptime_ms)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    print(f"Door {'OPENED' if event.door_open else 'CLOSED'} (uptime {event.uptime_ms} ms)", flush=True)
    return event

#מקבל תמונה כmultipart ושומר אותה בתיקייה storage/images/<event_id>
@app.post("/api/v1/fridge/upload-image", status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    camera_id: int = Form(..., ge=1, le=MAX_CAMERA_ID),
    # The pattern also keeps the id safe to use as a directory name
    event_id: str = Form(..., pattern=EVENT_ID_PATTERN),
    db: AsyncSession = Depends(get_db),
):
    # Read the whole multipart body before responding, otherwise the connection
    # is closed while the camera is still sending and it gets "connection reset"
    image_bytes = await file.read()

    extension = ALLOWED_IMAGE_TYPES.get(file.content_type)
    if extension is None:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {file.content_type}")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    # All the cameras of one door-close event share a directory, one file per camera.
    # The camera always sends "fridge.jpg", so the name is built from camera_id instead
    taken_at = datetime.utcnow()
    event_dir = IMAGES_DIR / event_id
    filename = f"{event_id}/cam{camera_id}{extension}"
    event_dir.mkdir(parents=True, exist_ok=True)
    await run_in_threadpool((IMAGES_DIR / filename).write_bytes, image_bytes)

    # Only after the image is safely on disk, record it in the single fridge state row
    state = await db.get(FridgeState, FRIDGE_STATE_ID)
    if state is None:
        state = FridgeState(id=FRIDGE_STATE_ID)
        db.add(state)
    state.last_image_taken = taken_at
    await db.commit()

    print(f"Saved image: {filename}, {len(image_bytes)} bytes", flush=True)
    return {
        "message": "OK",
        "filename": filename,
        "camera_id": camera_id,
        "event_id": event_id,
        "size": len(image_bytes),
        "taken_at": taken_at,
    }

#מחזיר את כל המוצרים שנמצאים כרגע במקרר
@app.get("/api/v1/inventory", response_model=list[InventoryItemResponse])
async def get_inventory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Inventory).order_by(Inventory.added_at.desc()))
    return result.scalars().all()

#מחזיר מוצרים שתאריך התפוגה שלהם לפני היום
@app.get("/api/v1/inventory/expired", response_model=list[InventoryItemResponse])
async def get_expired_inventory(db: AsyncSession = Depends(get_db)):
    today = datetime.now(LOCAL_TZ).date()
    result = await db.execute(
        select(Inventory)
        .where(Inventory.expiration_date < today)
        .order_by(Inventory.expiration_date)
    )
    return result.scalars().all()
