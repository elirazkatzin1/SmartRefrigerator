from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analysis import analyze_upload
from database import get_db
from models import AnalysisStatus, DoorEvent, EventAnalysis, FridgeState, ImageAnalysis, Inventory
from schemas import DoorStatusCreate, DoorStatusResponse, EventAnalysisResponse, InventoryItemResponse
from vision import detector


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the YOLO weights once on startup, not on every request
    try:
        await run_in_threadpool(detector.load_model)
        print(f"Detector loaded from {detector.DETECTOR_WEIGHTS}", flush=True)
    except FileNotFoundError as error:
        # The server still starts without a trained model, so the cameras can keep uploading
        # images (which are needed to train one). Detection fails until the weights exist
        print(f"WARNING: {error}", flush=True)
    yield


# Initializing the FastAPI application
app = FastAPI(title="VISION Smart Refrigerator API", lifespan=lifespan)

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

#מקבל תמונה כmultipart, שומר אותה בתיקייה storage/images/<event_id> ומפעיל את הניתוח ברקע
@app.post("/api/v1/fridge/upload-image", status_code=201)
async def upload_image(
    background_tasks: BackgroundTasks,
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

    # A camera re-sends an image when no response arrived, which overwrote the file above,
    # so the existing row is analyzed again instead of adding a second one
    analysis = (await db.execute(select(ImageAnalysis).where(ImageAnalysis.filename == filename))).scalar_one_or_none()
    if analysis is None:
        analysis = ImageAnalysis(filename=filename, camera_id=camera_id, event_id=event_id)
        db.add(analysis)
    else:
        analysis.status = AnalysisStatus.PENDING.value
        analysis.detections = None
        analysis.error = None
    await db.commit()

    # Runs after the response is sent, so the camera gets 201 right away
    background_tasks.add_task(analyze_upload, analysis.id, str(IMAGES_DIR / filename))

    print(f"Saved image: {filename}, {len(image_bytes)} bytes", flush=True)
    return {
        "message": "OK",
        "filename": filename,
        "camera_id": camera_id,
        "event_id": event_id,
        "size": len(image_bytes),
        "taken_at": taken_at,
    }

#מחזיר את הניתוח של סגירת הדלת האחרונה: התמונות, מה זוהה ומה השתנה במלאי
@app.get("/api/v1/analysis/latest", response_model=EventAnalysisResponse)
async def get_latest_analysis(db: AsyncSession = Depends(get_db)):
    event = (await db.execute(
        select(EventAnalysis).order_by(EventAnalysis.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="No door event has been analyzed yet")
    images = (await db.execute(
        select(ImageAnalysis).where(ImageAnalysis.event_id == event.event_id).order_by(ImageAnalysis.camera_id)
    )).scalars().all()
    return EventAnalysisResponse(
        event_id=event.event_id,
        analyzed_at=event.created_at,
        camera_ids=event.camera_ids,
        timed_out=event.timed_out,
        images=images,
        detections=event.snapshot,
        changes=event.changes,
    )

#מחזיר את כל המוצרים שנמצאים כרגע במקרר
@app.get("/api/v1/inventory", response_model=list[InventoryItemResponse])
async def get_inventory(db: AsyncSession = Depends(get_db)):
    # Products that were taken out keep their row (removed_at is set) but are no longer inventory
    result = await db.execute(
        select(Inventory).where(Inventory.removed_at.is_(None)).order_by(Inventory.added_at.desc())
    )
    return result.scalars().all()

#מחזיר מוצרים שתאריך התפוגה שלהם לפני היום
@app.get("/api/v1/inventory/expired", response_model=list[InventoryItemResponse])
async def get_expired_inventory(db: AsyncSession = Depends(get_db)):
    today = datetime.now(LOCAL_TZ).date()
    result = await db.execute(
        select(Inventory)
        .where(Inventory.expiration_date < today, Inventory.removed_at.is_(None))
        .order_by(Inventory.expiration_date)
    )
    return result.scalars().all()
