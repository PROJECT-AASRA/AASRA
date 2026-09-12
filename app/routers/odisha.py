from fastapi import APIRouter

router = APIRouter(
    prefix="/odisha",
    tags=["Odisha (Upcoming)"]
)


@router.get("/")
def odisha():
    return {
        "state": "Odisha",
        "status": "PILOT_PENDING_PHASE_2",
        "message": "Odisha coastal, cyclone, and tidal surge modules will be onboarded in Phase 2. Currently active pilot: Uttarakhand.",
        "planned_hazards": [
            "Tropical Cyclones",
            "Coastal Storm Surge",
            "Heavy Rainfall",
            "Riverine Floods"
        ]
    }


@router.get("/hazards")
def odisha_hazards():
    return {
        "state": "Odisha",
        "status": "PILOT_PENDING",
        "message": "Coastal buoy and cyclone track ingestion pending Phase 2 expansion.",
        "hazards": {}
    }


@router.get("/risk")
def odisha_risk():
    return {
        "state": "Odisha",
        "status": "PILOT_PENDING",
        "risk_score": None,
        "risk_level": "PENDING_TELEMETRY"
    }
