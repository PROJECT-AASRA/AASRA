from fastapi import APIRouter

router = APIRouter(
    prefix="/assam",
    tags=["Assam (Upcoming)"]
)


@router.get("/")
def assam():
    return {
        "state": "Assam",
        "status": "PILOT_PENDING_PHASE_2",
        "message": "Assam regional hazard, telemetry, and shelter modules will be onboarded in Phase 2. Currently active pilot: Uttarakhand.",
        "planned_hazards": [
            "Brahmaputra River Flooding",
            "Flash Floods",
            "Monsoon Heavy Rainfall",
            "Riverbank Erosion"
        ]
    }


@router.get("/hazards")
def assam_hazards():
    return {
        "state": "Assam",
        "status": "PILOT_PENDING",
        "message": "Telemetry sensor ingestion pending Phase 2 expansion.",
        "hazards": {}
    }


@router.get("/risk")
def assam_risk():
    return {
        "state": "Assam",
        "status": "PILOT_PENDING",
        "risk_score": None,
        "risk_level": "PENDING_TELEMETRY"
    }
