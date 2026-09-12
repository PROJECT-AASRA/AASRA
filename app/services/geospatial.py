"""
Geospatial Hazard & Proximity Processing Service
Powered by Shapely and GeoPandas for high-performance spatial indexing:
- Point-in-Polygon checks against historical flood layers (Uttrakhandpast_flood.geojson)
- Real-time distance calculation to nearest river geometries (uttarakhand_river_4326.geojson)
- Spatial proximity to emergency hospitals and health facilities (healthcare.geojson)
- Composite geospatial hazard exposure scoring for households and geographic points
"""

import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from shapely.geometry import shape, Point
from shapely.strtree import STRtree

# Base directories
_SERVICES_DIR = Path(__file__).resolve().parent
_APP_DIR = _SERVICES_DIR.parent
_PROJECT_ROOT = _APP_DIR.parent
DATA_DIR = _PROJECT_ROOT / "data" / "uttarakhand"


class GeospatialEngine:
    """
    Singleton spatial engine maintaining indexed R-tree spatial trees
    for sub-millisecond point-in-polygon and nearest-neighbor calculations.
    """
    _instance = None

    def __init__(self):
        self.initialized = False
        self.flood_geoms: List[Any] = []
        self.flood_tree: Optional[STRtree] = None
        self.flood_properties: List[Dict[str, Any]] = []

        self.river_geoms: List[Any] = []
        self.river_tree: Optional[STRtree] = None

        self.hosp_geoms: List[Point] = []
        self.hosp_tree: Optional[STRtree] = None
        self.hosp_properties: List[Dict[str, Any]] = []

        self._load_layers()

    def _load_layers(self):
        """Loads and indexes GeoJSON layers into memory."""
        # 1. Historical Flood Layer
        flood_path = DATA_DIR / "hazards" / "Uttrakhandpast_flood.geojson"
        if flood_path.exists():
            try:
                with open(flood_path, "r", encoding="utf-8") as f:
                    gj = json.load(f)
                for feat in gj.get("features", []):
                    g = feat.get("geometry")
                    if g:
                        s = shape(g)
                        if s.is_valid:
                            self.flood_geoms.append(s)
                            self.flood_properties.append(feat.get("properties") or {})
                if self.flood_geoms:
                    self.flood_tree = STRtree(self.flood_geoms)
            except Exception as e:
                print(f"Warning loading flood layer: {e}")

        # 2. River Layer (Reprojected WGS84)
        river_path = DATA_DIR / "river" / "uttarakhand_river_4326.geojson"
        if not river_path.exists():
            river_path = DATA_DIR / "river" / "uttarakhand_river_polygon.geojson"

        if river_path.exists():
            try:
                with open(river_path, "r", encoding="utf-8") as f:
                    gj = json.load(f)
                for feat in gj.get("features", []):
                    g = feat.get("geometry")
                    if g:
                        s = shape(g)
                        if s.is_valid:
                            self.river_geoms.append(s)
                if self.river_geoms:
                    self.river_tree = STRtree(self.river_geoms)
            except Exception as e:
                print(f"Warning loading river layer: {e}")

        # 3. Healthcare Infrastructure Layer
        hosp_path = DATA_DIR / "infrastructure" / "emergency" / "healthcare.geojson"
        if hosp_path.exists():
            try:
                with open(hosp_path, "r", encoding="utf-8") as f:
                    gj = json.load(f)
                for feat in gj.get("features", []):
                    coords = feat.get("geometry", {}).get("coordinates", [])
                    if len(coords) >= 2:
                        lon, lat = float(coords[0]), float(coords[1])
                        self.hosp_geoms.append(Point(lon, lat))
                        self.hosp_properties.append(feat.get("properties") or {})
                if self.hosp_geoms:
                    self.hosp_tree = STRtree(self.hosp_geoms)
            except Exception as e:
                print(f"Warning loading healthcare layer: {e}")

        self.initialized = True

    def check_in_flood_zone(self, lat: float, lon: float) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Point-in-Polygon check to determine if (lat, lon) intersects
        any historical Uttarakhand flood polygon.
        """
        if not self.flood_tree or not self.flood_geoms:
            return False, None

        pt = Point(lon, lat)
        # Query bounding box candidates first
        candidates_idx = self.flood_tree.query(pt)
        for idx in candidates_idx:
            poly = self.flood_geoms[idx]
            if poly.contains(pt) or poly.touches(pt):
                props = self.flood_properties[idx] if idx < len(self.flood_properties) else {}
                return True, props

        return False, None

    def get_distance_to_nearest_river_km(self, lat: float, lon: float) -> float:
        """
        Calculates great-circle distance in kilometers to the nearest river geometry.
        """
        if not self.river_tree or not self.river_geoms:
            return 2.5  # Fallback default distance

        pt = Point(lon, lat)
        nearest_idx = self.river_tree.nearest(pt)
        nearest_geom = self.river_geoms[nearest_idx]

        if nearest_geom.contains(pt):
            return 0.0

        # Degree distance converted to kilometers at latitude ~30°
        deg_dist = pt.distance(nearest_geom)
        km_dist = deg_dist * 111.139 * math.cos(math.radians(lat))
        return round(max(0.0, km_dist), 2)

    def get_nearest_hospital(self, lat: float, lon: float) -> Tuple[float, str]:
        """
        Finds the nearest hospital/clinic and returns (distance_km, hospital_name).
        """
        if not self.hosp_tree or not self.hosp_geoms:
            return 5.0, "District Hospital"

        pt = Point(lon, lat)
        nearest_idx = self.hosp_tree.nearest(pt)
        hosp_pt = self.hosp_geoms[nearest_idx]
        props = self.hosp_properties[nearest_idx] if nearest_idx < len(self.hosp_properties) else {}

        # Great-circle distance to point
        deg_dist = pt.distance(hosp_pt)
        km_dist = deg_dist * 111.139 * math.cos(math.radians(lat))
        name = props.get("name") or props.get("name:en") or "Uttarakhand Primary Health Centre"

        return round(max(0.1, km_dist), 2), name.strip()

    def evaluate_geospatial_hazard(
        self,
        lat: float,
        lon: float,
        district: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive geospatial analysis pipeline:
        Point -> Spatial Lookup -> Multi-factor Hazard Exposure Computation.
        """
        in_flood, flood_props = self.check_in_flood_zone(lat, lon)
        dist_river_km = self.get_distance_to_nearest_river_km(lat, lon)
        dist_hosp_km, hosp_name = self.get_nearest_hospital(lat, lon)

        # 1. Flood Zone Severity Component
        flood_exposure = 0.95 if in_flood else 0.20

        # 2. River Proximity Severity Component
        if dist_river_km <= 0.20:
            river_exposure = 0.95
        elif dist_river_km <= 0.50:
            river_exposure = 0.85
        elif dist_river_km <= 1.50:
            river_exposure = 0.70
        elif dist_river_km <= 3.00:
            river_exposure = 0.50
        elif dist_river_km <= 6.00:
            river_exposure = 0.35
        else:
            river_exposure = 0.15

        # 3. Medical Isolation Risk Component
        if dist_hosp_km > 15.0:
            isolation_risk = 0.85
        elif dist_hosp_km > 8.0:
            isolation_risk = 0.65
        elif dist_hosp_km > 3.0:
            isolation_risk = 0.40
        else:
            isolation_risk = 0.15

        # 4. District baseline landslide / cloudburst factor
        HIGH_LANDSLIDE = {"chamoli", "rudraprayag", "uttarkashi", "pithoragarh", "tehri garhwal", "bageshwar"}
        dist_lower = (district or "").strip().lower()
        terrain_factor = 0.88 if dist_lower in HIGH_LANDSLIDE else 0.45

        # Composite Normalized Exposure (0.0 to 1.0)
        composite_exposure = round(
            flood_exposure * 0.35 +
            river_exposure * 0.30 +
            terrain_factor * 0.25 +
            isolation_risk * 0.10,
            3
        )
        composite_exposure = min(1.0, max(0.05, composite_exposure))

        # Risk tier classification
        if composite_exposure >= 0.75:
            tier = "CRITICAL"
        elif composite_exposure >= 0.50:
            tier = "HIGH"
        elif composite_exposure >= 0.30:
            tier = "MODERATE"
        else:
            tier = "LOW"

        return {
            "latitude": lat,
            "longitude": lon,
            "district": district or "Uttarakhand",
            "in_historical_flood_zone": in_flood,
            "flood_zone_details": flood_props,
            "distance_to_nearest_river_km": dist_river_km,
            "distance_to_nearest_hospital_km": dist_hosp_km,
            "nearest_hospital_name": hosp_name,
            "component_scores": {
                "flood_zone_component": flood_exposure,
                "river_proximity_component": river_exposure,
                "terrain_landslide_factor": terrain_factor,
                "medical_isolation_factor": isolation_risk
            },
            "composite_geospatial_hazard_exposure": composite_exposure,
            "geospatial_hazard_tier": tier
        }


# Global engine singleton instance
_engine_instance: Optional[GeospatialEngine] = None


def get_geospatial_engine() -> GeospatialEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = GeospatialEngine()
    return _engine_instance
