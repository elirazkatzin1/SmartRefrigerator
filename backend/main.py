from fastapi import FastAPI, File, UploadFile

# Initializing the FastAPI application
app = FastAPI(title="VISION Smart Refrigerator API")

@app.get("/")
async def root():
    return {"message": "VISION Smart Refrigerator API is running successfully!"}

@app.get("/api/health")
async def health_check():
    # This matches the health check requirement for our first sprint task
    return {"status": "ok"}

@app.post("/api/v1/fridge/status")
async def root():
    return {"message": "OK"}

@app.post("/api/v1/fridge/upload-image")
async def upload_image(file: UploadFile = File(...)):
    # Read the whole multipart body before responding, otherwise the connection
    # is closed while the camera is still sending and it gets "connection reset"
    image_bytes = await file.read()
    print(f"Received image: {file.filename}, {len(image_bytes)} bytes", flush=True)
    return {"message": "OK", "size": len(image_bytes)}

