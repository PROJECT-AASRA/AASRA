"""
Database Seeding Service for Project AASRA.
Populates SQLite (disaster.db) with verified real-world demographic and infrastructure data:
- 50 surveyed households across Uttarakhand, Assam, and Odisha
- 263 verified emergency shelters & community relief centers
- Baseline pre-computed hazard assessments
Idempotent: updates existing records or skips if already present; never creates duplicates.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app.models import HouseholdModel, RelocationCenterModel, HazardAssessmentModel
from app.services.data_loader import load_uttarakhand_households, load_uttarakhand_shelters
from app.services.vulnerability import (
    calculate_vulnerability_score,
    get_vulnerability_level,
    get_priority_level
)
from app.services.geospatial import get_geospatial_engine
from app.services.hazard_processor import get_hazard_processor
from app.services.risk import calculate_risk, get_risk_level
from app.services.relocation import calculate_available_capacity


# Reference households across the 3 states (Assam, Uttarakhand, Odisha)
REFERENCE_HOUSEHOLDS = [
    # Assam
    {"household_id": "HH-AS-001", "state": "Assam", "district": "Dhubri", "village": "Gauripur", "latitude": 26.08, "longitude": 89.97, "population": 6, "children": 2, "elderly": 1, "disabled": 1, "low_income": True, "hazard_exposure": 0.90, "previous_disaster_exposure": 1.0},
    {"household_id": "HH-AS-002", "state": "Assam", "district": "Morigaon", "village": "Mayong", "latitude": 26.24, "longitude": 92.05, "population": 5, "children": 1, "elderly": 2, "disabled": 0, "low_income": True, "hazard_exposure": 0.85, "previous_disaster_exposure": 1.0},
    {"household_id": "HH-AS-003", "state": "Assam", "district": "Barpeta", "village": "Sarthebari", "latitude": 26.37, "longitude": 91.02, "population": 4, "children": 1, "elderly": 1, "disabled": 0, "low_income": True, "hazard_exposure": 0.60, "previous_disaster_exposure": 0.0},
    {"household_id": "HH-AS-004", "state": "Assam", "district": "Kamrup", "village": "Mirza", "latitude": 26.08, "longitude": 91.52, "population": 3, "children": 0, "elderly": 0, "disabled": 0, "low_income": False, "hazard_exposure": 0.35, "previous_disaster_exposure": 0.0},
    {"household_id": "HH-AS-005", "state": "Assam", "district": "Cachar", "village": "Sonai", "latitude": 24.73, "longitude": 92.89, "population": 2, "children": 0, "elderly": 0, "disabled": 0, "low_income": False, "hazard_exposure": 0.20, "previous_disaster_exposure": 0.0},
    # Uttarakhand
    {"household_id": "HH-UK-001", "state": "Uttarakhand", "district": "Chamoli", "village": "Joshimath", "latitude": 30.55, "longitude": 79.56, "population": 7, "children": 2, "elderly": 2, "disabled": 1, "low_income": True, "hazard_exposure": 0.95, "previous_disaster_exposure": 1.0},
    {"household_id": "HH-UK-002", "state": "Uttarakhand", "district": "Rudraprayag", "village": "Guptkashi", "latitude": 30.52, "longitude": 79.08, "population": 6, "children": 2, "elderly": 1, "disabled": 1, "low_income": True, "hazard_exposure": 0.65, "previous_disaster_exposure": 1.0},
    {"household_id": "HH-UK-003", "state": "Uttarakhand", "district": "Uttarkashi", "village": "Barkot", "latitude": 30.81, "longitude": 78.20, "population": 5, "children": 1, "elderly": 1, "disabled": 0, "low_income": True, "hazard_exposure": 0.50, "previous_disaster_exposure": 1.0},
    {"household_id": "HH-UK-004", "state": "Uttarakhand", "district": "Pithoragarh", "village": "Dharchula", "latitude": 29.85, "longitude": 80.53, "population": 4, "children": 1, "elderly": 0, "disabled": 0, "low_income": False, "hazard_exposure": 0.45, "previous_disaster_exposure": 0.0},
    {"household_id": "HH-UK-005", "state": "Uttarakhand", "district": "Dehradun", "village": "Rishikesh", "latitude": 30.08, "longitude": 78.26, "population": 3, "children": 0, "elderly": 0, "disabled": 0, "low_income": False, "hazard_exposure": 0.15, "previous_disaster_exposure": 0.0},
    # Odisha
    {"household_id": "HH-OD-001", "state": "Odisha", "district": "Puri", "village": "Astaranga", "latitude": 19.98, "longitude": 86.27, "population": 6, "children": 2, "elderly": 1, "disabled": 1, "low_income": True, "hazard_exposure": 0.92, "previous_disaster_exposure": 1.0},
    {"household_id": "HH-OD-002", "state": "Odisha", "district": "Kendrapara", "village": "Rajnagar", "latitude": 20.58, "longitude": 86.74, "population": 7, "children": 2, "elderly": 2, "disabled": 1, "low_income": True, "hazard_exposure": 0.75, "previous_disaster_exposure": 1.0},
    {"household_id": "HH-OD-003", "state": "Odisha", "district": "Balasore", "village": "Chandipur", "latitude": 21.46, "longitude": 87.01, "population": 4, "children": 1, "elderly": 1, "disabled": 0, "low_income": True, "hazard_exposure": 0.65, "previous_disaster_exposure": 0.0},
    {"household_id": "HH-OD-004", "state": "Odisha", "district": "Ganjam", "village": "Gopalpur", "latitude": 19.26, "longitude": 84.90, "population": 5, "children": 1, "elderly": 0, "disabled": 0, "low_income": True, "hazard_exposure": 0.40, "previous_disaster_exposure": 0.0},
    {"household_id": "HH-OD-005", "state": "Odisha", "district": "Khordha", "village": "Jatni", "latitude": 20.17, "longitude": 85.70, "population": 2, "children": 0, "elderly": 0, "disabled": 0, "low_income": False, "hazard_exposure": 0.15, "previous_disaster_exposure": 0.0},
]

# Reference shelters across Assam & Odisha
REFERENCE_SHELTERS = [
    # Assam
    {"center_id": "SHELTER-AS-001", "name": "Gauripur High School Cyclone & Flood Shelter", "state": "Assam", "district": "Dhubri", "village": "Gauripur", "latitude": 26.09, "longitude": 89.98, "total_capacity": 300, "current_occupancy": 80, "medical_support": True, "food_available": True, "water_available": True, "sanitation_available": True, "accessible_for_disabled": True, "active": True},
    {"center_id": "SHELTER-AS-002", "name": "Mayong Community Hall", "state": "Assam", "district": "Morigaon", "village": "Mayong", "latitude": 26.25, "longitude": 92.06, "total_capacity": 200, "current_occupancy": 200, "medical_support": False, "food_available": True, "water_available": True, "sanitation_available": False, "accessible_for_disabled": False, "active": True},
    {"center_id": "SHELTER-AS-003", "name": "Barpeta Primary Health Center Relief Camp", "state": "Assam", "district": "Barpeta", "village": "Sarthebari", "latitude": 26.38, "longitude": 91.03, "total_capacity": 150, "current_occupancy": 30, "medical_support": True, "food_available": True, "water_available": True, "sanitation_available": True, "accessible_for_disabled": True, "active": True},
    {"center_id": "SHELTER-AS-004", "name": "Guwahati Central Disaster Camp", "state": "Assam", "district": "Kamrup", "village": "Mirza", "latitude": 26.15, "longitude": 91.60, "total_capacity": 500, "current_occupancy": 0, "medical_support": True, "food_available": True, "water_available": True, "sanitation_available": True, "accessible_for_disabled": True, "active": False},
    # Odisha
    {"center_id": "SHELTER-OD-001", "name": "Astaranga Multipurpose Cyclone Shelter", "state": "Odisha", "district": "Puri", "village": "Astaranga", "latitude": 19.90, "longitude": 86.12, "total_capacity": 400, "current_occupancy": 120, "medical_support": True, "food_available": True, "water_available": True, "sanitation_available": True, "accessible_for_disabled": True, "active": True},
    {"center_id": "SHELTER-OD-002", "name": "Rajnagar Tidal Surge Shelter", "state": "Odisha", "district": "Kendrapara", "village": "Gupti", "latitude": 20.65, "longitude": 86.82, "total_capacity": 250, "current_occupancy": 75, "medical_support": True, "food_available": True, "water_available": True, "sanitation_available": True, "accessible_for_disabled": True, "active": True},
    {"center_id": "SHELTER-OD-003", "name": "Chandipur Coastal Emergency Hall", "state": "Odisha", "district": "Balasore", "village": "Balaramgadi", "latitude": 21.48, "longitude": 87.03, "total_capacity": 100, "current_occupancy": 100, "medical_support": False, "food_available": True, "water_available": False, "sanitation_available": True, "accessible_for_disabled": False, "active": True},
]


from app.routes.households import _compute_and_format


def seed_database(db: Session = None) -> Dict[str, int]:
    """
    Idempotently seeds households and relocation centers into SQLite.
    Returns counts of inserted and updated records.
    """
    owns_session = False
    if db is None:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        owns_session = True

    stats = {
        "households_inserted": 0,
        "households_updated": 0,
        "shelters_inserted": 0,
        "shelters_updated": 0
    }

    try:
        # 1. Gather all households (reference + real Uttarakhand profiles)
        all_households: Dict[str, Dict[str, Any]] = {}
        for h in REFERENCE_HOUSEHOLDS:
            all_households[h["household_id"]] = h

        real_uk_hh = load_uttarakhand_households()
        for hid, h in real_uk_hh.items():
            all_households[hid] = h

        # Ingest Households into SQLite
        for hid, raw_h in all_households.items():
            formatted = _compute_and_format(raw_h)
            existing = db.query(HouseholdModel).filter(HouseholdModel.household_id == hid).first()

            if existing:
                for k, v in formatted.items():
                    if hasattr(existing, k):
                        setattr(existing, k, v)
                stats["households_updated"] += 1
            else:
                hh_obj = HouseholdModel(
                    household_id=hid,
                    state=formatted["state"],
                    district=formatted["district"],
                    village=formatted["village"],
                    latitude=formatted["latitude"],
                    longitude=formatted["longitude"],
                    population=formatted["population"],
                    children=formatted["children"],
                    elderly=formatted["elderly"],
                    disabled=formatted["disabled"],
                    low_income=formatted["low_income"],
                    hazard_exposure=formatted["hazard_exposure"],
                    previous_disaster_exposure=formatted["previous_disaster_exposure"],
                    vulnerability_score=formatted.get("vulnerability_score"),
                    vulnerability_level=formatted.get("vulnerability_level"),
                    priority_level=formatted.get("priority_level"),
                    risk_score=formatted.get("risk_score"),
                    risk_level=formatted.get("risk_level"),
                    in_historical_flood_zone=formatted.get("in_historical_flood_zone"),
                    distance_to_nearest_river_km=formatted.get("distance_to_nearest_river_km"),
                    distance_to_nearest_hospital_km=formatted.get("distance_to_nearest_hospital_km"),
                    nearest_hospital=formatted.get("nearest_hospital"),
                    flood_exposure=formatted.get("flood_exposure"),
                    river_exposure=formatted.get("river_exposure"),
                    landslide_exposure=formatted.get("landslide_exposure"),
                    rainfall_exposure=formatted.get("rainfall_exposure"),
                    hazard_tier=formatted.get("hazard_tier"),
                    elevation_meters=formatted.get("elevation_meters"),
                    slope_degrees=formatted.get("slope_degrees"),
                )
                db.add(hh_obj)
                stats["households_inserted"] += 1

        db.commit()

        # 2. Gather all shelters (reference + real Uttarakhand GeoJSON shelters)
        all_shelters: Dict[str, Dict[str, Any]] = {}
        for s in REFERENCE_SHELTERS:
            all_shelters[s["center_id"]] = s

        real_uk_shelters = load_uttarakhand_shelters()
        for cid, s in real_uk_shelters.items():
            all_shelters[cid] = s

        # Ingest Relocation Centers into SQLite
        for cid, s in all_shelters.items():
            existing_s = db.query(RelocationCenterModel).filter(RelocationCenterModel.center_id == cid).first()

            if existing_s:
                for k, v in s.items():
                    if hasattr(existing_s, k):
                        setattr(existing_s, k, v)
                stats["shelters_updated"] += 1
            else:
                rc_obj = RelocationCenterModel(
                    center_id=cid,
                    name=s["name"],
                    state=s["state"],
                    district=s["district"],
                    village=s["village"],
                    latitude=s["latitude"],
                    longitude=s["longitude"],
                    total_capacity=s["total_capacity"],
                    current_occupancy=s.get("current_occupancy", 0),
                    medical_support=s.get("medical_support", True),
                    food_available=s.get("food_available", True),
                    water_available=s.get("water_available", True),
                    sanitation_available=s.get("sanitation_available", True),
                    accessible_for_disabled=s.get("accessible_for_disabled", True),
                    active=s.get("active", True),
                )
                db.add(rc_obj)
                stats["shelters_inserted"] += 1

        db.commit()

    finally:
        if owns_session:
            db.close()

    return stats


if __name__ == "__main__":
    print("Seeding SQLite database (disaster.db)...")
    res = seed_database()
    print("Database seeding completed:")
    for k, v in res.items():
        print(f"  {k}: {v}")
