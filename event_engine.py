"""
Smart event engine - evaluates rules and generates security events
"""
import time
from typing import List, Dict, Optional, Callable
from datetime import datetime
from loguru import logger
from dataclasses import dataclass, field

from detection.yolo_detector import Detection
from tracking.deepsort_tracker import TrackedObject
from zones.zone_manager import ZoneManager, Zone
from config.settings import settings


@dataclass
class SecurityEvent:
    """Generated security event"""
    event_type: str
    camera_id: int
    camera_name: str
    severity: str          # low, medium, high, critical
    description: str
    
    track_id: Optional[int] = None
    person_name: Optional[str] = None
    zone_name: Optional[str] = None
    confidence: float = 0.0
    bbox: Optional[tuple] = None
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    
    snapshot: Optional[bytes] = None  # JPEG bytes


class AlertThrottler:
    """Prevents duplicate alerts within cooldown period"""
    
    def __init__(self, cooldown: int = 60):
        self.cooldown = cooldown
        self._last_alerts: Dict[str, float] = {}
    
    def should_alert(self, key: str) -> bool:
        """Returns True if alert should be sent (not throttled)"""
        now = time.time()
        last = self._last_alerts.get(key, 0)
        if now - last >= self.cooldown:
            self._last_alerts[key] = now
            return True
        return False
    
    def reset(self, key: str):
        self._last_alerts.pop(key, None)


class EventEngine:
    """
    Rule-based event engine.
    Evaluates conditions and generates SecurityEvents.
    """
    
    def __init__(self, camera_id: int, camera_name: str, zone_manager: ZoneManager):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.zone_manager = zone_manager
        self.throttler = AlertThrottler(settings.ALERT_COOLDOWN_SECONDS)
        
        self.event_callbacks: List[Callable] = []
        
        # Track state
        self._package_present: bool = False
        self._known_package_ids: set = set()
        
        logger.info(f"Event engine initialized for camera {camera_name}")
    
    def on_event(self, callback: Callable):
        """Register event callback"""
        self.event_callbacks.append(callback)
    
    def _emit(self, event: SecurityEvent):
        """Dispatch event to all registered callbacks"""
        for cb in self.event_callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
    
    def evaluate(self, tracked_objects: List[TrackedObject],
                 all_detections: List[Detection],
                 face_results: List[dict],
                 frame_snapshot: Optional[bytes] = None):
        """
        Main evaluation method. Called every processed frame.
        Evaluates all rules against current state.
        """
        current_hour = datetime.now().hour
        is_night = self._is_night_time(current_hour)
        
        # Map track_id -> face result
        face_map = self._map_faces_to_tracks(tracked_objects, face_results)
        
        for obj in tracked_objects:
            if obj.class_name != "person":
                continue
            
            face_info = face_map.get(obj.track_id)
            person_name = face_info["name"] if face_info else None
            is_known = face_info["is_known"] if face_info else False
            
            # Update person_name on object
            if face_info and not obj.face_recognized:
                obj.person_name = person_name
                obj.face_recognized = True
            
            # Rule 1: Unknown person near door
            door_zone = self.zone_manager.get_door_zone()
            if door_zone and door_zone.contains_point(*obj.center):
                obj.near_door = True
                
                if not is_known:
                    alert_key = f"unknown_door_{self.camera_id}"
                    if self.throttler.should_alert(alert_key):
                        self._emit(SecurityEvent(
                            event_type="unknown_person",
                            camera_id=self.camera_id,
                            camera_name=self.camera_name,
                            severity="high",
                            description=f"Unknown person detected at door",
                            track_id=obj.track_id,
                            zone_name=door_zone.name,
                            bbox=obj.bbox,
                            snapshot=frame_snapshot,
                        ))
                else:
                    # Known person at door - log as informational
                    alert_key = f"known_door_{self.camera_id}_{person_name}"
                    if self.throttler.should_alert(alert_key):
                        self._emit(SecurityEvent(
                            event_type="known_person",
                            camera_id=self.camera_id,
                            camera_name=self.camera_name,
                            severity="low",
                            description=f"{person_name} at door",
                            track_id=obj.track_id,
                            person_name=person_name,
                            zone_name=door_zone.name,
                            bbox=obj.bbox,
                            snapshot=frame_snapshot,
                        ))
            
            # Rule 2: Loitering detection
            if obj.is_loitering:
                alert_key = f"loitering_{self.camera_id}_{obj.track_id}"
                if self.throttler.should_alert(alert_key):
                    zone_name = obj.current_zones[0] if obj.current_zones else "area"
                    self._emit(SecurityEvent(
                        event_type="loitering",
                        camera_id=self.camera_id,
                        camera_name=self.camera_name,
                        severity="medium",
                        description=f"Person loitering in {zone_name} for "
                                   f"{obj.total_time_visible:.0f}s",
                        track_id=obj.track_id,
                        person_name=person_name if is_known else None,
                        zone_name=zone_name,
                        bbox=obj.bbox,
                        snapshot=frame_snapshot,
                    ))
            
            # Rule 3: Restricted zone intrusion
            for zone in self.zone_manager.zones.values():
                if zone.zone_type == "restricted" and zone.contains_point(*obj.center):
                    alert_key = f"intrusion_{self.camera_id}_{zone.name}_{obj.track_id}"
                    if self.throttler.should_alert(alert_key):
                        self._emit(SecurityEvent(
                            event_type="intrusion",
                            camera_id=self.camera_id,
                            camera_name=self.camera_name,
                            severity="critical",
                            description=f"Intrusion detected in restricted zone: {zone.name}",
                            track_id=obj.track_id,
                            person_name=person_name if is_known else None,
                            zone_name=zone.name,
                            bbox=obj.bbox,
                            snapshot=frame_snapshot,
                            metadata={"is_known": is_known},
                        ))
            
            # Rule 4: Night-time activity
            if is_night:
                alert_key = f"night_activity_{self.camera_id}_{obj.track_id}"
                if self.throttler.should_alert(alert_key):
                    self._emit(SecurityEvent(
                        event_type="night_activity",
                        camera_id=self.camera_id,
                        camera_name=self.camera_name,
                        severity="high",
                        description=f"Activity detected during restricted hours ({current_hour}:00)",
                        track_id=obj.track_id,
                        bbox=obj.bbox,
                        snapshot=frame_snapshot,
                    ))
        
        # Rule 5: Package detection and theft
        self._evaluate_packages(all_detections, frame_snapshot)
    
    def _evaluate_packages(self, detections: List[Detection], snapshot: Optional[bytes]):
        """Detect package delivery and removal events"""
        package_classes = {"suitcase", "backpack", "handbag"}
        packages_now = [d for d in detections if d.class_name in package_classes]
        
        # Simple heuristic: if package appears near door without a person
        door_zone = self.zone_manager.get_door_zone()
        if not door_zone:
            return
        
        packages_at_door = [p for p in packages_now 
                           if door_zone.contains_point(*p.center)]
        
        if packages_at_door and not self._package_present:
            self._package_present = True
            alert_key = f"package_delivered_{self.camera_id}"
            if self.throttler.should_alert(alert_key):
                self._emit(SecurityEvent(
                    event_type="package_delivered",
                    camera_id=self.camera_id,
                    camera_name=self.camera_name,
                    severity="low",
                    description="Package detected at door",
                    snapshot=snapshot,
                ))
        elif not packages_at_door and self._package_present:
            self._package_present = False
            alert_key = f"package_removed_{self.camera_id}"
            if self.throttler.should_alert(alert_key):
                self._emit(SecurityEvent(
                    event_type="package_removed",
                    camera_id=self.camera_id,
                    camera_name=self.camera_name,
                    severity="medium",
                    description="Package removed from door area",
                    snapshot=snapshot,
                ))
    
    def _map_faces_to_tracks(self, tracks: List[TrackedObject],
                              face_results: List[dict]) -> Dict[int, dict]:
        """
        Match face recognition results to tracked objects by bbox overlap.
        """
        mapping = {}
        for track in tracks:
            best_overlap = 0
            best_face = None
            
            tx1, ty1, tx2, ty2 = track.bbox
            
            for face in face_results:
                fx1, fy1, fx2, fy2 = face["bbox"]
                
                # Compute intersection
                ix1 = max(tx1, fx1)
                iy1 = max(ty1, fy1)
                ix2 = min(tx2, fx2)
                iy2 = min(ty2, fy2)
                
                if ix2 <= ix1 or iy2 <= iy1:
                    continue
                
                inter = (ix2 - ix1) * (iy2 - iy1)
                face_area = max((fx2 - fx1) * (fy2 - fy1), 1)
                overlap = inter / face_area
                
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_face = face
            
            if best_face and best_overlap > 0.3:
                mapping[track.track_id] = best_face
        
        return mapping
    
    def _is_night_time(self, hour: int) -> bool:
        start = settings.NIGHT_HOURS_START
        end = settings.NIGHT_HOURS_END
        if start > end:  # wraps midnight
            return hour >= start or hour < end
        return start <= hour < end
