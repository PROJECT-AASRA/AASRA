"""
Household API Router
Provides endpoints for managing household demographics, vulnerability scoring, and emergency priorities.
"""

from typing import Dict, Any, List, Optional, Literal, Union, Tuple
from uuid import uuid4
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import HouseholdModel
from app.services.vulnerability import (
    calculate_vulnerability_score,
    get_vulnerability_level,
    get_priority_level
)
from app.services.data_loader import load_uttarakhand_households
from app.services.geospatial import get_geospatial_engine
from app.services.hazard_processor import get_hazard_processor
from app.services.risk import calculate_risk, get_risk_level


router = APIRouter()

# Supported states
AllowedState = Literal["Assam", "Uttarakhand", "Odisha"]


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class HouseholdCreate(BaseModel):
    household_id: Optional[str] = Field(None, description="Optional custom unique ID. Auto-generated if omitted.")
    state: AllowedState = Field(..., description="Must be Assam, Uttarakhand, or Odisha")
    district: str = Field(..., min_length=1, description="District name")
    village: str = Field(..., min_length=1, description="Village name")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate between -180 and 180")
    population: int = Field(..., ge=1, description="Total household population (>= 1)")
    children: int = Field(0, ge=0, description="Number of children (>= 0)")
    elderly: int = Field(0, ge=0, description="Number of elderly individuals (>= 0)")
    disabled: int = Field(0, ge=0, description="Number of disabled individuals (>= 0)")
    low_income: bool = Field(False, description="Low-income economic status flag")
    hazard_exposure: Optional[float] = Field(None, ge=0.0, le=1.0, description="Normalized hazard exposure (0.0 to 1.0). If omitted, automatically computed from geospatial datasets!")
    previous_disaster_exposure: Union[bool, float] = Field(False, description="Historical disaster exposure flag or index")

    @model_validator(mode="after")
    def validate_demographics(self):
        if self.children + self.elderly + self.disabled > self.population:
            raise ValueError(
                f"The sum of children ({self.children}), elderly ({self.elderly}), "
                f"and disabled ({self.disabled}) cannot exceed total population ({self.population})."
            )
        return self


class HouseholdUpdate(BaseModel):
    state: Optional[AllowedState] = None
    district: Optional[str] = None
    village: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    population: Optional[int] = Field(None, ge=1)
    children: Optional[int] = Field(None, ge=0)
    elderly: Optional[int] = Field(None, ge=0)
    disabled: Optional[int] = Field(None, ge=0)
    low_income: Optional[bool] = None
    hazard_exposure: Optional[float] = Field(None, ge=0.0, le=1.0)
    previous_disaster_exposure: Optional[Union[bool, float]] = None


class HouseholdResponse(BaseModel):
    household_id: str
    state: str
    district: str
    village: str
    latitude: float
    longitude: float
    population: int
    children: int
    elderly: int
    disabled: int
    low_income: bool
    hazard_exposure: float
    previous_disaster_exposure: Union[bool, float]
    vulnerability_score: float
    vulnerability_level: str
    priority_level: str
    in_historical_flood_zone: Optional[bool] = None
    distance_to_nearest_river_km: Optional[float] = None
    distance_to_nearest_hospital_km: Optional[float] = None
    nearest_hospital: Optional[str] = None
    flood_exposure: Optional[float] = None
    river_exposure: Optional[float] = None
    landslide_exposure: Optional[float] = None
    rainfall_exposure: Optional[float] = None
    hazard_tier: Optional[str] = None
    elevation_meters: Optional[float] = None
    slope_degrees: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None


class VulnerabilitySummary(BaseModel):
    household_id: str
    vulnerability_score: float
    vulnerability_level: str


class PrioritySummary(BaseModel):
    household_id: str
    priority_level: str
    vulnerability_level: str
    hazard_exposure: float


# ============================================================================
# IN-MEMORY DATABASE & PRE-POPULATED TEST DATA (15 Households)
# ============================================================================

HOUSEHOLDS_DB: Dict[str, Dict[str, Any]] = {}


def _compute_and_format(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper to compute geospatial hazard exposure, vulnerability metrics,
    and format a household record.
    Workflow: Coordinates -> Real Hazard Processor -> Vulnerability Scoring -> Risk Engine -> Emergency Priority.
    """
    record = dict(data)
    lat = record.get("latitude")
    lon = record.get("longitude")
    state = record.get("state", "Uttarakhand")
    district = record.get("district", "Chamoli")

    # Real Geospatial & Hazard Evaluation
    if lat is not None and lon is not None:
        try:
            # 1. Physical Infrastructure Proximity (Hospital, River, Past Flood Zone)
            geo_engine = get_geospatial_engine()
            geo_profile = geo_engine.evaluate_geospatial_hazard(lat, lon, district)
            record["in_historical_flood_zone"] = geo_profile["in_historical_flood_zone"]
            record["distance_to_nearest_river_km"] = geo_profile["distance_to_nearest_river_km"]
            record["distance_to_nearest_hospital_km"] = geo_profile["distance_to_nearest_hospital_km"]
            record["nearest_hospital"] = geo_profile["nearest_hospital_name"]

            # 2. Real Hazard Processor (Flood, River, Landslide, Rainfall, Elevation, Slope)
            hp = get_hazard_processor()
            hazard_profile = hp.calculate_multi_hazard_exposure(
                lat=lat,
                lon=lon,
                district=district,
                household_id=record.get("household_id")
            )
            record["flood_exposure"] = hazard_profile["hazards"]["flood"]
            record["river_exposure"] = hazard_profile["hazards"]["river"]
            record["landslide_exposure"] = hazard_profile["hazards"]["landslide"]
            record["rainfall_exposure"] = hazard_profile["hazards"]["rainfall"]
            record["hazard_tier"] = hazard_profile["hazard_tier"]
            record["elevation_meters"] = hazard_profile.get("elevation_meters")
            record["slope_degrees"] = hazard_profile.get("slope_degrees")

            # Calibrate compound risk score & level
            r_score = calculate_risk(hazard_profile["hazards"], state=state)
            record["risk_score"] = r_score
            record["risk_level"] = get_risk_level(r_score)

            # If hazard_exposure is omitted or for Uttarakhand households, use real composite score
            if record.get("hazard_exposure") is None or state.lower() == "uttarakhand":

                record["hazard_exposure"] = hazard_profile["composite_hazard_exposure"]

        except Exception as e:
            print(f"Warning in hazard/geospatial calculation for household: {e}")

    # Compute vulnerability score and emergency priority
    score = calculate_vulnerability_score(record)
    v_level = get_vulnerability_level(score)
    p_level = get_priority_level(v_level, record.get("hazard_exposure", 0.5))

    record["vulnerability_score"] = score
    record["vulnerability_level"] = v_level
    record["priority_level"] = p_level
    return record



# 15 Fictional test households across Assam, Uttarakhand, and Odisha
_INITIAL_HOUSEHOLDS = [
    # --- Assam (5 households) ---
    {
        "household_id": "HH-AS-001", "state": "Assam", "district": "Dhubri", "village": "Bilasipara",
        "latitude": 26.23, "longitude": 89.98, "population": 6, "children": 2, "elderly": 1,
        "disabled": 1, "low_income": True, "hazard_exposure": 0.90, "previous_disaster_exposure": True
    },
    {
        "household_id": "HH-AS-002", "state": "Assam", "district": "Majuli", "village": "Kamalabari",
        "latitude": 26.96, "longitude": 94.17, "population": 5, "children": 2, "elderly": 1,
        "disabled": 0, "low_income": True, "hazard_exposure": 0.85, "previous_disaster_exposure": True
    },
    {
        "household_id": "HH-AS-003", "state": "Assam", "district": "Barpeta", "village": "Sarthebari",
        "latitude": 26.37, "longitude": 91.02, "population": 4, "children": 1, "elderly": 1,
        "disabled": 0, "low_income": True, "hazard_exposure": 0.60, "previous_disaster_exposure": False
    },
    {
        "household_id": "HH-AS-004", "state": "Assam", "district": "Kamrup", "village": "Mirza",
        "latitude": 26.08, "longitude": 91.52, "population": 3, "children": 0, "elderly": 0,
        "disabled": 0, "low_income": False, "hazard_exposure": 0.35, "previous_disaster_exposure": False
    },
    {
        "household_id": "HH-AS-005", "state": "Assam", "district": "Cachar", "village": "Sonai",
        "latitude": 24.73, "longitude": 92.89, "population": 2, "children": 0, "elderly": 0,
        "disabled": 0, "low_income": False, "hazard_exposure": 0.20, "previous_disaster_exposure": False
    },

    # --- Uttarakhand (5 households) ---
    {
        "household_id": "HH-UK-001", "state": "Uttarakhand", "district": "Chamoli", "village": "Joshimath",
        "latitude": 30.55, "longitude": 79.56, "population": 7, "children": 2, "elderly": 2,
        "disabled": 1, "low_income": True, "hazard_exposure": 0.95, "previous_disaster_exposure": True
    },
    {
        "household_id": "HH-UK-002", "state": "Uttarakhand", "district": "Rudraprayag", "village": "Guptkashi",
        "latitude": 30.52, "longitude": 79.08, "population": 6, "children": 2, "elderly": 1,
        "disabled": 1, "low_income": True, "hazard_exposure": 0.65, "previous_disaster_exposure": True
    },
    {
        "household_id": "HH-UK-003", "state": "Uttarakhand", "district": "Uttarkashi", "village": "Barkot",
        "latitude": 30.81, "longitude": 78.20, "population": 5, "children": 1, "elderly": 1,
        "disabled": 0, "low_income": True, "hazard_exposure": 0.50, "previous_disaster_exposure": True
    },
    {
        "household_id": "HH-UK-004", "state": "Uttarakhand", "district": "Pithoragarh", "village": "Dharchula",
        "latitude": 29.85, "longitude": 80.53, "population": 4, "children": 1, "elderly": 0,
        "disabled": 0, "low_income": False, "hazard_exposure": 0.45, "previous_disaster_exposure": False
    },
    {
        "household_id": "HH-UK-005", "state": "Uttarakhand", "district": "Dehradun", "village": "Rishikesh",
        "latitude": 30.08, "longitude": 78.26, "population": 3, "children": 0, "elderly": 0,
        "disabled": 0, "low_income": False, "hazard_exposure": 0.15, "previous_disaster_exposure": False
    },

    # --- Odisha (5 households) ---
    {
        "household_id": "HH-OD-001", "state": "Odisha", "district": "Puri", "village": "Astaranga",
        "latitude": 19.98, "longitude": 86.27, "population": 6, "children": 2, "elderly": 1,
        "disabled": 1, "low_income": True, "hazard_exposure": 0.92, "previous_disaster_exposure": True
    },
    {
        "household_id": "HH-OD-002", "state": "Odisha", "district": "Kendrapara", "village": "Rajnagar",
        "latitude": 20.58, "longitude": 86.74, "population": 7, "children": 2, "elderly": 2,
        "disabled": 1, "low_income": True, "hazard_exposure": 0.75, "previous_disaster_exposure": True
    },
    {
        "household_id": "HH-OD-003", "state": "Odisha", "district": "Balasore", "village": "Chandipur",
        "latitude": 21.46, "longitude": 87.01, "population": 4, "children": 1, "elderly": 1,
        "disabled": 0, "low_income": True, "hazard_exposure": 0.65, "previous_disaster_exposure": False
    },
    {
        "household_id": "HH-OD-004", "state": "Odisha", "district": "Ganjam", "village": "Gopalpur",
        "latitude": 19.26, "longitude": 84.90, "population": 5, "children": 1, "elderly": 0,
        "disabled": 0, "low_income": True, "hazard_exposure": 0.40, "previous_disaster_exposure": False
    },
    {
        "household_id": "HH-OD-005", "state": "Odisha", "district": "Khordha", "village": "Jatni",
        "latitude": 20.17, "longitude": 85.70, "population": 2, "children": 0, "elderly": 0,
        "disabled": 0, "low_income": False, "hazard_exposure": 0.15, "previous_disaster_exposure": False
    }
]

# Initialize in-memory store with reference households and real Uttarakhand households
for h in _INITIAL_HOUSEHOLDS:
    HOUSEHOLDS_DB[h["household_id"]] = _compute_and_format(h)

_REAL_HOUSEHOLDS = load_uttarakhand_households()
if _REAL_HOUSEHOLDS:
    for hid, h in _REAL_HOUSEHOLDS.items():
        HOUSEHOLDS_DB[hid] = _compute_and_format(h)


def sync_households_from_db():
    """Synchronizes in-memory HOUSEHOLDS_DB with records from SQLite database."""
    try:
        db = SessionLocal()
        try:
            records = db.query(HouseholdModel).all()
            for r in records:
                HOUSEHOLDS_DB[r.household_id] = r.to_dict()
        finally:
            db.close()
    except Exception as e:
        print(f"Notice: initial household sync from database: {e}")


# Run initial sync if database exists and has records
sync_households_from_db()


def _resolve_session(db: Any) -> Tuple[Session, bool]:
    """Helper to resolve Session when function is called directly vs via FastAPI dependency injection."""
    if hasattr(db, "query"):
        return db, False
    return SessionLocal(), True


# ============================================================================
# API ROUTE HANDLERS (SQLAlchemy + SQLite Database)
# ============================================================================

@router.post("/", response_model=HouseholdResponse, status_code=status.HTTP_201_CREATED)
def create_household(payload: HouseholdCreate, db: Session = Depends(get_db)):
    """Register a new household, calculate vulnerability/priority, and persist to SQLite."""
    db, owns_db = _resolve_session(db)
    try:
        hh_id = payload.household_id
        if not hh_id:
            state_code = payload.state[:2].upper()
            hh_id = f"HH-{state_code}-{uuid4().hex[:6].upper()}"

        # Check database and in-memory cache for duplicate
        existing = db.query(HouseholdModel).filter(HouseholdModel.household_id == hh_id).first()
        if existing or hh_id in HOUSEHOLDS_DB:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Household with ID '{hh_id}' already exists."
            )

        data = payload.model_dump()
        data["household_id"] = hh_id

        record = _compute_and_format(data)

        # Persist to SQLite
        hh_model = HouseholdModel(
            household_id=hh_id,
            state=record["state"],
            district=record["district"],
            village=record["village"],
            latitude=record["latitude"],
            longitude=record["longitude"],
            population=record["population"],
            children=record["children"],
            elderly=record["elderly"],
            disabled=record["disabled"],
            low_income=record["low_income"],
            hazard_exposure=record.get("hazard_exposure", 0.0),
            previous_disaster_exposure=1.0 if record.get("previous_disaster_exposure") in (True, 1, 1.0, "true", "True") else 0.0,
            vulnerability_score=record.get("vulnerability_score"),
            vulnerability_level=record.get("vulnerability_level"),
            priority_level=record.get("priority_level"),
            risk_score=record.get("risk_score"),
            risk_level=record.get("risk_level"),
            in_historical_flood_zone=record.get("in_historical_flood_zone"),
            distance_to_nearest_river_km=record.get("distance_to_nearest_river_km"),
            distance_to_nearest_hospital_km=record.get("distance_to_nearest_hospital_km"),
            nearest_hospital=record.get("nearest_hospital"),
            flood_exposure=record.get("flood_exposure"),
            river_exposure=record.get("river_exposure"),
            landslide_exposure=record.get("landslide_exposure"),
            rainfall_exposure=record.get("rainfall_exposure"),
            hazard_tier=record.get("hazard_tier"),
            elevation_meters=record.get("elevation_meters"),
            slope_degrees=record.get("slope_degrees"),
        )
        db.add(hh_model)
        db.commit()
        db.refresh(hh_model)

        HOUSEHOLDS_DB[hh_id] = record
        return record
    finally:
        if owns_db:
            db.close()


@router.get("/", response_model=List[HouseholdResponse])
def list_households(
    district: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List registered households from SQLite with optional district or priority filters."""
    db, owns_db = _resolve_session(db)
    try:
        query = db.query(HouseholdModel)
        if district:
            query = query.filter(HouseholdModel.district.ilike(f"%{district.strip()}%"))
        if priority:
            query = query.filter(HouseholdModel.priority_level.ilike(f"%{priority.strip()}%"))

        db_results = query.limit(limit).all()
        if db_results:
            return [h.to_dict() for h in db_results]

        # Fallback to in-memory store
        results = list(HOUSEHOLDS_DB.values())
        if district:
            results = [h for h in results if h.get("district", "").lower() == district.lower()]
        if priority:
            results = [h for h in results if h.get("priority_level", "").upper() == priority.upper()]
        return results[:limit]
    finally:
        if owns_db:
            db.close()


@router.get("/district/{district}", response_model=List[HouseholdResponse])
def get_households_by_district(district: str, db: Session = Depends(get_db)):
    """Filter households by district from SQLite."""
    db, owns_db = _resolve_session(db)
    try:
        results = db.query(HouseholdModel).filter(HouseholdModel.district.ilike(district.strip())).all()
        if results:
            return [h.to_dict() for h in results]
        return [
            h for h in HOUSEHOLDS_DB.values()
            if h.get("district", "").strip().lower() == district.strip().lower()
        ]
    finally:
        if owns_db:
            db.close()


@router.get("/state/{state}", response_model=List[HouseholdResponse])
def get_households_by_state(state: str, db: Session = Depends(get_db)):
    """Filter households by state from SQLite."""
    db, owns_db = _resolve_session(db)
    try:
        results = db.query(HouseholdModel).filter(HouseholdModel.state.ilike(state.strip())).all()
        if results:
            return [h.to_dict() for h in results]
        return [
            h for h in HOUSEHOLDS_DB.values()
            if h["state"].strip().lower() == state.strip().lower()
        ]
    finally:
        if owns_db:
            db.close()


@router.get("/{household_id}", response_model=HouseholdResponse)
def get_household(household_id: str, db: Session = Depends(get_db)):
    """Retrieve full details of a specific household from SQLite."""
    db, owns_db = _resolve_session(db)
    try:
        hh = db.query(HouseholdModel).filter(HouseholdModel.household_id == household_id).first()
        if hh:
            return hh.to_dict()
        if household_id in HOUSEHOLDS_DB:
            return HOUSEHOLDS_DB[household_id]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household with ID '{household_id}' not found."
        )
    finally:
        if owns_db:
            db.close()


@router.put("/{household_id}", response_model=HouseholdResponse)
def update_household(household_id: str, payload: HouseholdUpdate, db: Session = Depends(get_db)):
    """Update household details in SQLite and recompute vulnerability and priority levels."""
    db, owns_db = _resolve_session(db)
    try:
        hh = db.query(HouseholdModel).filter(HouseholdModel.household_id == household_id).first()
        if not hh and household_id not in HOUSEHOLDS_DB:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Household with ID '{household_id}' not found."
            )

        current = hh.to_dict() if hh else dict(HOUSEHOLDS_DB[household_id])
        update_data = payload.model_dump(exclude_unset=True)
        current.update(update_data)

        # Validate demographic consistency after update
        pop = current.get("population", 1)
        ch = current.get("children", 0)
        eld = current.get("elderly", 0)
        dis = current.get("disabled", 0)
        if ch + eld + dis > pop:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Updated demographics invalid: children ({ch}) + elderly ({eld}) + disabled ({dis}) > population ({pop})."
            )

        updated_record = _compute_and_format(current)

        if hh:
            for k, v in updated_record.items():
                if hasattr(hh, k):
                    if k == "previous_disaster_exposure":
                        v = 1.0 if v in (True, 1, 1.0, "true", "True") else 0.0
                    setattr(hh, k, v)
            db.commit()
            db.refresh(hh)

        HOUSEHOLDS_DB[household_id] = updated_record
        return updated_record
    finally:
        if owns_db:
            db.close()


@router.delete("/{household_id}")
def delete_household(household_id: str, db: Session = Depends(get_db)):
    """Delete a household from SQLite and cache."""
    db, owns_db = _resolve_session(db)
    try:
        hh = db.query(HouseholdModel).filter(HouseholdModel.household_id == household_id).first()
        if not hh and household_id not in HOUSEHOLDS_DB:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Household with ID '{household_id}' not found."
            )
        if hh:
            db.delete(hh)
            db.commit()
        if household_id in HOUSEHOLDS_DB:
            HOUSEHOLDS_DB.pop(household_id)
        return {
            "message": f"Household '{household_id}' deleted successfully.",
            "household_id": household_id
        }
    finally:
        if owns_db:
            db.close()


@router.get("/{household_id}/vulnerability", response_model=VulnerabilitySummary)
def get_household_vulnerability(household_id: str, db: Session = Depends(get_db)):
    """Get vulnerability score and classification level for a household from SQLite."""
    db, owns_db = _resolve_session(db)
    try:
        hh = db.query(HouseholdModel).filter(HouseholdModel.household_id == household_id).first()
        if hh:
            d = hh.to_dict()
            return {
                "household_id": d["household_id"],
                "vulnerability_score": d["vulnerability_score"],
                "vulnerability_level": d["vulnerability_level"]
            }
        if household_id in HOUSEHOLDS_DB:
            h = HOUSEHOLDS_DB[household_id]
            return {
                "household_id": h["household_id"],
                "vulnerability_score": h["vulnerability_score"],
                "vulnerability_level": h["vulnerability_level"]
            }
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household with ID '{household_id}' not found."
        )
    finally:
        if owns_db:
            db.close()


@router.get("/{household_id}/priority", response_model=PrioritySummary)
def get_household_priority(household_id: str, db: Session = Depends(get_db)):
    """Get emergency priority classification and hazard exposure for a household from SQLite."""
    db, owns_db = _resolve_session(db)
    try:
        hh = db.query(HouseholdModel).filter(HouseholdModel.household_id == household_id).first()
        if hh:
            d = hh.to_dict()
            return {
                "household_id": d["household_id"],
                "priority_level": d["priority_level"],
                "vulnerability_level": d["vulnerability_level"],
                "hazard_exposure": d["hazard_exposure"]
            }
        if household_id in HOUSEHOLDS_DB:
            h = HOUSEHOLDS_DB[household_id]
            return {
                "household_id": h["household_id"],
                "priority_level": h["priority_level"],
                "vulnerability_level": h["vulnerability_level"],
                "hazard_exposure": h["hazard_exposure"]
            }
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household with ID '{household_id}' not found."
        )
    finally:
        if owns_db:
            db.close()

