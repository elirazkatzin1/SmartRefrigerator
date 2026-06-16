from fastapi import FastAPI

# Initializing the FastAPI application
app = FastAPI(title="VISION Smart Refrigerator API")

@app.get("/")
async def root():
    return {"message": "VISION Smart Refrigerator API is running successfully!"}

@app.get("/api/health")
async def health_check():
    # This matches the health check requirement for our first sprint task
    return {"status": "ok"}