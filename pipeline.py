"""
Per-camera AI processing pipeline
"""
import cv2
import asyncio
import threading
import time
import numpy as np
from typing import Optional, List, Callable
from loguru import logger

from cameras.stream_manager import CameraStream
from detection.yolo_detector import YOLODetector, Detection
from tracking.deepsort_tracker import DeepSORTTracker
from recognition.face_recognizer import FaceRecognizer
from zones.zone_manager import ZoneManager
from events.event_engine import EventEngine, SecurityEvent
from storage.evidence_store import EvidenceStore, evidence_store
from config.settings import settings


class CameraPipeline:
    """
    Full AI processing pipeline for a single camera.
    Runs detection, tracking, recognition, and event generation.
    """
    
    def __init__(self, camera_id: int, camera_name: str, stream: CameraStream,
                 zones_config: List[dict] = None):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.stream = stream
        
        # AI components (each pipeline has its own tracker)
        self.detector = YOLODetector()
        self.tracker = DeepSORTTracker()
        self.face_recognizer = FaceRecognizer()
        
        # Zone management
        self.zone_manager = ZoneManager(camera_id)
        if zones_config:
            self.zone_manager.load_zones_from_config(zones_config)
        
        # Event engine
        self.event_engine = EventEngine(camera_id, camera_name, self.zone_manager)
        
        # State
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.frame_count = 0
        self.fps = 0.0
        self.last_frame: Optional[np.ndarray] = None
        self.last_annotated_frame: Optional[np.ndarray] = None
        
        # Performance tracking
        self._fps_timer = time.time()
        self._fps_frames = 0
        
        # Face recognition runs every N frames (expensive)
        self._face_check_interval = 15
        self._last_face_results = []
        
        logger.info(f"Pipeline created for camera: {camera_name}")
    
    def on_event(self, callback: Callable[[SecurityEvent], None]):
        """Register callback for security events"""
        self.event_engine.on_event(callback)
    
    def start(self):
        """Start processing pipeline"""
        self.running = True
        self.thread = threading.Thread(target=self._pipeline_loop, daemon=True)
        self.thread.start()
        logger.info(f"[{self.camera_name}] Pipeline started")
    
    def stop(self):
        """Stop processing pipeline"""
        self.running = False
        self.tracker.reset()
        if self.thread:
            self.thread.join(timeout=5.0)
        logger.info(f"[{self.camera_name}] Pipeline stopped")
    
    def get_frame_jpeg(self) -> Optional[bytes]:
        """Get latest annotated frame as JPEG for streaming"""
        frame = self.last_annotated_frame
        if frame is None:
            return None
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        return buffer.tobytes()
    
    def _pipeline_loop(self):
        """Main processing loop"""
        frame_skip = 0
        
        while self.running:
            frame = self.stream.get_frame(timeout=0.5)
            if frame is None:
                continue
            
            self.last_frame = frame.copy()
            self.frame_count += 1
            
            # Frame skipping for performance
            frame_skip += 1
            if frame_skip < settings.FRAME_SKIP:
                continue
            frame_skip = 0
            
            try:
                self._process_frame(frame)
            except Exception as e:
                logger.error(f"[{self.camera_name}] Pipeline error: {e}")
            
            self._update_fps()
    
    def _process_frame(self, frame: np.ndarray):
        """Process a single frame through the full AI pipeline"""
        annotated = frame.copy()
        
        # Step 1: Object detection
        detections = self.detector.detect(frame)
        
        # Step 2: Get zones as list of dicts
        zones = [z.to_dict() for z in self.zone_manager.zones.values() if z.enabled]
        
        # Step 3: Update tracker
        tracked_objects = self.tracker.update(detections, frame, zones)
        
        # Step 4: Face recognition (periodic)
        if self.frame_count % self._face_check_interval == 0:
            persons = [d for d in detections if d.class_name == "person"]
            if persons:
                self._last_face_results = self.face_recognizer.recognize_faces(frame)
        
        # Step 5: Event engine evaluation
        snapshot_bytes = evidence_store.frame_to_jpeg(frame)
        self.event_engine.evaluate(
            tracked_objects=tracked_objects,
            all_detections=detections,
            face_results=self._last_face_results,
            frame_snapshot=snapshot_bytes,
        )
        
        # Step 6: Annotate frame
        annotated = self._annotate_frame(annotated, detections, tracked_objects)
        self.last_annotated_frame = annotated
    
    def _annotate_frame(self, frame: np.ndarray, detections, tracked_objects) -> np.ndarray:
        """Draw all annotations on frame"""
        # Draw zones
        frame = self.zone_manager.draw_zones(frame)
        
        # Draw detections
        frame = self.detector.draw_detections(frame, detections)
        
        # Draw tracked IDs and names
        for obj in tracked_objects:
            x1, y1, x2, y2 = obj.bbox
            
            label_parts = [f"ID:{obj.track_id}"]
            if obj.person_name:
                label_parts.append(obj.person_name)
            elif obj.class_name == "person":
                label_parts.append("Unknown")
            
            if obj.is_loitering:
                label_parts.append("⚠LOITERING")
            if obj.near_door:
                label_parts.append("🚪DOOR")
            
            label = " | ".join(label_parts)
            color = (0, 255, 0) if obj.person_name else (0, 165, 255)
            
            cv2.putText(frame, label, (x1, y2 + 16),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        
        # Draw face results
        frame = self.face_recognizer.draw_faces(frame, self._last_face_results)
        
        # HUD overlay
        frame = self._draw_hud(frame)
        
        return frame
    
    def _draw_hud(self, frame: np.ndarray) -> np.ndarray:
        """Draw heads-up display with system info"""
        h, w = frame.shape[:2]
        
        # Semi-transparent top bar
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 30), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        text = f"{self.camera_name}  |  {timestamp}  |  {self.fps:.1f} FPS"
        cv2.putText(frame, text, (8, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return frame
    
    def _update_fps(self):
        self._fps_frames += 1
        elapsed = time.time() - self._fps_timer
        if elapsed >= 1.0:
            self.fps = self._fps_frames / elapsed
            self._fps_frames = 0
            self._fps_timer = time.time()
    
    @property
    def status(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "running": self.running,
            "fps": round(self.fps, 1),
            "frame_count": self.frame_count,
            "tracked_objects": len(self.tracker.tracked_objects),
        }
