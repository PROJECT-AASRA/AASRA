from fastapi import APIRouter
from app.services.risk import calculate_risk, get_risk_level
from app.services.data_loader import (
    get_uttarakhand_hazard_metrics,
    get_uttarakhand_district_hazards,
    get_pilot_summary
)

router = APIRouter(
    prefix="/uttarakhand",
    tags=["Uttarakhand"]
)


@router.get("/")
def uttarakhand():
    return {
        "state": "Uttarakhand",
        "status": "ACTIVE_PILOT",
        "region": "Himalayan",
        "major_hazards": [
            "Landslide",
            "Flash Flood",
            "Heavy Rainfall / Cloudburst",
            "River Flooding"
        ],
        "description": "Active disaster resilience and relocation pilot covering 13 Himalayan districts."
    }


@router.get("/summary")
def uttarakhand_summary():
    """Returns a comprehensive status summary of the Uttarakhand pilot, including loaded shelters, capacity, and telemetry."""
    return get_pilot_summary()


@router.get("/hazards")
def uttarakhand_hazards():
    """Returns calibrated multi-hazard severity metrics computed from real IMD & river telemetry datasets."""
    return get_uttarakhand_hazard_metrics()


@router.get("/risk")
def uttarakhand_risk():
    """Calculates state-wide aggregate multi-hazard compound risk score and alert tier."""
    hazard_data = get_uttarakhand_hazard_metrics()
    hazards = hazard_data.get("hazards", {})
    score = calculate_risk(hazards)

    return {
        "state": "Uttarakhand",
        "risk_score": score,
        "risk_level": get_risk_level(score),
        "active_telemetry": hazard_data.get("telemetry_summary", {})
    }


@router.get("/districts")
def uttarakhand_districts():
    """Returns localized risk scores, alert levels, and historical disaster counts for all 13 districts."""
    return {
        "state": "Uttarakhand",
        "total_districts": 13,
        "districts": get_uttarakhand_district_hazards()
    }
