# AI Smart Security System - Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     AI Smart Security System                      │
└──────────────────────────────────────────────────────────────────┘

┌─────────────┐   RTSP    ┌──────────────┐
│  IP Cameras │──────────►│    Stream    │
│  (Multiple) │           │   Manager   │
└─────────────┘           └──────┬───────┘
                                 │  frames
                                 ▼
               ┌─────────────────────────────────────┐
               │       Per-Camera AI Pipeline        │
               │                                     │
               │  YOLOv8 Detection                   │
               │       │                             │
               │       ▼                             │
               │  DeepSORT Tracker ──► Zone Manager  │
               │       │                    │        │
               │       ▼                    │        │
               │  Face Recognizer           │        │
               │       │                    │        │
               │       └──────────┬─────────┘        │
               │                  ▼                  │
               │          Event Engine               │
               └──────────────┬──────────────────────┘
                              │ events
              ┌───────────────▼─────────────────────┐
              │         FastAPI Backend              │
              │   REST API | WebSocket | MJPEG       │
              └──┬──────────┬────────────┬───────────┘
                 │          │            │
          ┌──────▼──┐  ┌────▼────┐  ┌───▼────────┐
          │Postgres │  │  React  │  │  Alerts    │
          │ DB      │  │Dashboard│  │ Telegram   │
          └─────────┘  └─────────┘  │ Email/Hook │
                                    └────────────┘
```

## Security Event Rules

| Trigger Condition | Event Type | Severity |
|-------------------|-----------|---------|
| Unknown face at door zone | unknown_person | HIGH |
| Known face at door | known_person | LOW |
| Person in zone > 15s | loitering | MEDIUM |
| Person in restricted zone | intrusion | CRITICAL |
| Any activity at night | night_activity | HIGH |
| Package appears at door | package_delivered | LOW |
| Package disappears | package_removed | MEDIUM |

## Performance Targets

| Model | Hardware | Target FPS |
|-------|----------|-----------|
| yolov8n (nano) | CPU (i7) | 5–10 FPS |
| yolov8n | GPU (RTX 3060) | 25–60 FPS |
| yolov8s | GPU (RTX 3060) | 15–30 FPS |
| yolov8n | Jetson Orin Nano | 15–30 FPS |
