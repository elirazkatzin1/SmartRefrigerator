from fastapi import Depends, FastAPI, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import DoorEvent
from schemas import DoorStatusCreate, DoorStatusResponse

# Initializing the FastAPI application
app = FastAPI(title="VISION Smart Refrigerator API")

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

#מקבל תמונה כmultipart קורא ומדפיס את הגודל, לא שומר
@app.post("/api/v1/fridge/upload-image")
async def upload_image(file: UploadFile = File(...)):
    # Read the whole multipart body before responding, otherwise the connection
    # is closed while the camera is still sending and it gets "connection reset"
    image_bytes = await file.read()
    print(f"Received image: {file.filename}, {len(image_bytes)} bytes", flush=True)
    return {"message": "OK", "size": len(image_bytes)}

