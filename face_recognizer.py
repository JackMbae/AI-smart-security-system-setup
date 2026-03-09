"""
Face recognition system with known persons database
"""
import os
import cv2
import numpy as np
import face_recognition
from typing import List, Tuple, Optional, Dict
from loguru import logger
from pathlib import Path
import threading
import time

from config.settings import settings


class FaceRecord:
    def __init__(self, name: str, encoding: np.ndarray, role: str = "known"):
        self.name = name
        self.encoding = encoding
        self.role = role


class FaceRecognizer:
    """
    Face recognition using face_recognition library.
    Supports loading faces from directory and database.
    """
    
    def __init__(self):
        self.known_faces: List[FaceRecord] = []
        self._lock = threading.Lock()
        self._load_from_directory()
        logger.success(f"Face recognizer ready with {len(self.known_faces)} known faces")
    
    def _load_from_directory(self):
        """Load known faces from the known_faces/ directory"""
        faces_dir = Path(settings.KNOWN_FACES_DIR)
        if not faces_dir.exists():
            faces_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created known_faces directory at {faces_dir}")
            return
        
        count = 0
        for img_path in faces_dir.glob("*.[jp][pn][g]*"):
            name = img_path.stem  # filename without extension
            try:
                image = face_recognition.load_image_file(str(img_path))
                encodings = face_recognition.face_encodings(image)
                
                if encodings:
                    record = FaceRecord(name=name, encoding=encodings[0])
                    self.known_faces.append(record)
                    count += 1
                    logger.debug(f"Loaded face: {name}")
                else:
                    logger.warning(f"No face found in: {img_path}")
            except Exception as e:
                logger.error(f"Error loading face {img_path}: {e}")
        
        logger.info(f"Loaded {count} faces from directory")
    
    def add_face(self, name: str, image: np.ndarray, role: str = "known") -> bool:
        """Add a new face to the recognition database"""
        try:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            encodings = face_recognition.face_encodings(rgb_image)
            
            if not encodings:
                logger.warning(f"No face detected for {name}")
                return False
            
            with self._lock:
                # Remove existing entry if name exists
                self.known_faces = [f for f in self.known_faces if f.name != name]
                self.known_faces.append(FaceRecord(name, encodings[0], role))
            
            logger.info(f"Added face: {name} ({role})")
            return True
        except Exception as e:
            logger.error(f"Error adding face {name}: {e}")
            return False
    
    def recognize_faces(self, frame: np.ndarray) -> List[dict]:
        """
        Detect and recognize all faces in a frame.
        Returns list of face recognition results.
        """
        try:
            # Downscale for speed (process at 1/2 size)
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            # Detect face locations and encodings
            face_locations = face_recognition.face_locations(
                rgb_frame,
                model=settings.FACE_RECOGNITION_MODEL
            )
            
            if not face_locations:
                return []
            
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            
            results = []
            with self._lock:
                known_encodings = [f.encoding for f in self.known_faces]
                known_names = [f.name for f in self.known_faces]
                known_roles = [f.role for f in self.known_faces]
            
            for encoding, location in zip(face_encodings, face_locations):
                name = "Unknown"
                role = "unknown"
                confidence = 0.0
                
                if known_encodings:
                    # Compare with known faces
                    distances = face_recognition.face_distance(known_encodings, encoding)
                    best_idx = np.argmin(distances)
                    best_distance = distances[best_idx]
                    
                    if best_distance <= settings.FACE_RECOGNITION_TOLERANCE:
                        name = known_names[best_idx]
                        role = known_roles[best_idx]
                        confidence = float(1.0 - best_distance)
                
                # Scale location back to full size
                top, right, bottom, left = [coord * 2 for coord in location]
                
                results.append({
                    "name": name,
                    "role": role,
                    "confidence": round(confidence, 3),
                    "bbox": (left, top, right, bottom),  # x1, y1, x2, y2
                    "is_known": name != "Unknown",
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Face recognition error: {e}")
            return []
    
    def draw_faces(self, frame: np.ndarray, face_results: List[dict]) -> np.ndarray:
        """Draw face recognition results on frame"""
        frame = frame.copy()
        for face in face_results:
            x1, y1, x2, y2 = face["bbox"]
            name = face["name"]
            is_known = face["is_known"]
            confidence = face["confidence"]
            
            color = (0, 255, 0) if is_known else (0, 0, 255)
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{name} ({confidence:.0%})" if is_known else "Unknown"
            cv2.putText(frame, label, (x1, y1 - 8),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return frame
    
    def reload(self):
        """Reload faces from directory"""
        with self._lock:
            self.known_faces = []
        self._load_from_directory()
        logger.info("Face database reloaded")


# Global recognizer instance
face_recognizer = FaceRecognizer()
