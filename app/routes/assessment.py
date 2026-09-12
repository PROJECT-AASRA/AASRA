"""
Project AASRA - Final Disaster Assessment & Intelligent Relocation Decision Engine
FastAPI Router exposing comprehensive multi-hazard evaluation, compound risk,
demographic vulnerability, actionable relocation decisions, and shelter allocation.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Path, Query, status, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.assessment import get_assessment_engine


router = APIRouter()


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/household/{household_id}",
    summary="Get Complete Disaster Assessment & Relocation Plan for a Household",
    description=(
        "Executes the full Project AASRA decision pipeline for a registered household:\n"
        "1. Demographics retrieval\n"
        "2. Real multi-hazard spatial exposure (Flood, Landslide, River, Rain, Elevation, Slope)\n"
        "3. Compound risk score & level (RED/ORANGE/YELLOW/GREEN)\n"
        "4. Demographic vulnerability score & emergency priority\n"
        "5. Actionable relocation decision (IMMEDIATE, HIGH PRIORITY, PREPARE, MONITOR, SAFE)\n"
        "6. Intelligent shelter suitability ranking & capacity matching"
    ),
    response_description="Complete household disaster assessment and shelter recommendation"
)
def get_household_assessment(
    household_id: str = Path(..., description="Unique Household ID (e.g., 'HH-UK-001')"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    engine = get_assessment_engine()
    try:
        assessment = engine.get_household_assessment(household_id, db=db)
        return assessment
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Household '{household_id}' not found in registry."
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing assessment for household '{household_id}': {str(exc)}"
        )


@router.get(
    "/high-risk",
    summary="List High-Risk Households Requiring Relocation",
    description=(
        "Scans all registered households, identifies those requiring relocation "
        "(IMMEDIATE RELOCATION, HIGH PRIORITY RELOCATION, PREPARE FOR RELOCATION), "
        "and sorts them in priority queue order by urgency tier (Tier 1 first) "
        "and compound risk score descending."
    ),
    response_description="Prioritized list of households requiring relocation"
)
def get_high_risk_households(
    state: Optional[str] = Query(None, description="Optional filter by state (e.g. 'Uttarakhand', 'Assam', 'Odisha')"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of records to return")
) -> Dict[str, Any]:
    engine = get_assessment_engine()
    try:
        high_risk = engine.get_high_risk_households(state=state, limit=limit)
        return {
            "status": "success",
            "state_filter": state,
            "total_records_returned": len(high_risk),
            "households": high_risk
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error querying high-risk households: {str(exc)}"
        )


@router.get(
    "/state/{state}",
    summary="Get Strategic Disaster Assessment & Relocation Overview for a State",
    description=(
        "Aggregates state-level disaster metrics across all indexed households:\n"
        "- Total households assessed & affected population\n"
        "- Risk tier distribution (RED, ORANGE, YELLOW, GREEN)\n"
        "- Relocation action distribution (Immediate, High Priority, Prepare, Monitor, Safe)\n"
        "- Evacuation headcount requirement vs available shelter capacity in the state\n"
        "- District-by-district vulnerability ranking"
    ),
    response_description="State-level strategic disaster and evacuation profile"
)
def get_state_assessment(
    state: str = Path(..., description="State name (e.g., 'Uttarakhand', 'Assam', 'Odisha')")
) -> Dict[str, Any]:
    engine = get_assessment_engine()
    try:
        state_summary = engine.get_state_assessment(state)
        return state_summary
    except KeyError as ke:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ke)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error compiling state assessment for '{state}': {str(exc)}"
        )


@router.get(
    "/district/{district}",
    summary="Get Operational Disaster Assessment & Relocation Plan for a District",
    description=(
        "Returns a detailed tactical evacuation report for a specific district:\n"
        "- Total households and population at risk\n"
        "- Average composite risk score\n"
        "- List of households requiring relocation with assigned candidate shelters\n"
        "- Risk and decision breakdown"
    ),
    response_description="District operational disaster and relocation report"
)
def get_district_assessment(
    district: str = Path(..., description="District name (e.g., 'Chamoli', 'Rudraprayag', 'Pithoragarh')"),
    state: Optional[str] = Query(None, description="Optional state disambiguation filter")
) -> Dict[str, Any]:
    engine = get_assessment_engine()
    try:
        district_summary = engine.get_district_assessment(district, state=state)
        return district_summary
    except KeyError as ke:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ke)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error compiling district assessment for '{district}': {str(exc)}"
        )
