"""
Zone-based detection management - defines areas of interest on camera feeds
"""
import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from loguru import logger
from dataclasses import dataclass, field


@dataclass
class Zone:
    name: str
    points: List[Tuple[int, int]]    # polygon vertices
    zone_type: str = "detection"      # detection, door, restricted, driveway
    color: Tuple[int, int, int] = (0, 255, 255)
    enabled: bool = True
    
    # Rules
    alert_on_entry: bool = True
    alert_on_loitering: bool = True
    loitering_threshold: int = 15    # seconds
    restricted_hours_start: Optional[int] = None
    restricted_hours_end: Optional[int] = None
    
    @property
    def polygon(self) -> np.ndarray:
        return np.array(self.points, dtype=np.int32)
    
    def contains_point(self, x: int, y: int) -> bool:
        """Check if point is inside zone polygon"""
        if len(self.points) < 3:
            return False
        result = cv2.pointPolygonTest(self.polygon, (float(x), float(y)), False)
        return result >= 0
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "points": self.points,
            "zone_type": self.zone_type,
            "enabled": self.enabled,
            "alert_on_entry": self.alert_on_entry,
            "alert_on_loitering": self.alert_on_loitering,
            "loitering_threshold": self.loitering_threshold,
        }


class ZoneManager:
    """Manages detection zones for a camera"""
    
    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self.zones: Dict[str, Zone] = {}
        self._setup_default_zones()
    
    def _setup_default_zones(self):
        """Setup a default full-frame zone"""
        # Will be overridden by user-configured zones
        pass
    
    def add_zone(self, zone: Zone):
        self.zones[zone.name] = zone
        logger.info(f"Camera {self.camera_id}: Added zone '{zone.name}' ({zone.zone_type})")
    
    def remove_zone(self, name: str):
        if name in self.zones:
            del self.zones[name]
    
    def load_zones_from_config(self, zones_config: List[dict]):
        """Load zones from camera configuration"""
        self.zones.clear()
        for zc in zones_config:
            zone = Zone(
                name=zc["name"],
                points=[(int(p[0]), int(p[1])) for p in zc["points"]],
                zone_type=zc.get("zone_type", "detection"),
                enabled=zc.get("enabled", True),
                alert_on_entry=zc.get("alert_on_entry", True),
                alert_on_loitering=zc.get("alert_on_loitering", True),
                loitering_threshold=zc.get("loitering_threshold", 15),
            )
            self.add_zone(zone)
    
    def get_zones_containing(self, x: int, y: int) -> List[Zone]:
        """Get all zones that contain the given point"""
        return [z for z in self.zones.values() if z.enabled and z.contains_point(x, y)]
    
    def get_door_zone(self) -> Optional[Zone]:
        """Get the configured door zone"""
        for zone in self.zones.values():
            if zone.zone_type == "door":
                return zone
        return None
    
    def bbox_overlaps_zone(self, bbox: Tuple[int, int, int, int], 
                           zone: Zone, threshold: float = 0.3) -> bool:
        """
        Check if bounding box significantly overlaps with zone.
        threshold: minimum overlap ratio.
        """
        x1, y1, x2, y2 = bbox
        mask = np.zeros((720, 1280), dtype=np.uint8)  # assume standard resolution
        cv2.fillPoly(mask, [zone.polygon], 255)
        
        # Check how many pixels in bbox are inside zone
        bbox_area = max((x2 - x1) * (y2 - y1), 1)
        
        # Clip bbox to frame
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(1279, x2), min(719, y2)
        
        if x2 <= x1 or y2 <= y1:
            return False
        
        bbox_region = mask[y1:y2, x1:x2]
        overlap_pixels = np.count_nonzero(bbox_region)
        overlap_ratio = overlap_pixels / bbox_area
        
        return overlap_ratio >= threshold
    
    def draw_zones(self, frame: np.ndarray, alpha: float = 0.3) -> np.ndarray:
        """Draw all zones as overlays on frame"""
        overlay = frame.copy()
        
        zone_colors = {
            "door": (0, 0, 255),        # red
            "restricted": (255, 0, 0),   # blue
            "driveway": (255, 165, 0),   # orange
            "detection": (0, 255, 255),  # yellow
        }
        
        for zone in self.zones.values():
            if not zone.enabled or len(zone.points) < 3:
                continue
            
            color = zone_colors.get(zone.zone_type, zone.color)
            pts = zone.polygon.reshape((-1, 1, 2))
            
            # Fill zone
            cv2.fillPoly(overlay, [zone.polygon], color)
            # Draw outline
            cv2.polylines(frame, [pts], True, color, 2)
            
            # Label
            centroid = zone.polygon.mean(axis=0).astype(int)
            cv2.putText(frame, zone.name, tuple(centroid),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # Blend overlay
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        return frame
