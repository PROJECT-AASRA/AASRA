import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import uttarakhand, assam, odisha
from app.routes import households, relocation, hazards, gis, assessment
from app.services.data_loader import get_pilot_summary

app = FastAPI(
    title="Project AASRA (Disaster Resilience & Relocation API)",
    description=(
        "Backend platform for disaster risk intelligence, demographic vulnerability mapping, "
        "and emergency relocation planning. Currently featuring the active Uttarakhand Pilot "
        "powered by real Census, OSM, and CWC/IMD disaster datasets."
    ),
    version="1.3.0"
)

# Active regional hazard routers
app.include_router(uttarakhand.router)
app.include_router(assam.router)
app.include_router(odisha.router)

# Core demographic, hazard, and relocation management routers
app.include_router(households.router, prefix="/households", tags=["Households"])
app.include_router(relocation.router, prefix="/relocation", tags=["Relocation"])
app.include_router(hazards.router, prefix="/hazards", tags=["Hazard Engine"])
app.include_router(gis.router, prefix="/gis", tags=["GIS & Maps"])
app.include_router(assessment.router, prefix="/assessment", tags=["Disaster Assessment & Decision Engine"])

# Mount static frontend assets
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

from app.database import engine, Base
from app.seed_db import seed_database
from app.routes.households import sync_households_from_db
from app.routes.relocation import sync_shelters_from_db


@app.on_event("startup")
def startup_db_init():
    """Initializes SQLite database, applies schema, seeds baseline data, and syncs caches."""
    Base.metadata.create_all(bind=engine)
    seed_database()
    sync_households_from_db()
    sync_shelters_from_db()


import math
from typing import Optional
from fastapi import Query, Depends
from sqlalchemy.orm import Session
from app.database import get_db

@app.get("/map", tags=["GIS & Maps"], summary="Interactive GIS Map")
def get_gis_map():
    """Serves the interactive Leaflet GIS visualization map."""
    map_path = STATIC_DIR / "map.html"
    if map_path.exists():
        return FileResponse(str(map_path))
    return {"error": "map.html not found"}


@app.get("/dashboard", tags=["Frontend"], summary="AASRA Assessment Console & Map Dashboard")
@app.get("/assessment", tags=["Frontend"], summary="AASRA Assessment Console & Map Dashboard")
@app.get("/console", tags=["Frontend"], summary="AASRA Assessment Console & Map Dashboard")
@app.get("/AASRA_v1_frontend_no_timeline.html", tags=["Frontend"], summary="AASRA Assessment Console & Map Dashboard")
def get_assessment_dashboard():
    """Serves the AI-Assisted Safe Relocation & Assessment Dashboard."""
    dash_path = STATIC_DIR / "AASRA_v1_frontend_no_timeline.html"
    if dash_path.exists():
        return FileResponse(str(dash_path))
    return {"error": "Dashboard not found"}


@app.get("/", tags=["Frontend"], summary="AASRA Front Page")
@app.get("/home", tags=["Frontend"], summary="AASRA Front Page")
@app.get("/frontpage", tags=["Frontend"], summary="AASRA Front Page")
@app.get("/AASRA_finalfrontpage_ready.html", tags=["Frontend"], summary="AASRA Front Page")
def get_landing_page():
    """Serves the AASRA interactive frontend landing page."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return FileResponse(str(STATIC_DIR / "AASRA_finalfrontpage_ready.html"))


@app.get("/api", tags=["General"], summary="API Status & Pilot Metrics")
def api_root():
    """Provides machine-readable Project AASRA API metadata and pilot metrics."""
    summary = get_pilot_summary()
    return {
        "project": "Project AASRA",
        "message": "Project AASRA Disaster Resilience API is running",
        "description": "Disaster Resilience & Relocation Intelligence System",
        "active_pilot": "Uttarakhand",
        "status": "online",
        "frontend": "/",
        "gis_map": "/map",
        "pilot_stats": {
            "shelters_ready": summary["total_shelters_loaded"],
            "total_shelter_capacity": summary["total_shelter_capacity"],
            "vulnerable_households_indexed": summary["vulnerable_households_indexed"],
            "districts_monitored": summary["districts_covered"]
        },
        "docs": "/docs",
        "redoc": "/redoc"
    }

root = api_root


@app.get("/api/locate", tags=["GIS & Maps"], summary="Auto-detect State & District from Coordinates")
def locate_from_coords(
    lat: float = Query(..., description="GPS Latitude"),
    lon: float = Query(..., description="GPS Longitude")
):
    """
    Reverse-geolocates user's GPS coordinates to the nearest supported State and District.
    Powers the 'Use my current location' toggle on the front page.
    """
    from app.services.data_loader import DISTRICT_CENTERS

    state_centers = {
        "Uttarakhand": (30.0668, 79.0193),
        "Assam": (26.2006, 92.9376),
        "Odisha": (20.9517, 85.0985),
    }

    def calc_dist(c1, c2):
        return math.hypot(c1[0] - c2[0], c1[1] - c2[1])

    nearest_state = min(state_centers.keys(), key=lambda s: calc_dist((lat, lon), state_centers[s]))

    matched_district = "Dehradun"
    if nearest_state == "Uttarakhand":
        matched_district = min(DISTRICT_CENTERS.keys(), key=lambda d: calc_dist((lat, lon), DISTRICT_CENTERS[d]))
    elif nearest_state == "Assam":
        assam_centers = {
            "Dhubri": (26.02, 89.97), "Morigaon": (26.25, 92.34), "Barpeta": (26.32, 91.0),
            "Kamrup": (26.31, 91.60), "Cachar": (24.83, 92.8)
        }
        matched_district = min(assam_centers.keys(), key=lambda d: calc_dist((lat, lon), assam_centers[d]))
    elif nearest_state == "Odisha":
        odisha_centers = {
            "Puri": (19.81, 85.83), "Kendrapara": (20.50, 86.42), "Balasore": (21.49, 86.93),
            "Ganjam": (19.38, 85.05), "Khordha": (20.18, 85.62)
        }
        matched_district = min(odisha_centers.keys(), key=lambda d: calc_dist((lat, lon), odisha_centers[d]))

    return {
        "state": nearest_state,
        "district": matched_district,
        "latitude": lat,
        "longitude": lon
    }


@app.get("/api/districts", tags=["General"], summary="Get Districts for a State")
def get_districts_by_state(state: str = Query(..., description="State name")):
    """Returns official districts supported in Project AASRA for the selected state."""
    from app.services.data_loader import DISTRICT_CENTERS
    s = state.strip().lower()
    if s == "uttarakhand":
        return {"state": "Uttarakhand", "districts": sorted(list(DISTRICT_CENTERS.keys()))}
    elif s == "assam":
        return {"state": "Assam", "districts": ["Barpeta", "Cachar", "Dhubri", "Kamrup", "Morigaon"]}
    elif s == "odisha":
        return {"state": "Odisha", "districts": ["Balasore", "Ganjam", "Kendrapara", "Khordha", "Puri"]}
    else:
        return {"state": state, "districts": []}


@app.get("/api/danger-levels", tags=["Hazard Engine"], summary="Get Uttarakhand Danger Levels from Database")
def get_danger_levels_api(db: Session = Depends(get_db)):
    """Fetches all district hazard classifications directly from SQLite danger_levels table."""
    conn = db.connection().connection
    cur = conn.cursor()
    cur.execute("SELECT district, danger_level, danger_index, main_risk, reference_period, data_status FROM danger_levels ORDER BY danger_index DESC")
    rows = cur.fetchall()
    return [
        {
            "district": r[0],
            "danger_level": r[1],
            "danger_index": r[2],
            "main_risk": r[3],
            "reference_period": r[4],
            "data_status": r[5]
        }
        for r in rows
    ]


@app.get("/health", tags=["General"])
def health():
    return {
        "status": "healthy",
        "pilot": "Uttarakhand"
    }


@app.get("/states", tags=["General"])
def states():
    return {
        "active_pilot": ["Uttarakhand"],
        "upcoming_pilots": ["Assam", "Odisha"],
        "pilot_focus": "Uttarakhand (Himalayan Cloudburst, Landslide & River Flooding Resilience)"
    }