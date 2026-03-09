"""
DeepSORT multi-object tracker with zone awareness
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from deep_sort_realtime.deepsort_tracker import DeepSort
from loguru import logger
from dataclasses import dataclass, field
import time

from detection.yolo_detector import Detection
from config.settings import settings


@dataclass
class TrackedObject:
    """A tracked object with history"""
    track_id: int
    class_name: str
    bbox: Tuple[int, int, int, int]
    confidence: float
    center: Tuple[int, int]
    
    # Zone tracking
    current_zones: List[str] = field(default_factory=list)
    zone_entry_times: Dict[str, float] = field(default_factory=dict)
    
    # Face recognition result
    person_name: Optional[str] = None
    face_recognized: bool = False
    
    # Behavioral flags
    is_loitering: bool = False
    near_door: bool = False
    is_suspicious: bool = False
    
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    
    @property
    def time_in_zone(self) -> Dict[str, float]:
        return {
            zone: time.time() - entry_time
            for zone, entry_time in self.zone_entry_times.items()
        }
    
    @property
    def total_time_visible(self) -> float:
        return time.time() - self.first_seen


class DeepSORTTracker:
    """
    Multi-object tracker using DeepSORT algorithm.
    Maintains persistent IDs across frames.
    """
    
    def __init__(self):
        self.tracker = DeepSort(
            max_age=settings.MAX_TRACK_AGE,
            n_init=settings.MIN_TRACK_HITS,
            max_iou_distance=0.7,
        )
        self.tracked_objects: Dict[int, TrackedObject] = {}
        self.lost_tracks: Dict[int, TrackedObject] = {}
        logger.success("DeepSORT tracker initialized")
    
    def update(self, detections: List[Detection], frame: np.ndarray,
               zones: List[dict] = None) -> List[TrackedObject]:
        """
        Update tracker with new detections.
        Returns list of currently tracked objects.
        """
        if not detections:
            # Age out tracks
            self._age_tracks()
            return list(self.tracked_objects.values())
        
        # Prepare detections for DeepSORT: [x, y, w, h, conf]
        raw_detections = []
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            w, h = x2 - x1, y2 - y1
            raw_detections.append(([x1, y1, w, h], det.confidence, det.class_name))
        
        try:
            tracks = self.tracker.update_tracks(raw_detections, frame=frame)
        except Exception as e:
            logger.error(f"Tracker update error: {e}")
            return list(self.tracked_objects.values())
        
        current_ids = set()
        updated_objects = []
        
        for track in tracks:
            if not track.is_confirmed():
                continue
            
            track_id = track.track_id
            current_ids.add(track_id)
            
            bbox = track.to_tlbr()  # [x1, y1, x2, y2]
            x1, y1, x2, y2 = map(int, bbox)
            center = ((x1 + x2) // 2, (y1 + y2) // 2)
            
            if track_id in self.tracked_objects:
                obj = self.tracked_objects[track_id]
                obj.bbox = (x1, y1, x2, y2)
                obj.center = center
                obj.last_seen = time.time()
            else:
                obj = TrackedObject(
                    track_id=track_id,
                    class_name=track.get_det_class() or "person",
                    bbox=(x1, y1, x2, y2),
                    confidence=track.get_det_conf() or 0.0,
                    center=center,
                )
                self.tracked_objects[track_id] = obj
                logger.debug(f"New track: ID={track_id}")
            
            # Update zone membership
            if zones:
                self._update_zones(obj, zones)
            
            # Check loitering
            self._check_loitering(obj)
            
            updated_objects.append(obj)
        
        # Handle lost tracks
        lost_ids = set(self.tracked_objects.keys()) - current_ids
        for lost_id in lost_ids:
            obj = self.tracked_objects.pop(lost_id)
            self.lost_tracks[lost_id] = obj
            logger.debug(f"Track lost: ID={lost_id}")
        
        # Clean old lost tracks (keep 60 seconds for deduplication)
        cutoff = time.time() - 60
        self.lost_tracks = {
            k: v for k, v in self.lost_tracks.items()
            if v.last_seen > cutoff
        }
        
        return updated_objects
    
    def _update_zones(self, obj: TrackedObject, zones: List[dict]):
        """Check which zones the object center is in"""
        import cv2
        cx, cy = obj.center
        current_zones = []
        
        for zone in zones:
            zone_name = zone.get("name", "unknown")
            polygon = np.array(zone.get("points", []), dtype=np.int32)
            
            if len(polygon) < 3:
                continue
            
            inside = cv2.pointPolygonTest(polygon, (cx, cy), False) >= 0
            
            if inside:
                current_zones.append(zone_name)
                if zone_name not in obj.zone_entry_times:
                    obj.zone_entry_times[zone_name] = time.time()
                    logger.debug(f"Track {obj.track_id} entered zone: {zone_name}")
            else:
                # Remove from zone
                obj.zone_entry_times.pop(zone_name, None)
        
        obj.current_zones = current_zones
    
    def _check_loitering(self, obj: TrackedObject):
        """Flag loitering if person stays too long"""
        threshold = settings.LOITERING_THRESHOLD_SECONDS
        for zone, entry_time in obj.zone_entry_times.items():
            time_in_zone = time.time() - entry_time
            if time_in_zone > threshold:
                if not obj.is_loitering:
                    obj.is_loitering = True
                    logger.warning(
                        f"Loitering detected: ID={obj.track_id} in {zone} "
                        f"for {time_in_zone:.1f}s"
                    )
    
    def _age_tracks(self):
        """Remove stale tracks"""
        cutoff = time.time() - (settings.MAX_TRACK_AGE / 30.0)  # ~1 second at 30fps
        stale = [tid for tid, obj in self.tracked_objects.items()
                 if obj.last_seen < cutoff]
        for tid in stale:
            self.tracked_objects.pop(tid)
    
    def get_track(self, track_id: int) -> Optional[TrackedObject]:
        return self.tracked_objects.get(track_id)
    
    def reset(self):
        self.tracked_objects.clear()
        self.lost_tracks.clear()
        self.tracker = DeepSort(
            max_age=settings.MAX_TRACK_AGE,
            n_init=settings.MIN_TRACK_HITS,
        )
