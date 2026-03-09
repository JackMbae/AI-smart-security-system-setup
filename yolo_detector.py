"""
YOLOv8 object detection pipeline
"""
import cv2
import numpy as np
from typing import List, Tuple, Optional
from ultralytics import YOLO
from loguru import logger
from config.settings import settings
from dataclasses import dataclass


@dataclass
class Detection:
    """Single detection result"""
    bbox: Tuple[int, int, int, int]   # x1, y1, x2, y2
    class_id: int
    class_name: str
    confidence: float
    center: Tuple[int, int]
    
    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)


# COCO class names relevant to security
SECURITY_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    14: "bird",
    15: "cat",
    16: "dog",
    24: "backpack",
    26: "handbag",
    28: "suitcase",
    39: "bottle",
    56: "chair",
    63: "laptop",
    67: "phone",
    73: "book",
}


class YOLODetector:
    """YOLOv8 real-time object detector"""
    
    def __init__(self):
        self.model = None
        self.frame_skip_counter = 0
        self._load_model()
    
    def _load_model(self):
        try:
            self.model = YOLO(settings.YOLO_MODEL)
            logger.success(f"YOLOv8 model loaded: {settings.YOLO_MODEL}")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
    
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Run object detection on a frame.
        Returns list of Detection objects.
        """
        if self.model is None:
            return []
        
        try:
            results = self.model(
                frame,
                conf=settings.YOLO_CONFIDENCE,
                iou=settings.YOLO_IOU,
                verbose=False,
                stream=False,
            )
            
            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    class_name = self.model.names.get(cls_id, "unknown")
                    center = ((x1 + x2) // 2, (y1 + y2) // 2)
                    
                    detections.append(Detection(
                        bbox=(x1, y1, x2, y2),
                        class_id=cls_id,
                        class_name=class_name,
                        confidence=conf,
                        center=center,
                    ))
            
            return detections
            
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []
    
    def detect_persons(self, frame: np.ndarray) -> List[Detection]:
        """Filter detections to persons only"""
        return [d for d in self.detect(frame) if d.class_name == "person"]
    
    def draw_detections(self, frame: np.ndarray, detections: List[Detection],
                        tracked_ids: dict = None) -> np.ndarray:
        """Draw bounding boxes and labels on frame"""
        frame = frame.copy()
        
        colors = {
            "person": (0, 255, 0),      # green
            "car": (255, 165, 0),       # orange
            "truck": (255, 165, 0),
            "package": (0, 0, 255),     # red
            "dog": (255, 0, 255),       # magenta
            "cat": (255, 0, 255),
        }
        
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = colors.get(det.class_name, (200, 200, 200))
            
            # Bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Label background
            label = f"{det.class_name} {det.confidence:.2f}"
            if tracked_ids and det in tracked_ids:
                label = f"ID:{tracked_ids[det]} " + label
            
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - lh - 6), (x1 + lw, y1), color, -1)
            cv2.putText(frame, label, (x1, y1 - 4),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        return frame


# Global detector instance
detector = YOLODetector()
