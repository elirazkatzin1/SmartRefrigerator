from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
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

#מקבל תמונה כmultipart ושומר אותה בתיקייה storage/images
@app.post("/api/v1/fridge/upload-image", status_code=201)
async def upload_image(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    # Read the whole multipart body before responding, otherwise the connection
    # is closed while the camera is still sending and it gets "connection reset"
    image_bytes = await file.read()

    extension = ALLOWED_IMAGE_TYPES.get(file.content_type)
    if extension is None:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {file.content_type}")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    # The camera always sends "fridge.jpg", so build a unique name to avoid overwriting
    taken_at = datetime.utcnow()
    filename = f"{taken_at:%Y%m%d_%H%M%S}_{uuid4().hex[:8]}{extension}"
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    await run_in_threadpool((IMAGES_DIR / filename).write_bytes, image_bytes)

    # Only after the image is safely on disk, record it in the single fridge state row
    state = await db.get(FridgeState, FRIDGE_STATE_ID)
    if state is None:
        state = FridgeState(id=FRIDGE_STATE_ID)
        db.add(state)
    state.last_image_taken = taken_at
    await db.commit()

    print(f"Saved image: {filename}, {len(image_bytes)} bytes", flush=True)
    return {"message": "OK", "filename": filename, "size": len(image_bytes), "taken_at": taken_at}

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
