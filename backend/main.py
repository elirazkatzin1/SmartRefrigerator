import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alerts import alert_hub
from analysis import analyze_upload, fail_interrupted_analyses
from database import get_db
from inventory.edit import InvalidEdit, apply_edit
from log import configure_logging, log
import shopping
from models import AnalysisStatus, DoorEvent, EventAnalysis, FridgeState, ImageAnalysis, Inventory, ShoppingItem
from schemas import (
    DoorStatusCreate,
    DoorStatusResponse,
    EventAnalysisResponse,
    FridgeStateResponse,
    InventoryItemResponse,
    InventoryItemUpdate,
    ShoppingItemCreate,
    ShoppingItemResponse,
    ShoppingItemUpdate,
)
from vision import detector
from vision.calibration import undistort
from vision.draw import draw_detections
from vision.errors import ImageRejectedError
from vision.preprocess import load_image

configure_logging()
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the YOLO weights once on startup, not on every request
    try:
        await run_in_threadpool(detector.load_model)
        log(logger, "detector loaded", weights=detector.DETECTOR_WEIGHTS)
    except FileNotFoundError as error:
        # The server still starts without a trained model, so the cameras can keep uploading
        # images (which are needed to train one). Detection fails until the weights exist
        log(logger, str(error), logging.WARNING)
    # Analyses a restart cut off would otherwise stay "processing" forever
    await fail_interrupted_analyses()
    # Resends the alerts periodically, so "N days in the fridge" alerts follow the date
    refresh_alerts = asyncio.create_task(alert_hub.refresh_forever())
    yield
    refresh_alerts.cancel()


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
# Folders are numbered in arrival order, "0001_<event_id>", so the highest number is the latest door event
EVENT_FOLDER_PATTERN = re.compile(r"^(\d+)_([0-9a-f]{16})$")
# The cameras of one event upload together: only one request at a time may pick the next number
_event_folder_lock = asyncio.Lock()


def _find_or_number_event_folder(event_id: str) -> str:
    """The event's folder name: the existing one, or the next number if this is its first image."""
    numbers = [0]
    for folder in IMAGES_DIR.iterdir() if IMAGES_DIR.exists() else []:
        match = EVENT_FOLDER_PATTERN.match(folder.name)
        if match:
            if match.group(2) == event_id:
                return folder.name
            numbers.append(int(match.group(1)))
    return f"{max(numbers) + 1:04d}_{event_id}"

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
    log(logger, "door opened" if event.door_open else "door closed", uptime_ms=event.uptime_ms)
    await alert_hub.door_changed(event.door_open)
    return event

#מקבל תמונה כmultipart, שומר אותה בתיקייה storage/images/<מספר>_<event_id> ומפעיל את הניתוח ברקע
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

    # All the cameras of one door-close event share a numbered directory, one file per camera.
    # The camera always sends "fridge.jpg", so the name is built from camera_id instead
    taken_at = datetime.utcnow()
    async with _event_folder_lock:
        folder = await run_in_threadpool(_find_or_number_event_folder, event_id)
        (IMAGES_DIR / folder).mkdir(parents=True, exist_ok=True)
    filename = f"{folder}/cam{camera_id}{extension}"
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

    log(logger, "image uploaded", event_id=event_id, camera_id=camera_id, bytes=len(image_bytes))
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
        error=event.error,
    )

def _annotated_jpeg(path: Path, camera_id: int, detections: list[dict]) -> bytes:
    # The boxes are in the coordinates of the lens-corrected image the detector saw
    image = undistort(load_image(path), camera_id)
    ok, encoded = cv2.imencode(".jpg", draw_detections(image, detections), [cv2.IMWRITE_JPEG_QUALITY, 90])
    return encoded.tobytes()

#מחזיר את התמונה עם המלבנים והשמות של מה שזוהה בה
@app.get("/api/v1/analysis/{analysis_id}/image", response_class=Response,
         responses={200: {"content": {"image/jpeg": {}}}})
async def get_analysis_image(analysis_id: int, db: AsyncSession = Depends(get_db)):
    analysis = await db.get(ImageAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"No image analysis with id {analysis_id}")
    path = IMAGES_DIR / analysis.filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Image file {analysis.filename} no longer exists")
    try:
        # Decoding and drawing are CPU work, so they run off the event loop
        jpeg = await run_in_threadpool(_annotated_jpeg, path, analysis.camera_id, analysis.detections or [])
    except ImageRejectedError:
        # A black or corrupted image (its analysis failed): there is nothing to draw on, return it as is
        jpeg = await run_in_threadpool(path.read_bytes)
    return Response(content=jpeg, media_type="image/jpeg")

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

#עריכה ידנית של מוצר מהאפליקציה: תאריך הכנסה, קטגוריה, כמות
@app.patch("/api/v1/inventory/{item_id}", response_model=InventoryItemResponse)
async def edit_inventory_item(item_id: int, update: InventoryItemUpdate, db: AsyncSession = Depends(get_db)):
    row = await db.get(Inventory, item_id)
    # A removed product is history, not inventory, so it can't be edited either
    if row is None or row.removed_at is not None:
        raise HTTPException(status_code=404, detail="Item not found")
    try:
        apply_edit(row, update, datetime.now(LOCAL_TZ).date())
    except InvalidEdit as error:
        raise HTTPException(status_code=422, detail=str(error))
    await db.commit()
    await db.refresh(row)
    log(logger, "inventory item edited", item_id=item_id, **update.model_dump(exclude_none=True, mode="json"))
    # A new expiration date can add or clear an expiry alert
    await alert_hub.broadcast()
    return row

#התראות בזמן אמת לאפליקציה: בכל שינוי נשלחת כל רשימת ההתראות הפעילות
@app.websocket("/api/v1/ws/alerts")
async def alerts_socket(websocket: WebSocket):
    await alert_hub.connect(websocket)
    try:
        # The app sends nothing; waiting for a message is how the server notices it disconnected
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        alert_hub.disconnect(websocket)

#מצב המקרר למסך ההגדרות: אירוע הדלת האחרון, התמונה האחרונה ומצלמות שלא שלחו תמונה
@app.get("/api/v1/fridge/state", response_model=FridgeStateResponse)
async def get_fridge_state(db: AsyncSession = Depends(get_db)):
    last_door = (await db.execute(select(DoorEvent).order_by(DoorEvent.created_at.desc()).limit(1))).scalar_one_or_none()
    state = await db.get(FridgeState, FRIDGE_STATE_ID)
    return FridgeStateResponse(
        door_open=last_door.door_open if last_door else None,
        last_door_event_at=last_door.created_at if last_door else None,
        last_image_at=state.last_image_taken if state else None,
        expected_cameras=alert_hub.expected_cameras,
        offline_cameras=alert_hub.offline_cameras(),
    )

#רשימת הקניות: קודם מה שעוד צריך לקנות, אחר כך מה שכבר נקנה
@app.get("/api/v1/shopping-list", response_model=list[ShoppingItemResponse])
async def get_shopping_list(db: AsyncSession = Depends(get_db)):
    return await shopping.list_items(db)

#הוספת פריט שהמשתמש הקליד
@app.post("/api/v1/shopping-list", response_model=ShoppingItemResponse, status_code=201)
async def add_shopping_item(item: ShoppingItemCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await shopping.add_manual(db, item.name)
    except shopping.DuplicateItem as error:
        raise HTTPException(status_code=409, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

#מחיקת כל מה שסומן כנקנה. מוגדר לפני /{item_id}, אחרת "checked" היה נקרא כמזהה
@app.delete("/api/v1/shopping-list/checked", status_code=204)
async def clear_bought_items(db: AsyncSession = Depends(get_db)):
    await shopping.clear_checked(db)

#סימון פריט כנקנה (או ביטול הסימון)
@app.patch("/api/v1/shopping-list/{item_id}", response_model=ShoppingItemResponse)
async def update_shopping_item(item_id: int, update: ShoppingItemUpdate, db: AsyncSession = Depends(get_db)):
    item = await db.get(ShoppingItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return await shopping.set_checked(db, item, update.checked)

#מחיקת פריט מהרשימה
@app.delete("/api/v1/shopping-list/{item_id}", status_code=204)
async def delete_shopping_item(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(ShoppingItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()

#דף בדיקה למפתחים: מציג את ההתראות בזמן אמת ומאפשר להפעיל אירועים (דלת, זמן במקרר)
@app.get("/dev/alerts", include_in_schema=False)
async def alerts_test_page():
    return FileResponse(Path(__file__).parent / "dev" / "alerts.html")
