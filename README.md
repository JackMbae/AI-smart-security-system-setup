# 🛡️ AI Smart Security System

A production-grade, open-source smart security system inspired by Ring and Hikvision — built entirely in Python using state-of-the-art AI models.

---

## ✨ Features

| Feature | Technology |
|---------|-----------|
| Object Detection | YOLOv8 (persons, vehicles, packages, animals) |
| Multi-Object Tracking | DeepSORT (persistent IDs across frames) |
| Face Recognition | face_recognition + dlib |
| Behavioral AI | Loitering, door interaction, intrusion |
| Zone Detection | Polygon-based zones (door, restricted, driveway) |
| Multi-Camera | Unlimited RTSP streams |
| Real-Time Alerts | Telegram, Email (SendGrid), Webhook |
| Evidence Storage | Snapshots + video clips, dated directories |
| Web Dashboard | React, live feeds, event timeline |
| Backend API | FastAPI + PostgreSQL + Redis |
| Containerized | Docker Compose |

---

## 🚀 Quick Start

### Option A: Docker (Recommended)

```bash
# Clone and configure
git clone <repo>
cd ai-security-system
cp .env.example .env
# Edit .env with your Telegram token, email config, etc.

# Build and start
docker-compose up --build

# Access
# Dashboard: http://localhost:3000
# API docs:  http://localhost:8000/docs
```

### Option B: Local Development

```bash
# Install dependencies
bash install.sh

# Start infrastructure
docker-compose up -d postgres redis

# Activate venv and run
source venv/bin/activate
python main.py

# Or run demo with webcam
python demo.py 0

# Or test with a video file
python demo.py /path/to/video.mp4
```

---

## 📷 Adding Cameras

### Via Dashboard
1. Open http://localhost:3000
2. Go to Cameras → Add Camera
3. Enter name, RTSP URL, location
4. Draw detection zones

### Via API
```bash
curl -X POST http://localhost:8000/api/v1/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Front Door",
    "stream_url": "rtsp://admin:password@192.168.1.100:554/stream",
    "location": "Main Entrance",
    "zones": [],
    "door_zone": {
      "name": "Door",
      "points": [[400,200],[800,200],[800,600],[400,600]],
      "zone_type": "door"
    }
  }'
```

---

## 👤 Adding Known Faces

### Via Dashboard
1. Go to Known Faces
2. Upload a clear photo
3. Enter name and role

### Via Directory
Drop photos in `known_faces/`:
```
known_faces/
  john_smith.jpg
  jane_doe.jpg
  employee_bob.jpg
```

### Via API
```bash
curl -X POST http://localhost:8000/api/v1/faces \
  -F "name=John Smith" \
  -F "role=family" \
  -F "image=@john.jpg"
```

---

## ⚙️ Configuration

Edit `.env`:

```env
# AI Models
YOLO_MODEL=yolov8n.pt          # nano=fastest, s/m/l/x=larger
YOLO_CONFIDENCE=0.45
FACE_RECOGNITION_MODEL=hog     # hog (CPU) or cnn (GPU)

# Behavioral Rules
LOITERING_THRESHOLD_SECONDS=15
NIGHT_HOURS_START=22
NIGHT_HOURS_END=6

# Telegram Alerts
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_CHAT_ID=your-chat-id

# Email
SENDGRID_API_KEY=your-key
ALERT_EMAIL_FROM=security@domain.com
ALERT_EMAIL_TO=you@domain.com

# Performance
FRAME_SKIP=2                   # process every Nth frame
ALERT_COOLDOWN_SECONDS=60      # min seconds between same-type alerts
```

---

## 🗺️ Zone Configuration

Zones are defined as polygons in pixel coordinates:

```json
{
  "name": "Front Door",
  "points": [[350, 200], [750, 200], [750, 580], [350, 580]],
  "zone_type": "door",
  "alert_on_entry": true,
  "alert_on_loitering": true,
  "loitering_threshold": 15
}
```

**Zone types:**
- `door` — triggers unknown person alerts
- `restricted` — triggers intrusion alerts (critical)
- `driveway` — vehicle monitoring
- `detection` — general activity monitoring

---

## 📡 API Reference

```
GET  /api/v1/cameras              # List cameras
POST /api/v1/cameras              # Add camera
GET  /api/v1/cameras/{id}/status  # Pipeline status

GET  /api/v1/events               # List events (filterable)
GET  /api/v1/events/stats/summary # Event statistics
PATCH /api/v1/events/{id}/acknowledge

GET  /api/v1/faces                # List known persons
POST /api/v1/faces                # Add person with photo
DELETE /api/v1/faces/{id}

GET  /api/v1/stream/{id}/mjpeg    # MJPEG live stream
GET  /api/v1/stream/{id}/snapshot # Single frame

WS   /ws/events                   # Real-time event stream
WS   /ws/stream/{id}              # Live video WebSocket

GET  /api/v1/system/status        # System health
```

---

## 🖥️ Edge Deployment (Jetson)

```bash
# Use GPU-optimized settings
YOLO_MODEL=yolov8n.pt
FACE_RECOGNITION_MODEL=cnn
FRAME_SKIP=1

# Install CUDA-enabled packages
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# TensorRT optimization (optional)
yolo export model=yolov8n.pt format=engine device=0
```

---

## 📁 Project Structure

```
ai-security-system/
├── main.py                     # FastAPI application entry point
├── demo.py                     # Local demo script
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── nginx.conf
├── .env.example
│
├── config/
│   ├── settings.py             # Pydantic settings
│   └── database.py             # SQLAlchemy async engine
│
├── cameras/
│   ├── stream_manager.py       # RTSP stream management
│   └── pipeline.py             # Per-camera AI pipeline
│
├── detection/
│   └── yolo_detector.py        # YOLOv8 inference
│
├── tracking/
│   └── deepsort_tracker.py     # DeepSORT multi-object tracking
│
├── recognition/
│   └── face_recognizer.py      # Face recognition system
│
├── zones/
│   └── zone_manager.py         # Polygon zone detection
│
├── events/
│   └── event_engine.py         # Rule-based event generation
│
├── alerts/
│   └── notifier.py             # Telegram, Email, Webhook alerts
│
├── storage/
│   └── evidence_store.py       # Snapshot and clip storage
│
├── api/
│   ├── models.py               # SQLAlchemy database models
│   ├── pipeline_manager.py     # Global pipeline orchestration
│   ├── websocket.py            # WebSocket connection manager
│   └── routes/
│       ├── cameras.py          # Camera CRUD API
│       ├── events.py           # Events query API
│       └── faces.py            # Face management API
│
├── dashboard/                  # React web dashboard
│   ├── src/App.jsx
│   ├── package.json
│   └── Dockerfile
│
├── docs/
│   └── ARCHITECTURE.md
│
├── known_faces/                # Add face photos here
└── events/                     # Auto-created evidence storage
```

---

## 🔧 Troubleshooting

**Camera won't connect:**
```bash
# Test RTSP stream
ffplay rtsp://user:pass@ip:554/stream
vlc rtsp://user:pass@ip:554/stream
```

**Low FPS:**
- Use `yolov8n.pt` (nano model)
- Increase `FRAME_SKIP` in .env
- Enable GPU: install CUDA + torch with CUDA

**Face not recognized:**
- Use clear, well-lit frontal photos
- Adjust `FACE_RECOGNITION_TOLERANCE` (lower = stricter)
- Use `FACE_RECOGNITION_MODEL=cnn` for better accuracy (GPU needed)

**Alerts not sending:**
- Check Telegram token and chat ID
- Verify bot has been started (`/start` in Telegram)
- Check `ALERT_COOLDOWN_SECONDS` (default 60s between same alerts)

---

## 📄 License

MIT License — Free to use, modify, and deploy.
