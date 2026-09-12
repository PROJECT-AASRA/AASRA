"""
Relocation & Shelter Management Service (Prototype)
Provides shelter capacity calculations, Haversine distance calculations,
and suitability/priority-based shelter matching for households.

NOTE: All scoring algorithms, weights, and suitability classifications
are initial prototype assumptions designed to be transparent and explainable.
They are not claimed to be scientifically or empirically validated.
"""

import math
from typing import Dict, Any, List, Tuple


def calculate_available_capacity(total_capacity: int, current_occupancy: int) -> int:
    """
    Computes remaining available capacity for a shelter.
    Ensures available capacity is never negative.
    """
    return max(0, int(total_capacity) - int(current_occupancy))


def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates great-circle distance in kilometers between two latitude/longitude
    points using the Haversine formula.
    """
    # Earth radius in kilometers
    R = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return round(R * c, 2)


def evaluate_shelter_suitability(
    household: Dict[str, Any],
    shelter: Dict[str, Any],
    distance_km: float
) -> Tuple[float, str]:
    """
    Computes a transparent suitability score (0-100+) and qualitative tier
    ('HIGH', 'MEDIUM', 'LOW') for a shelter relative to a household's needs.

    Evaluation criteria:
    - Same state alignment
    - Essential baseline amenities (water, food, sanitation)
    - Medical readiness (weighted heavily for IMMEDIATE priority / HIGH vulnerability)
    - Physical accessibility (critical for households with disabled members)
    - Proximity (closer shelters are preferred)
    """
    score = 0.0

    # 1. Geographic Affinity (prefer shelters within the same state)
    same_state = household.get("state", "").strip().lower() == shelter.get("state", "").strip().lower()
    if same_state:
        score += 25.0
    else:
        score -= 15.0

    # 2. Baseline Facilities (Max 45 points)
    if shelter.get("water_available", False):
        score += 15.0
    if shelter.get("food_available", False):
        score += 15.0
    if shelter.get("sanitation_available", False):
        score += 15.0

    # 3. Medical Support & Emergency Priority
    has_medical = shelter.get("medical_support", False)
    priority_level = household.get("priority_level", "LOW")
    vulnerability_level = household.get("vulnerability_level", "LOW")

    if has_medical:
        score += 15.0
        # High-priority households get a substantial bonus for medical-equipped shelters
        if priority_level == "IMMEDIATE":
            score += 20.0
        elif priority_level == "HIGH" or vulnerability_level == "HIGH":
            score += 10.0
    else:
        # Penalize missing medical support for immediate emergency evacuees
        if priority_level == "IMMEDIATE":
            score -= 20.0

    # 4. Disability Accessibility
    disabled_count = int(household.get("disabled", 0))
    is_accessible = shelter.get("accessible_for_disabled", False)

    if is_accessible:
        score += 10.0
        if disabled_count > 0:
            score += 30.0  # Strong boost for matching disabled needs
    else:
        if disabled_count > 0:
            score -= 35.0  # Significant penalty if shelter cannot accommodate disabled members

    # 5. Distance Factor
    # Closer shelters retain higher scores (slight attenuation over long distances)
    if distance_km <= 15.0:
        score += 15.0
    elif distance_km <= 40.0:
        score += 5.0
    elif distance_km > 100.0:
        score -= 20.0

    # Classify qualitative suitability tier
    if score >= 75.0:
        tier = "HIGH"
    elif score >= 40.0:
        tier = "MEDIUM"
    else:
        tier = "LOW"

    return round(score, 2), tier


def recommend_shelters(
    household: Dict[str, Any],
    shelters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Filters, evaluates, and ranks shelters for a given household.

    Hard Filtering Rules:
    - Shelters must be active (active == True).
    - Shelters must have available capacity (available_capacity > 0).

    Ranking Strategy:
    - Primary sort: Suitability score (descending)
    - Secondary sort: Distance in km (ascending)
    """
    hh_lat = float(household.get("latitude", 0.0))
    hh_lon = float(household.get("longitude", 0.0))

    candidates = []

    for s in shelters:
        # Check active status
        if not s.get("active", False):
            continue

        # Calculate remaining capacity
        avail_cap = calculate_available_capacity(
            s.get("total_capacity", 0),
            s.get("current_occupancy", 0)
        )
        if avail_cap <= 0:
            continue

        # Distance calculation
        s_lat = float(s.get("latitude", 0.0))
        s_lon = float(s.get("longitude", 0.0))
        dist_km = calculate_distance_km(hh_lat, hh_lon, s_lat, s_lon)

        # Suitability calculation
        suit_score, suit_tier = evaluate_shelter_suitability(household, s, dist_km)

        candidate = {
            "center_id": s.get("center_id"),
            "name": s.get("name"),
            "distance_km": dist_km,
            "available_capacity": avail_cap,
            "medical_support": s.get("medical_support", False),
            "food_available": s.get("food_available", False),
            "water_available": s.get("water_available", False),
            "sanitation_available": s.get("sanitation_available", False),
            "accessible_for_disabled": s.get("accessible_for_disabled", False),
            "suitability": suit_tier,
            "_suitability_score": suit_score  # Internal sorting key
        }
        candidates.append(candidate)

    # Sort candidates: Higher suitability score first, then shorter distance first
    candidates.sort(key=lambda x: (-x["_suitability_score"], x["distance_km"]))

    # Clean up internal sorting key from public response objects
    for c in candidates:
        del c["_suitability_score"]

    return candidates
