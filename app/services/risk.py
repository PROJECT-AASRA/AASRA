from typing import Dict, Any, Optional

def calculate_risk(hazards: Dict[str, Any], state: str = "Uttarakhand") -> float:
    """
    Computes compound multi-hazard risk score (0 - 100).
    Uses state-specific regional hazard weight calibrations:
    - Uttarakhand: Flash Flood (30%), Landslide (25%), River (25%), Heavy Rainfall (20%)
    - Assam: Flood (30%), River Flooding (30%), Heavy Rainfall (25%), Landslide (15%)
    - Odisha: Cyclone (35%), Coastal Surge (25%), Monsoon Flood (25%), Heavy Rainfall (15%)
    """
    flood = float(hazards.get("flood", 0))
    landslide = float(hazards.get("landslide", 0))
    rainfall = float(hazards.get("rainfall", 0))
    river = float(hazards.get("river", 0))
    cyclone = float(hazards.get("cyclone", 0))
    coastal = float(hazards.get("coastal", 0))

    st = state.strip().lower()
    if st == "uttarakhand":
        risk = (flood * 0.30) + (landslide * 0.25) + (river * 0.25) + (rainfall * 0.20)
    elif st == "assam":
        risk = (flood * 0.30) + (river * 0.30) + (rainfall * 0.25) + (landslide * 0.15)
    elif st == "odisha":
        risk = (cyclone * 0.35) + (coastal * 0.25) + (flood * 0.25) + (rainfall * 0.15)
    else:
        # General multi-hazard fallback
        risk = (
            flood * 0.25 +
            landslide * 0.20 +
            rainfall * 0.20 +
            river * 0.15 +
            cyclone * 0.10 +
            coastal * 0.10
        )

    return round(min(1.0, max(0.0, risk)) * 100, 2)



def get_risk_level(score: float) -> str:
    """
    Maps numerical risk score (0 - 100) to standard disaster alert tiers:
    - >= 70 -> RED (Critical / Severe Alert)
    - >= 40 -> ORANGE (High Alert)
    - >= 20 -> YELLOW (Moderate Warning)
    - <  20 -> GREEN (Low / Advisory)
    """
    if score >= 70.0:
        return "RED"
    elif score >= 40.0:
        return "ORANGE"
    elif score >= 20.0:
        return "YELLOW"
    else:
        return "GREEN"


def evaluate_household_risk(
    hazards: Dict[str, Any],
    household_id: Optional[str] = None,
    state: str = "Uttarakhand"
) -> Dict[str, Any]:
    """
    Produces a complete risk assessment block with score, alert tier, and hazard inputs.
    """
    score = calculate_risk(hazards, state=state)
    level = get_risk_level(score)
    return {
        "household_id": household_id or "UNKNOWN",
        "state": state,
        "risk_score": score,
        "risk_level": level,
        "hazard_inputs": hazards
    }

