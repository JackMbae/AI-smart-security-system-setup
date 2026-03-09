"""
AI Smart Security System - Main Application Entry Point
"""
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse
from loguru import logger
import sys
import os

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add("logs/security.log", rotation="10 MB", retention="30 days", level="DEBUG")

os.makedirs("logs", exist_ok=True)
os.makedirs("known_faces", exist_ok=True)
os.makedirs("events", exist_ok=True)

from config.settings import settings
from config.database import init_db, get_db
from api.pipeline_manager import pipeline_manager
from api.websocket import ws_manager
from api.routes.cameras import router as camera_router
from api.routes.events import router as events_router
from api.routes.faces import router as faces_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown"""
    logger.info("=" * 60)
    logger.info(f"  {settings.APP_NAME} v{settings.VERSION}")
    logger.info("=" * 60)
    
    # Initialize database
    await init_db()
    logger.success("Database initialized")
    
    # Register event broadcast via WebSocket
    def broadcast_event(event):
        event_data = {
            "event_type": event.event_type,
            "camera_name": event.camera_name,
            "severity": event.severity,
            "description": event.description,
            "timestamp": event.timestamp.isoformat(),
            "person_name": event.person_name,
            "zone_name": event.zone_name,
        }
        asyncio.create_task(ws_manager.broadcast_event(event_data))
    
    pipeline_manager.on_event(broadcast_event)
    
    # Start all enabled cameras from DB
    async for db in get_db():
        await pipeline_manager.start_all_from_db(db)
        break
    
    # Start frame streaming task
    asyncio.create_task(frame_broadcast_loop())
    
    logger.success("System ready!")
    yield
    
    # Shutdown
    logger.info("Shutting down pipelines...")
    pipeline_manager.stop_all()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Production-grade AI Smart Security System",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(camera_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(faces_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "cameras_active": len(pipeline_manager.pipelines),
    }


@app.get("/api/v1/system/status")
async def system_status():
    """System health and pipeline status"""
    import psutil
    return {
        "pipelines": pipeline_manager.get_all_status(),
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "websocket_connections": len(ws_manager.active_connections),
    }


@app.get("/api/v1/stream/{camera_id}/snapshot")
async def get_snapshot(camera_id: int):
    """Get single JPEG snapshot from camera"""
    jpeg = pipeline_manager.get_frame_jpeg(camera_id)
    if not jpeg:
        return JSONResponse(status_code=404, content={"detail": "No frame available"})
    
    return StreamingResponse(
        iter([jpeg]),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"}
    )


@app.get("/api/v1/stream/{camera_id}/mjpeg")
async def mjpeg_stream(camera_id: int):
    """MJPEG stream for live video"""
    async def generate():
        while True:
            jpeg = pipeline_manager.get_frame_jpeg(camera_id)
            if jpeg:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                )
            await asyncio.sleep(0.067)  # ~15 FPS
    
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"},
    )


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket endpoint for real-time event updates"""
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.websocket("/ws/stream/{camera_id}")
async def websocket_stream(websocket: WebSocket, camera_id: int):
    """WebSocket endpoint for live camera feed"""
    await ws_manager.connect(websocket, camera_id=camera_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


async def frame_broadcast_loop():
    """Periodically broadcast frames to WebSocket subscribers"""
    while True:
        for camera_id, pipeline in pipeline_manager.pipelines.items():
            subs = ws_manager.camera_subscribers.get(camera_id, set())
            if subs:
                jpeg = pipeline.get_frame_jpeg()
                if jpeg:
                    await ws_manager.send_frame(camera_id, jpeg)
        await asyncio.sleep(0.1)  # 10 FPS to websocket


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
