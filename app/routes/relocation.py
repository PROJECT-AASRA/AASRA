"""
Relocation & Shelter API Router
Endpoints for managing emergency shelters and computing personalized shelter recommendations.

DISCLAIMER: All demo shelters, capacities, and suitability rankings are purely fictional
assumptions used for testing and prototype demonstrations.
"""

from typing import Dict, Any, List, Optional, Literal, Tuple
from uuid import uuid4
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import RelocationCenterModel, HouseholdModel
from app.services.relocation import (
    calculate_available_capacity,
    recommend_shelters
)
from app.services.data_loader import load_uttarakhand_shelters
from app.routes.households import HOUSEHOLDS_DB

router = APIRouter()

AllowedState = Literal["Assam", "Uttarakhand", "Odisha"]


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class RelocationCenterCreate(BaseModel):
    center_id: Optional[str] = Field(None, description="Optional custom unique center ID. Auto-generated if omitted.")
    name: str = Field(..., min_length=2, description="Shelter facility name")
    state: AllowedState = Field(..., description="Must be Assam, Uttarakhand, or Odisha")
    district: str = Field(..., min_length=1, description="District name")
    village: str = Field(..., min_length=1, description="Village or neighborhood name")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180")
    total_capacity: int = Field(..., gt=0, description="Total intake capacity (> 0)")
    current_occupancy: int = Field(0, ge=0, description="Current occupants (>= 0)")
    medical_support: bool = Field(True, description="Presence of medical personnel or first aid supplies")
    food_available: bool = Field(True, description="On-site emergency food rations")
    water_available: bool = Field(True, description="Potable water infrastructure")
    sanitation_available: bool = Field(True, description="Operational sanitation facilities")
    accessible_for_disabled: bool = Field(True, description="Wheelchair / physical disability accessibility")
    active: bool = Field(True, description="Whether facility is operational and accepting evacuees")

    @model_validator(mode="after")
    def validate_capacity_bounds(self):
        if self.current_occupancy > self.total_capacity:
            raise ValueError(
                f"current_occupancy ({self.current_occupancy}) cannot exceed total_capacity ({self.total_capacity})."
            )
        return self


class RelocationCenterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2)
    state: Optional[AllowedState] = None
    district: Optional[str] = None
    village: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    total_capacity: Optional[int] = Field(None, gt=0)
    current_occupancy: Optional[int] = Field(None, ge=0)
    medical_support: Optional[bool] = None
    food_available: Optional[bool] = None
    water_available: Optional[bool] = None
    sanitation_available: Optional[bool] = None
    accessible_for_disabled: Optional[bool] = None
    active: Optional[bool] = None


class RelocationCenterResponse(BaseModel):
    center_id: str
    name: str
    state: str
    district: str
    village: str
    latitude: float
    longitude: float
    total_capacity: int
    current_occupancy: int
    available_capacity: int
    medical_support: bool
    food_available: bool
    water_available: bool
    sanitation_available: bool
    accessible_for_disabled: bool
    active: bool


class CenterCapacityResponse(BaseModel):
    center_id: str
    name: str
    total_capacity: int
    current_occupancy: int
    available_capacity: int
    active: bool


class RecommendedCenterItem(BaseModel):
    center_id: str
    name: str
    distance_km: float
    available_capacity: int
    medical_support: bool
    food_available: bool
    water_available: bool
    sanitation_available: bool
    accessible_for_disabled: bool
    suitability: str


class RecommendationResponse(BaseModel):
    household_id: str
    vulnerability_level: str
    priority_level: str
    recommended_centers: List[RecommendedCenterItem]


# ============================================================================
# IN-MEMORY SHELTERS DATABASE (Demo / Testing Data)
# ============================================================================

SHELTERS_DB: Dict[str, Dict[str, Any]] = {}


def _format_shelter_record(data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to compute available_capacity and format record."""
    record = dict(data)
    record["available_capacity"] = calculate_available_capacity(
        record["total_capacity"],
        record["current_occupancy"]
    )
    return record


_DEMO_SHELTERS = [
    # --- Assam (4 shelters: varying distance, full capacity, inactive, and fully equipped) ---
    {
        "center_id": "SHELTER-AS-001", "name": "Bilasipara Model Relief Camp",
        "state": "Assam", "district": "Dhubri", "village": "Bilasipara Town",
        "latitude": 26.25, "longitude": 90.02, "total_capacity": 250, "current_occupancy": 80,
        "medical_support": True, "food_available": True, "water_available": True,
        "sanitation_available": True, "accessible_for_disabled": True, "active": True
    },
    {
        "center_id": "SHELTER-AS-002", "name": "Majuli Island High-Ground Flood Shelter",
        "state": "Assam", "district": "Majuli", "village": "Garamur",
        "latitude": 26.98, "longitude": 94.22, "total_capacity": 150, "current_occupancy": 150,
        "medical_support": True, "food_available": True, "water_available": True,
        "sanitation_available": True, "accessible_for_disabled": True, "active": True
        # NOTE: At full capacity (available_capacity = 0)
    },
    {
        "center_id": "SHELTER-AS-003", "name": "Kamrup Community Cyclone Center",
        "state": "Assam", "district": "Kamrup", "village": "Palasbari",
        "latitude": 26.12, "longitude": 91.50, "total_capacity": 200, "current_occupancy": 35,
        "medical_support": False, "food_available": True, "water_available": True,
        "sanitation_available": True, "accessible_for_disabled": False, "active": True
        # NOTE: Missing medical and disabled accessibility
    },
    {
        "center_id": "SHELTER-AS-004", "name": "Cachar Standby Emergency Shelter",
        "state": "Assam", "district": "Cachar", "village": "Kanakpur",
        "latitude": 24.81, "longitude": 92.79, "total_capacity": 120, "current_occupancy": 0,
        "medical_support": True, "food_available": True, "water_available": True,
        "sanitation_available": True, "accessible_for_disabled": True, "active": False
        # NOTE: Inactive facility
    },

    # --- Uttarakhand (3 shelters: mountain relief, valley center, non-accessible) ---
    {
        "center_id": "SHELTER-UK-001", "name": "Joshimath Higher Secondary Relief Station",
        "state": "Uttarakhand", "district": "Chamoli", "village": "Upper Bazar",
        "latitude": 30.56, "longitude": 79.57, "total_capacity": 180, "current_occupancy": 50,
        "medical_support": True, "food_available": True, "water_available": True,
        "sanitation_available": True, "accessible_for_disabled": True, "active": True
    },
    {
        "center_id": "SHELTER-UK-002", "name": "Mandakini Valley Transit Shelter",
        "state": "Uttarakhand", "district": "Rudraprayag", "village": "Agastyamuni",
        "latitude": 30.39, "longitude": 78.98, "total_capacity": 140, "current_occupancy": 40,
        "medical_support": True, "food_available": True, "water_available": True,
        "sanitation_available": True, "accessible_for_disabled": False, "active": True
        # NOTE: Not accessible for disabled
    },
    {
        "center_id": "SHELTER-UK-003", "name": "Doon Valley Regional Evacuation Hub",
        "state": "Uttarakhand", "district": "Dehradun", "village": "Rishikesh Bypass",
        "latitude": 30.12, "longitude": 78.29, "total_capacity": 350, "current_occupancy": 60,
        "medical_support": False, "food_available": True, "water_available": True,
        "sanitation_available": True, "accessible_for_disabled": True, "active": True
    },

    # --- Odisha (3 shelters: coastal cyclone, lagoon haven, full capacity) ---
    {
        "center_id": "SHELTER-OD-001", "name": "Puri Coastal Multi-Purpose Cyclone Center",
        "state": "Odisha", "district": "Puri", "village": "Konark Marine",
        "latitude": 19.90, "longitude": 86.12, "total_capacity": 400, "current_occupancy": 120,
        "medical_support": True, "food_available": True, "water_available": True,
        "sanitation_available": True, "accessible_for_disabled": True, "active": True
    },
    {
        "center_id": "SHELTER-OD-002", "name": "Rajnagar Tidal Surge Shelter",
        "state": "Odisha", "district": "Kendrapara", "village": "Gupti",
        "latitude": 20.65, "longitude": 86.82, "total_capacity": 250, "current_occupancy": 75,
        "medical_support": True, "food_available": True, "water_available": True,
        "sanitation_available": True, "accessible_for_disabled": True, "active": True
    },
    {
        "center_id": "SHELTER-OD-003", "name": "Chandipur Coastal Emergency Hall",
        "state": "Odisha", "district": "Balasore", "village": "Balaramgadi",
        "latitude": 21.48, "longitude": 87.03, "total_capacity": 100, "current_occupancy": 100,
        "medical_support": False, "food_available": True, "water_available": False,
        "sanitation_available": True, "accessible_for_disabled": False, "active": True
        # NOTE: At full capacity (available_capacity = 0)
    }
]

# Initialize in-memory store with demo shelters (Assam, Odisha) and real Uttarakhand shelters from GeoJSONs
for s in _DEMO_SHELTERS:
    SHELTERS_DB[s["center_id"]] = _format_shelter_record(s)

_REAL_SHELTERS = load_uttarakhand_shelters()
if _REAL_SHELTERS:
    for cid, s in _REAL_SHELTERS.items():
        SHELTERS_DB[cid] = _format_shelter_record(s)


def sync_shelters_from_db():
    """Synchronizes in-memory SHELTERS_DB with records from SQLite database."""
    try:
        db = SessionLocal()
        try:
            records = db.query(RelocationCenterModel).all()
            for r in records:
                SHELTERS_DB[r.center_id] = r.to_dict()
        finally:
            db.close()
    except Exception as e:
        print(f"Notice: initial shelter sync from database: {e}")


# Run initial sync if database exists and has records
sync_shelters_from_db()


def _resolve_session(db: Any) -> Tuple[Session, bool]:
    """Helper to resolve Session when function is called directly vs via FastAPI dependency injection."""
    if hasattr(db, "query"):
        return db, False
    return SessionLocal(), True


# ============================================================================
# API ROUTE HANDLERS (SQLAlchemy + SQLite Database)
# ============================================================================

@router.post("/", response_model=RelocationCenterResponse, status_code=status.HTTP_201_CREATED)
def create_relocation_center(payload: RelocationCenterCreate, db: Session = Depends(get_db)):
    """Register a new relocation center and persist to SQLite."""
    db, owns_db = _resolve_session(db)
    try:
        cid = payload.center_id
        if not cid:
            state_code = payload.state[:2].upper()
            cid = f"SHELTER-{state_code}-{uuid4().hex[:6].upper()}"

        existing = db.query(RelocationCenterModel).filter(RelocationCenterModel.center_id == cid).first()
        if existing or cid in SHELTERS_DB:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Relocation center with ID '{cid}' already exists."
            )

        data = payload.model_dump()
        data["center_id"] = cid

        record = _format_shelter_record(data)

        # Persist to SQLite
        rc_model = RelocationCenterModel(
            center_id=cid,
            name=record["name"],
            state=record["state"],
            district=record["district"],
            village=record["village"],
            latitude=record["latitude"],
            longitude=record["longitude"],
            total_capacity=record["total_capacity"],
            current_occupancy=record.get("current_occupancy", 0),
            medical_support=record.get("medical_support", True),
            food_available=record.get("food_available", True),
            water_available=record.get("water_available", True),
            sanitation_available=record.get("sanitation_available", True),
            accessible_for_disabled=record.get("accessible_for_disabled", True),
            active=record.get("active", True),
        )
        db.add(rc_model)
        db.commit()
        db.refresh(rc_model)

        SHELTERS_DB[cid] = record
        return record
    finally:
        if owns_db:
            db.close()


@router.get("/", response_model=List[RelocationCenterResponse])
def list_relocation_centers(
    district: Optional[str] = None,
    accessible_only: Optional[bool] = False,
    medical_only: Optional[bool] = False,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List registered relocation shelters from SQLite with optional filters."""
    db, owns_db = _resolve_session(db)
    try:
        query = db.query(RelocationCenterModel)
        if district:
            query = query.filter(RelocationCenterModel.district.ilike(f"%{district.strip()}%"))
        if accessible_only:
            query = query.filter(RelocationCenterModel.accessible_for_disabled == True)
        if medical_only:
            query = query.filter(RelocationCenterModel.medical_support == True)

        db_results = query.limit(limit).all()
        if db_results:
            return [s.to_dict() for s in db_results]

        # Fallback to in-memory store
        results = list(SHELTERS_DB.values())
        if district:
            results = [s for s in results if s.get("district", "").lower() == district.lower()]
        if accessible_only:
            results = [s for s in results if s.get("accessible_for_disabled") is True]
        if medical_only:
            results = [s for s in results if s.get("medical_support") is True]
        return results[:limit]
    finally:
        if owns_db:
            db.close()


@router.get("/recommend/{household_id}", response_model=RecommendationResponse)
def recommend_shelters_for_household(household_id: str, db: Session = Depends(get_db)):
    """
    Evaluates operational shelters and returns suitability-ranked recommendations
    tailored to the household's vulnerability level, priority tier, and disability needs.
    """
    db, owns_db = _resolve_session(db)
    try:
        # Check SQLite first, then in-memory
        hh_row = db.query(HouseholdModel).filter(HouseholdModel.household_id == household_id).first()
        household = hh_row.to_dict() if hh_row else HOUSEHOLDS_DB.get(household_id)

        if not household:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Household with ID '{household_id}' not found in registry."
            )

        # Fetch shelters from SQLite
        shelter_rows = db.query(RelocationCenterModel).filter(RelocationCenterModel.active == True).all()
        if shelter_rows:
            shelter_list = [s.to_dict() for s in shelter_rows]
        else:
            shelter_list = list(SHELTERS_DB.values())

        recommended = recommend_shelters(household, shelter_list)

        return {
            "household_id": household["household_id"],
            "vulnerability_level": household.get("vulnerability_level", "LOW"),
            "priority_level": household.get("priority_level", "LOW"),
            "recommended_centers": recommended
        }
    finally:
        if owns_db:
            db.close()


@router.get("/{center_id}/capacity", response_model=CenterCapacityResponse)
def get_center_capacity(center_id: str, db: Session = Depends(get_db)):
    """Get current and available capacity status for a shelter from SQLite."""
    db, owns_db = _resolve_session(db)
    try:
        rc = db.query(RelocationCenterModel).filter(RelocationCenterModel.center_id == center_id).first()
        if rc:
            d = rc.to_dict()
            return {
                "center_id": d["center_id"],
                "name": d["name"],
                "total_capacity": d["total_capacity"],
                "current_occupancy": d["current_occupancy"],
                "available_capacity": d["available_capacity"],
                "active": d["active"]
            }
        if center_id in SHELTERS_DB:
            s = SHELTERS_DB[center_id]
            return {
                "center_id": s["center_id"],
                "name": s["name"],
                "total_capacity": s["total_capacity"],
                "current_occupancy": s["current_occupancy"],
                "available_capacity": s["available_capacity"],
                "active": s["active"]
            }
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Relocation center with ID '{center_id}' not found."
        )
    finally:
        if owns_db:
            db.close()


@router.get("/{center_id}", response_model=RelocationCenterResponse)
def get_relocation_center(center_id: str, db: Session = Depends(get_db)):
    """Retrieve full details of a specific relocation center from SQLite."""
    db, owns_db = _resolve_session(db)
    try:
        rc = db.query(RelocationCenterModel).filter(RelocationCenterModel.center_id == center_id).first()
        if rc:
            return rc.to_dict()
        if center_id in SHELTERS_DB:
            return SHELTERS_DB[center_id]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Relocation center with ID '{center_id}' not found."
        )
    finally:
        if owns_db:
            db.close()


@router.put("/{center_id}", response_model=RelocationCenterResponse)
def update_relocation_center(center_id: str, payload: RelocationCenterUpdate, db: Session = Depends(get_db)):
    """Update relocation center details in SQLite and recompute available capacity."""
    db, owns_db = _resolve_session(db)
    try:
        rc = db.query(RelocationCenterModel).filter(RelocationCenterModel.center_id == center_id).first()
        if not rc and center_id not in SHELTERS_DB:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Relocation center with ID '{center_id}' not found."
            )

        current = rc.to_dict() if rc else dict(SHELTERS_DB[center_id])
        update_data = payload.model_dump(exclude_unset=True)
        current.update(update_data)

        tot = current.get("total_capacity", 1)
        occ = current.get("current_occupancy", 0)
        if occ > tot:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid occupancy update: current_occupancy ({occ}) cannot exceed total_capacity ({tot})."
            )

        updated_record = _format_shelter_record(current)

        if rc:
            for k, v in updated_record.items():
                if hasattr(rc, k):
                    setattr(rc, k, v)
            db.commit()
            db.refresh(rc)

        SHELTERS_DB[center_id] = updated_record
        return updated_record
    finally:
        if owns_db:
            db.close()


@router.delete("/{center_id}")
def delete_relocation_center(center_id: str, db: Session = Depends(get_db)):
    """Delete a relocation center from SQLite and cache."""
    db, owns_db = _resolve_session(db)
    try:
        rc = db.query(RelocationCenterModel).filter(RelocationCenterModel.center_id == center_id).first()
        if not rc and center_id not in SHELTERS_DB:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Relocation center with ID '{center_id}' not found."
            )
        if rc:
            db.delete(rc)
            db.commit()
        if center_id in SHELTERS_DB:
            SHELTERS_DB.pop(center_id)
        return {
            "message": f"Relocation center '{center_id}' deleted successfully.",
            "center_id": center_id
        }
    finally:
        if owns_db:
            db.close()

