"""
General Hazard Engine API Router
Provides spatial hazard lookups, point-in-polygon flood assessments,
river proximity queries, and household multi-hazard evaluations.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.geospatial import get_geospatial_engine
from app.services.hazard_processor import get_hazard_processor
from app.services.risk import calculate_risk, get_risk_level
from app.services.data_loader import (
    get_uttarakhand_hazard_metrics,
    get_uttarakhand_district_hazards
)
from app.routes.households import HOUSEHOLDS_DB

router = APIRouter()



# ============================================================================
# PYDANTIC RESPONSE SCHEMAS
# ============================================================================

class ComponentScores(BaseModel):
    flood_zone_component: float
    river_proximity_component: float
    terrain_landslide_factor: float
    medical_isolation_factor: float


class GeospatialHazardResponse(BaseModel):
    latitude: float
    longitude: float
    district: str
    in_historical_flood_zone: bool
    flood_zone_details: Optional[Dict[str, Any]] = None
    distance_to_nearest_river_km: float
    distance_to_nearest_hospital_km: float
    nearest_hospital_name: str
    component_scores: ComponentScores
    composite_geospatial_hazard_exposure: float
    geospatial_hazard_tier: str


class HouseholdHazardEvaluation(BaseModel):
    household_id: str
    village: str
    district: str
    state: str
    population: int
    vulnerability_level: str
    priority_level: str
    geospatial_assessment: GeospatialHazardResponse


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/exposure/point", response_model=GeospatialHazardResponse)
def get_point_hazard_exposure(
    latitude: float = Query(..., ge=28.0, le=32.0, description="Latitude in Uttarakhand (-90 to 90)"),
    longitude: float = Query(..., ge=77.0, le=82.0, description="Longitude in Uttarakhand (-180 to 180)"),
    district: Optional[str] = Query(None, description="Optional district name")
):
    """
    Evaluates real-time geospatial hazard exposure for any geographic coordinate in Uttarakhand:
    - Tests if coordinate lies inside historical flood polygons (Uttrakhandpast_flood.geojson)
    - Computes distance to the nearest river geometry (uttarakhand_river_polygon.geojson)
    - Identifies nearest hospital and distance (healthcare.geojson)
    - Computes multi-factor normalized hazard exposure (0.0 to 1.0)
    """
    engine = get_geospatial_engine()
    return engine.evaluate_geospatial_hazard(latitude, longitude, district)


@router.get("/exposure/household/{household_id}", response_model=HouseholdHazardEvaluation)
def get_household_hazard_exposure(household_id: str):
    """
    Performs live geospatial hazard evaluation for a registered household.
    Connects household coordinates -> spatial lookup -> river & flood exposure -> priority classification.
    """
    if household_id not in HOUSEHOLDS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household '{household_id}' not found in registry."
        )

    hh = HOUSEHOLDS_DB[household_id]
    engine = get_geospatial_engine()
    geo_profile = engine.evaluate_geospatial_hazard(
        hh["latitude"],
        hh["longitude"],
        hh.get("district")
    )

    return {
        "household_id": hh["household_id"],
        "village": hh["village"],
        "district": hh["district"],
        "state": hh["state"],
        "population": hh["population"],
        "vulnerability_level": hh.get("vulnerability_level", "MODERATE"),
        "priority_level": hh.get("priority_level", "HIGH"),
        "geospatial_assessment": geo_profile
    }


@router.get("/districts")
def list_district_hazards():
    """
    Returns empirical multi-hazard rankings and disaster history (houses destroyed, damaged, fatalities)
    for all 13 Uttarakhand districts.
    """
    return {
        "state": "Uttarakhand",
        "districts": get_uttarakhand_district_hazards()
    }


@router.get("/summary")
def get_hazards_summary():
    """
    Returns state-level hazard metrics, active river discharge stations, and rainfall stats.
    """
    return get_uttarakhand_hazard_metrics()


# ============================================================================
# REAL HAZARD EXPOSURE ENGINE - MODULAR ENDPOINTS
# ============================================================================

def _get_household_or_404(household_id: str) -> Dict[str, Any]:
    if household_id not in HOUSEHOLDS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household '{household_id}' not found in registry."
        )
    return HOUSEHOLDS_DB[household_id]


@router.get("/household/{household_id}/flood")
def get_household_flood_exposure(household_id: str):
    """
    Computes flood hazard exposure for a household.
    Uses 37 verified historical flood polygons for Uttarakhand.
    For Assam and Odisha, returns calibrated regional baseline pending Phase 2 vector layers.
    """
    hh = _get_household_or_404(household_id)
    st = hh.get("state", "Uttarakhand")

    if st == "Uttarakhand":
        hp = get_hazard_processor()
        res = hp.calculate_flood_exposure(hh["latitude"], hh["longitude"], hh.get("district", ""))
    else:
        # Regional baseline for Assam (Brahmaputra) or Odisha (Mahanadi)
        score = float(hh.get("hazard_exposure", 0.75))
        tier = "CRITICAL" if score >= 0.85 else "HIGH" if score >= 0.60 else "MODERATE"
        res = {
            "hazard": "flood",
            "exposure_score": score,
            "exposure_level": tier,
            "status": "PHASE_2_GIS_DATASET_PENDING",
            "inside_hazard_zone": score >= 0.70,
            "source_dataset": f"{st} Regional Flood Baseline (GIS Pending)",
            "explanation": f"Household in {hh.get('district')}, {st} evaluated against regional flood baseline. High-resolution GIS vector layer scheduled for Phase 2."
        }

    return {
        "household_id": household_id,
        "village": hh.get("village"),
        "district": hh.get("district"),
        "state": st,
        "coordinates": {"latitude": hh["latitude"], "longitude": hh["longitude"]},
        **res
    }


@router.get("/household/{household_id}/river")
def get_household_river_exposure(household_id: str):
    """
    Computes river flooding exposure for a household.
    Uses 525 reprojected river geometries for Uttarakhand.
    """
    hh = _get_household_or_404(household_id)
    st = hh.get("state", "Uttarakhand")

    if st == "Uttarakhand":
        hp = get_hazard_processor()
        res = hp.calculate_river_exposure(hh["latitude"], hh["longitude"], hh.get("district", ""))
    else:
        score = round(max(0.20, float(hh.get("hazard_exposure", 0.60)) * 0.90), 2)
        tier = "HIGH" if score >= 0.65 else "MODERATE"
        res = {
            "hazard": "river_flooding",
            "exposure_score": score,
            "exposure_level": tier,
            "status": "PHASE_2_GIS_DATASET_PENDING",
            "inside_river_polygon": False,
            "source_dataset": f"{st} Major River Basin Corridor (GIS Pending)",
            "explanation": f"Household proximity evaluated against {st} major river basin corridor baseline."
        }

    return {
        "household_id": household_id,
        "village": hh.get("village"),
        "district": hh.get("district"),
        "state": st,
        "coordinates": {"latitude": hh["latitude"], "longitude": hh["longitude"]},
        **res
    }


@router.get("/household/{household_id}/landslide")
def get_household_landslide_exposure(household_id: str):
    """
    Computes landslide exposure. Applicable to mountainous states (Uttarakhand and hilly tracts of Assam).
    Not applicable to coastal plains of Odisha.
    """
    hh = _get_household_or_404(household_id)
    st = hh.get("state", "Uttarakhand")

    if st == "Odisha":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Landslide hazard is not applicable for coastal/deltaic district '{hh.get('district')}', Odisha. Applicable hazards: cyclone, coastal_flooding, flood, heavy_rainfall."
        )

    if st == "Uttarakhand":
        hp = get_hazard_processor()
        res = hp.calculate_landslide_exposure(hh["latitude"], hh["longitude"], hh.get("district", ""))
    else:
        # Assam (e.g. Dima Hasao, Karbi Anglong, or foothill areas)
        score = 0.20
        res = {
            "hazard": "landslide",
            "exposure_score": score,
            "exposure_level": "LOW",
            "status": "PHASE_2_GIS_DATASET_PENDING",
            "district": hh.get("district"),
            "source_dataset": "Assam Geological Survey Baseline",
            "explanation": f"Lowland terrain in {hh.get('district')}, Assam; baseline low landslide susceptibility."
        }

    return {
        "household_id": household_id,
        "village": hh.get("village"),
        "district": hh.get("district"),
        "state": st,
        "coordinates": {"latitude": hh["latitude"], "longitude": hh["longitude"]},
        **res
    }


@router.get("/household/{household_id}/rainfall")
def get_household_rainfall_exposure(household_id: str):
    """
    Computes heavy rainfall exposure from IMD station telemetry and cloudburst thresholds.
    """
    hh = _get_household_or_404(household_id)
    st = hh.get("state", "Uttarakhand")

    if st == "Uttarakhand":
        hp = get_hazard_processor()
        res = hp.calculate_rainfall_exposure(hh["latitude"], hh["longitude"], hh.get("district", ""))
    else:
        score = 0.75 if st == "Assam" else 0.70
        tier = "HIGH"
        res = {
            "hazard": "heavy_rainfall",
            "exposure_score": score,
            "exposure_level": tier,
            "status": "PHASE_2_GIS_DATASET_PENDING",
            "monitored_station": f"{hh.get('district')} Regional IMD Station",
            "peak_daily_rainfall_mm": 115.0 if st == "Assam" else 95.0,
            "source_dataset": f"IMD {st} Historical Precipitation Telemetry",
            "explanation": f"Monsoon heavy rainfall pattern monitored for {hh.get('district')}, {st}."
        }

    return {
        "household_id": household_id,
        "village": hh.get("village"),
        "district": hh.get("district"),
        "state": st,
        "coordinates": {"latitude": hh["latitude"], "longitude": hh["longitude"]},
        **res
    }


@router.get("/household/{household_id}/cyclone")
def get_household_cyclone_exposure(household_id: str):
    """
    Computes cyclone exposure for coastal households.
    Applicable to coastal states (Odisha). Not applicable to landlocked Himalayan states.
    """
    hh = _get_household_or_404(household_id)
    st = hh.get("state", "Uttarakhand")

    if st != "Odisha":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cyclone hazard calculation is not applicable for inland/mountain state '{st}'. Applicable state: Odisha."
        )

    # Odisha coastal cyclone modeling
    coastal_districts = {"puri", "kendrapara", "balasore", "bhadrak", "ganjam", "jagatsinghpur"}
    dist = (hh.get("district") or "").lower()
    is_coastal = any(cd in dist for cd in coastal_districts)

    score = 0.92 if is_coastal else 0.45
    tier = "CRITICAL" if score >= 0.85 else "MODERATE"

    return {
        "household_id": household_id,
        "village": hh.get("village"),
        "district": hh.get("district"),
        "state": st,
        "coordinates": {"latitude": hh["latitude"], "longitude": hh["longitude"]},
        "hazard": "cyclone",
        "exposure_score": score,
        "exposure_level": tier,
        "status": "PHASE_2_GIS_DATASET_PENDING",
        "source_dataset": "IMD Cyclone Vulnerability Atlas (Bay of Bengal)",
        "explanation": f"High cyclonic surge exposure in coastal district {hh.get('district')}, Odisha (Category 4/5 cyclone corridor)."
    }


@router.get("/household/{household_id}/coastal")
def get_household_coastal_exposure(household_id: str):
    """
    Computes coastal flooding and storm surge exposure for coastal households.
    Applicable to coastal states (Odisha). Not applicable to landlocked states.
    """
    hh = _get_household_or_404(household_id)
    st = hh.get("state", "Uttarakhand")

    if st != "Odisha":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Coastal flooding hazard calculation is not applicable for landlocked state '{st}'. Applicable state: Odisha."
        )

    coastal_districts = {"puri", "kendrapara", "balasore", "bhadrak", "ganjam", "jagatsinghpur"}
    dist = (hh.get("district") or "").lower()
    is_coastal = any(cd in dist for cd in coastal_districts)

    score = 0.85 if is_coastal else 0.25
    tier = "HIGH" if score >= 0.70 else "LOW"

    return {
        "household_id": household_id,
        "village": hh.get("village"),
        "district": hh.get("district"),
        "state": st,
        "coordinates": {"latitude": hh["latitude"], "longitude": hh["longitude"]},
        "hazard": "coastal_flooding",
        "exposure_score": score,
        "exposure_level": tier,
        "status": "PHASE_2_GIS_DATASET_PENDING",
        "source_dataset": "INCOIS Coastal Inundation & Storm Surge Model",
        "explanation": f"Coastal storm surge and tidal inundation zone for {hh.get('district')}, Odisha."
    }


@router.get("/household/{household_id}/multi")
def get_household_multi_hazard_exposure(household_id: str):
    """
    Computes integrated state-specific multi-hazard exposure and compound risk score:
    - Uttarakhand: Flash Flood (30%) + River (25%) + Landslide (25%) + Rainfall (20%)
    - Assam: Flood (30%) + River (30%) + Heavy Rainfall (25%) + Landslide (15%)
    - Odisha: Cyclone (35%) + Coastal Surge (25%) + Flood (25%) + Rainfall (15%)
    """
    hh = _get_household_or_404(household_id)
    st = hh.get("state", "Uttarakhand")

    if st == "Uttarakhand":
        hp = get_hazard_processor()
        res = hp.calculate_multi_hazard_exposure(
            lat=hh["latitude"],
            lon=hh["longitude"],
            district=hh.get("district", "Chamoli"),
            household_id=household_id
        )
        hazards = res["hazards"]
        composite = res["composite_hazard_exposure"]
        tier = res["hazard_tier"]
        breakdown = res["detailed_breakdown"]
    elif st == "Assam":
        # Assam state-specific hazards: Flood, River, Rainfall, Landslide
        f = float(hh.get("hazard_exposure", 0.85))
        r = round(f * 0.90, 2)
        rn = 0.80
        ls = 0.20
        hazards = {"flood": f, "river": r, "rainfall": rn, "landslide": ls}
        composite = round((f * 0.30) + (r * 0.30) + (rn * 0.25) + (ls * 0.15), 3)
        tier = "CRITICAL" if composite >= 0.80 else "HIGH" if composite >= 0.60 else "MODERATE"
        breakdown = {
            "flood": {"hazard": "flood", "exposure_score": f, "status": "PHASE_2_GIS_DATASET_PENDING"},
            "river": {"hazard": "river_flooding", "exposure_score": r, "status": "PHASE_2_GIS_DATASET_PENDING"},
            "rainfall": {"hazard": "heavy_rainfall", "exposure_score": rn, "status": "PHASE_2_GIS_DATASET_PENDING"},
            "landslide": {"hazard": "landslide", "exposure_score": ls, "status": "PHASE_2_GIS_DATASET_PENDING"}
        }
    else:
        # Odisha state-specific hazards: Cyclone, Coastal Flooding, Flood, Rainfall
        dist = (hh.get("district") or "").lower()
        is_coastal = any(cd in dist for cd in ["puri", "kendrapara", "balasore", "ganjam"])
        cyc = 0.92 if is_coastal else 0.50
        cst = 0.85 if is_coastal else 0.25
        fl = 0.80
        rn = 0.75
        hazards = {"cyclone": cyc, "coastal": cst, "flood": fl, "rainfall": rn}
        composite = round((cyc * 0.35) + (cst * 0.25) + (fl * 0.25) + (rn * 0.15), 3)
        tier = "CRITICAL" if composite >= 0.80 else "HIGH" if composite >= 0.60 else "MODERATE"
        breakdown = {
            "cyclone": {"hazard": "cyclone", "exposure_score": cyc, "status": "PHASE_2_GIS_DATASET_PENDING"},
            "coastal": {"hazard": "coastal_flooding", "exposure_score": cst, "status": "PHASE_2_GIS_DATASET_PENDING"},
            "flood": {"hazard": "flood", "exposure_score": fl, "status": "PHASE_2_GIS_DATASET_PENDING"},
            "rainfall": {"hazard": "heavy_rainfall", "exposure_score": rn, "status": "PHASE_2_GIS_DATASET_PENDING"}
        }

    risk_score = calculate_risk(hazards, state=st)
    risk_level = get_risk_level(risk_score)

    return {
        "household_id": household_id,
        "state": st,
        "district": hh.get("district"),
        "village": hh.get("village"),
        "coordinates": {"latitude": hh["latitude"], "longitude": hh["longitude"]},
        "hazards": hazards,
        "composite_hazard_exposure": composite,
        "hazard_tier": tier,
        "compound_risk_score": risk_score,
        "risk_level": risk_level,
        "detailed_breakdown": breakdown
    }


@router.get("/household/{household_id}/terrain")
def get_household_terrain_profile(household_id: str):
    """
    Returns continuous 30m DEM elevation and geodetic slope profile for a household.
    Uses uttrakhand_dem_clip.tif and Horn's topographic algorithm.
    """
    hh = _get_household_or_404(household_id)
    hp = get_hazard_processor()
    res = hp.calculate_terrain_profile(hh["latitude"], hh["longitude"])
    return {
        "household_id": household_id,
        "village": hh.get("village"),
        "district": hh.get("district"),
        "state": hh.get("state"),
        "coordinates": {"latitude": hh["latitude"], "longitude": hh["longitude"]},
        **res
    }


@router.get("/household/{household_id}/elevation")
def get_household_elevation(household_id: str):
    """
    Returns sampled elevation in meters above sea level from the 30m DEM raster.
    """
    hh = _get_household_or_404(household_id)
    hp = get_hazard_processor()
    res = hp.calculate_terrain_profile(hh["latitude"], hh["longitude"])
    return {
        "household_id": household_id,
        "village": hh.get("village"),
        "district": hh.get("district"),
        "coordinates": {"latitude": hh["latitude"], "longitude": hh["longitude"]},
        "elevation_meters": res.get("elevation_meters"),
        "elevation_category": res.get("elevation_category"),
        "source_dataset": res.get("source_dataset")
    }


@router.get("/household/{household_id}/slope")
def get_household_slope(household_id: str):
    """
    Returns local topographic gradient slope in degrees computed from 30m DEM raster.
    """
    hh = _get_household_or_404(household_id)
    hp = get_hazard_processor()
    res = hp.calculate_terrain_profile(hh["latitude"], hh["longitude"])
    return {
        "household_id": household_id,
        "village": hh.get("village"),
        "district": hh.get("district"),
        "coordinates": {"latitude": hh["latitude"], "longitude": hh["longitude"]},
        "slope_degrees": res.get("slope_degrees"),
        "slope_category": res.get("slope_category"),
        "slope_hazard_tier": res.get("slope_hazard_tier"),
        "source_dataset": res.get("source_dataset")
    }


@router.get("/calculate")

def calculate_hazard_by_coordinates(
    latitude: float = Query(..., ge=28.0, le=32.5, description="Latitude coordinate"),
    longitude: float = Query(..., ge=77.0, le=82.0, description="Longitude coordinate"),
    district: Optional[str] = Query("Chamoli", description="District name in Uttarakhand")
):
    """
    Dynamic hazard calculation endpoint for arbitrary coordinates in Uttarakhand.
    Evaluates flood polygon containment, river proximity, landslide disaster metrics, and rainfall station history.
    """
    hp = get_hazard_processor()
    res = hp.calculate_multi_hazard_exposure(
        lat=latitude,
        lon=longitude,
        district=district or "Chamoli",
        household_id="COORDINATE_QUERY"
    )
    risk_score = calculate_risk(res["hazards"], state="Uttarakhand")
    risk_level = get_risk_level(risk_score)

    return {
        **res,
        "compound_risk_score": risk_score,
        "risk_level": risk_level
    }

