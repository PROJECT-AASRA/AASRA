"""
GIS & Map Visualization API Router (Project AASRA)
Provides standard GeoJSON FeatureCollections for frontend web map visualizers:
- District boundaries with real risk intelligence
- Flood polygons (Uttrakhandpast_flood.geojson)
- River networks (uttarakhand_river_4326.geojson)
- Landslide inventory points (landslide.geojson)
- Earthquake seismic epicenters (uttarakhand_earthquakes.geojson)
- Rainfall monitoring telemetry stations (uttarakhand_rainfall.geojson)
- Registered households colored by risk level (RED, ORANGE, YELLOW, GREEN)
- Emergency shelters with capacity & amenities
- Emergency infrastructure (hospitals, fire stations, police)
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Response

from app.routes.relocation import SHELTERS_DB
from app.routes.households import HOUSEHOLDS_DB
from app.services.data_loader import get_uttarakhand_district_hazards

router = APIRouter()

_APP_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _APP_DIR.parent
DATA_DIR = _PROJECT_ROOT / "data" / "uttarakhand"


@router.get("/shelters", summary="Shelters GeoJSON Layer")
def get_shelters_geojson(
    state: Optional[str] = Query(None, description="Optional state filter"),
    district: Optional[str] = Query(None, description="Optional district filter")
):
    """
    Returns emergency shelters, community halls, and schools
    as a GeoJSON FeatureCollection ready for map rendering.
    """
    target_state = state.strip().lower() if isinstance(state, str) and state.strip() else None
    target_dist = district.strip().lower() if isinstance(district, str) and district.strip() else None

    features = []
    for s in SHELTERS_DB.values():
        if target_state and s.get("state", "").strip().lower() != target_state:
            continue
        if target_dist and s.get("district", "").strip().lower() != target_dist:
            continue

        feat = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(s["longitude"]), float(s["latitude"])]
            },
            "properties": {
                "center_id": s["center_id"],
                "name": s["name"],
                "state": s.get("state", "Uttarakhand"),
                "district": s.get("district", ""),
                "village": s.get("village", ""),
                "total_capacity": s.get("total_capacity", 0),
                "current_occupancy": s.get("current_occupancy", 0),
                "available_capacity": s.get("available_capacity", 0),
                "medical_support": s.get("medical_support", False),
                "food_available": s.get("food_available", True),
                "water_available": s.get("water_available", True),
                "sanitation_available": s.get("sanitation_available", True),
                "accessible_for_disabled": s.get("accessible_for_disabled", False),
                "active": s.get("active", True),
                "source_type": s.get("source_type", "Emergency Shelter"),
                "marker_color": "#0288d1" if s.get("available_capacity", 0) > 0 else "#757575"
            }
        }
        features.append(feat)

    return {
        "type": "FeatureCollection",
        "name": "AASRA_Relocation_Shelters",
        "features": features
    }


@router.get("/households", summary="Households GeoJSON Layer with Risk & Vulnerability")
def get_households_geojson(
    state: Optional[str] = Query(None, description="Optional state filter"),
    district: Optional[str] = Query(None, description="Optional district filter")
):
    """
    Returns registered households as a GeoJSON FeatureCollection
    with properties for risk level (RED, ORANGE, YELLOW, GREEN),
    vulnerability level, priority tier, and relocation necessity.
    """
    target_state = state.strip().lower() if isinstance(state, str) and state.strip() else None
    target_dist = district.strip().lower() if isinstance(district, str) and district.strip() else None

    features = []
    color_map = {
        "RED": "#d32f2f",       # Very High / Critical
        "ORANGE": "#f57c00",    # High
        "YELLOW": "#fbc02d",    # Moderate
        "GREEN": "#388e3c"      # Low
    }

    for h in HOUSEHOLDS_DB.values():
        if target_state and h.get("state", "").strip().lower() != target_state:
            continue
        if target_dist and h.get("district", "").strip().lower() != target_dist:
            continue

        r_level = h.get("risk_level", "YELLOW")
        p_level = h.get("priority_level", "LOW")
        v_level = h.get("vulnerability_level", "MODERATE")

        # Relocation required heuristic
        relocation_req = (
            p_level in ["IMMEDIATE", "HIGH"] or
            r_level == "RED" or
            float(h.get("risk_score", 0)) >= 65.0
        )

        feat = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(h["longitude"]), float(h["latitude"])]
            },
            "properties": {
                "household_id": h["household_id"],
                "state": h.get("state", "Uttarakhand"),
                "district": h.get("district", ""),
                "village": h.get("village", ""),
                "population": h.get("population", 1),
                "children": h.get("children", 0),
                "elderly": h.get("elderly", 0),
                "disabled": h.get("disabled", 0),
                "risk_score": round(float(h.get("risk_score", 50.0)), 2),
                "risk_level": r_level,
                "vulnerability_score": round(float(h.get("vulnerability_score", 50.0)), 2),
                "vulnerability_level": v_level,
                "priority_level": p_level,
                "relocation_required": relocation_req,
                "marker_color": color_map.get(r_level, "#fbc02d")
            }
        }
        features.append(feat)

    return {
        "type": "FeatureCollection",
        "name": "AASRA_Households",
        "features": features
    }


@router.get("/villages", summary="Uttarakhand Villages GeoJSON Layer")
def get_villages_geojson(
    district: Optional[str] = Query(None, description="Optional district filter"),
    search: Optional[str] = Query(None, description="Search village by name prefix or substring"),
    limit: int = Query(2500, ge=1, le=20000, description="Max villages to return")
):
    """
    Streams verified Uttarakhand village settlement locations (16,920 records from Survey of India).
    Supports district filtering and substring name search.
    """
    v_path = DATA_DIR / "boundaries" / "uttarakhand_villages_4326.geojson"
    if not v_path.exists():
        raise HTTPException(status_code=404, detail="Village dataset not found on server.")

    with open(v_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])

    target_dist = district.strip().lower() if isinstance(district, str) and district.strip() else None
    target_search = search.strip().lower() if isinstance(search, str) and search.strip() else None

    if target_dist:
        features = [f for f in features if target_dist in f.get("properties", {}).get("district", "").lower()]

    if target_search:
        features = [f for f in features if target_search in f.get("properties", {}).get("village", "").lower()]

    return {
        "type": "FeatureCollection",
        "name": "Uttarakhand_Villages",
        "total_count": len(features),
        "features": features[:limit]
    }


@router.get("/districts", summary="District Boundaries GeoJSON Layer")
def get_districts_geojson():
    """Streams Uttarakhand district boundaries with attached live risk indicators."""
    dist_path = DATA_DIR / "boundaries" / "district_boundary_4326.geojson"
    if not dist_path.exists():
        dist_path = DATA_DIR / "boundaries" / "district_boundary.geojson"
    if not dist_path.exists():
        raise HTTPException(status_code=404, detail="District boundary layer not found.")

    with open(dist_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Attach live risk metrics to district features
    district_risks = {d["district"].lower(): d for d in get_uttarakhand_district_hazards()}
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        dname = (props.get("DISTRICT") or props.get("district") or props.get("District") or "").lower()
        if dname in district_risks:
            risk_info = district_risks[dname]
            props["risk_score"] = risk_info["overall_risk_score"]
            props["alert_level"] = risk_info["alert_level"]
            props["houses_destroyed"] = risk_info["houses_destroyed"]
            props["houses_damaged"] = risk_info["houses_damaged"]

    return data


@router.get("/state-boundary", summary="Uttarakhand State Boundary GeoJSON Layer")
def get_state_boundary_geojson():
    """Streams the official Uttarakhand state boundary polygon in WGS84."""
    state_path = DATA_DIR / "boundaries" / "state_boundary_4326.geojson"
    if not state_path.exists():
        state_path = DATA_DIR / "boundaries" / "state_boundary.geojson"
    if not state_path.exists():
        raise HTTPException(status_code=404, detail="State boundary layer not found.")

    with open(state_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/flood-zones", summary="Historical Flood Zones GeoJSON Layer")
def get_historical_flood_zones():
    """Streams the historical flood polygon layer (Uttrakhandpast_flood.geojson)."""
    flood_path = DATA_DIR / "hazards" / "Uttrakhandpast_flood.geojson"
    if not flood_path.exists():
        raise HTTPException(status_code=404, detail="Flood layer file not found.")

    with open(flood_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/rivers", summary="River Network GeoJSON Layer")
def get_rivers_geojson():
    """Streams the real river geometries layer (uttarakhand_river_4326.geojson)."""
    river_path = DATA_DIR / "river" / "uttarakhand_river_4326.geojson"
    if not river_path.exists():
        raise HTTPException(status_code=404, detail="River layer file not found.")

    with open(river_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/landslides", summary="Landslide Points GeoJSON Layer")
def get_landslides_geojson(limit: int = Query(2000, ge=1, le=6000, description="Max points to return")):
    """Streams Geological Survey of India (GSI) recorded landslide points."""
    landslide_path = DATA_DIR / "hazards" / "landslide.geojson"
    if not landslide_path.exists():
        raise HTTPException(status_code=404, detail="Landslide layer file not found.")

    with open(landslide_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Return up to limit features for fast rendering
    features = data.get("features", [])[:limit]
    return {
        "type": "FeatureCollection",
        "name": "Uttarakhand_Landslide_Inventory",
        "features": features
    }


@router.get("/earthquakes", summary="Earthquake Epicenters GeoJSON Layer")
def get_earthquakes_geojson():
    """Streams earthquake epicenters (uttarakhand_earthquakes.geojson)."""
    eq_path = DATA_DIR / "hazards" / "uttarakhand_earthquakes.geojson"
    if not eq_path.exists():
        raise HTTPException(status_code=404, detail="Earthquake layer file not found.")

    with open(eq_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/rainfall", summary="Rainfall Monitoring Stations GeoJSON Layer")
def get_rainfall_geojson():
    """Streams precipitation monitoring stations (uttarakhand_rainfall.geojson)."""
    rf_path = DATA_DIR / "rainfall" / "uttarakhand_rainfall.geojson"
    if not rf_path.exists():
        raise HTTPException(status_code=404, detail="Rainfall layer file not found.")

    with open(rf_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/emergency-services", summary="Emergency Infrastructure GeoJSON Layer")
def get_emergency_services_geojson(
    service_type: Optional[str] = Query("all", enum=["all", "healthcare", "fire", "police"])
):
    """Returns emergency infrastructure points (hospitals, fire stations, police stations)."""
    features = []
    sources = []

    if service_type in ["all", "healthcare"]:
        sources.append((DATA_DIR / "infrastructure" / "emergency" / "healthcare.geojson", "Hospital", "#007bff"))
    if service_type in ["all", "fire"]:
        sources.append((DATA_DIR / "infrastructure" / "emergency" / "firestation.geojson", "Fire Station", "#dc3545"))
    if service_type in ["all", "police"]:
        sources.append((DATA_DIR / "infrastructure" / "emergency" / "policestation.geojson", "Police Station", "#343a40"))

    for filepath, stype, color in sources:
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    gj = json.load(f)
                for feat in gj.get("features", [])[:300]:
                    props = feat.get("properties", {}) or {}
                    props["facility_type"] = stype
                    props["marker_color"] = color
                    features.append(feat)
            except Exception:
                pass

    return {
        "type": "FeatureCollection",
        "name": f"Uttarakhand_Emergency_{service_type.title()}",
        "features": features
    }


@router.get("/india-country-boundary", summary="India National Boundary GeoJSON Layer")
def get_india_country_boundary():
    """Streams India's national country boundary polygon in WGS84 with crisp vector lines."""
    p = _PROJECT_ROOT / "data" / "india_country_boundary.geojson"
    if not p.exists():
        raise HTTPException(status_code=404, detail="India country boundary file not found.")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/india-states", summary="India All States & UTs Boundaries GeoJSON Layer")
def get_india_states_boundary():
    """Streams all 35 Indian States and Union Territories boundary polygons in WGS84."""
    p = _PROJECT_ROOT / "data" / "india_states_simplified.geojson"
    if not p.exists():
        raise HTTPException(status_code=404, detail="India states boundary file not found.")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

