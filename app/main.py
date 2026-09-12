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


@app.get("/map", tags=["GIS & Maps"], summary="Interactive GIS Map")
def get_gis_map():
    """Serves the interactive Leaflet GIS visualization map."""
    map_path = STATIC_DIR / "map.html"
    if map_path.exists():
        return FileResponse(str(map_path))
    return {"error": "map.html not found"}


@app.get("/", tags=["General"])
def root():
    summary = get_pilot_summary()
    return {
        "project": "Project AASRA",
        "message": "Project AASRA Disaster Resilience API is running",
        "description": "Disaster Resilience & Relocation Intelligence System",
        "active_pilot": "Uttarakhand",
        "status": "online",
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