"""
Disaster Assessment & Intelligent Relocation Decision Engine (Project AASRA)
Unified decision intelligence layer combining:
1. Household demographic registry
2. Real multi-hazard spatial exposure (Flood, River, Landslide, Rainfall, Elevation, Slope)
3. Calibrated compound risk scoring (risk.py)
4. Vulnerability & emergency priority profiling (vulnerability.py)
5. Action-oriented relocation decision evaluation
6. Intelligent capacity-aware shelter matching & routing (relocation.py)

DISCLAIMER: Relocation action categories and priority tiers are prototype
decision-support heuristics created for testing and hackathon demonstration.
"""

from typing import Dict, Any, List, Optional
from app.services.hazard_processor import get_hazard_processor
from app.services.risk import calculate_risk, get_risk_level
from app.services.vulnerability import (
    calculate_vulnerability_score,
    get_vulnerability_level,
    get_priority_level
)
from app.services.relocation import recommend_shelters
from app.routes.households import HOUSEHOLDS_DB
from app.routes.relocation import SHELTERS_DB
from app.models import HazardAssessmentModel, HouseholdModel


# ============================================================================
# PROTOTYPE RELOCATION ACTION CLASSIFICATION
# ============================================================================
ACTION_IMMEDIATE = "IMMEDIATE RELOCATION"
ACTION_HIGH = "HIGH PRIORITY RELOCATION"
ACTION_PREPARE = "PREPARE FOR RELOCATION"
ACTION_MONITOR = "MONITOR"
ACTION_SAFE = "NO IMMEDIATE ACTION"


def determine_relocation_decision(
    risk_score: float,
    risk_level: str,
    vulnerability_score: float,
    vulnerability_level: str,
    priority_level: str,
    hazard_exposure: float
) -> Dict[str, Any]:
    """
    Evaluates actionable relocation necessity and operational urgency based on
    compound risk, demographic vulnerability, and emergency priority.

    Decision Rules (Prototype Heuristics):
    - IMMEDIATE RELOCATION:
        Priority is IMMEDIATE, OR Risk is RED with HIGH Vulnerability, OR Risk Score >= 80.
        -> Relocation required immediately.
    - HIGH PRIORITY RELOCATION:
        Priority is HIGH, OR Risk is RED with MEDIUM/HIGH Vulnerability, OR Risk Score >= 65.
        -> Relocation required in primary evacuation wave.
    - PREPARE FOR RELOCATION:
        Priority is MODERATE with Risk Score >= 40 (OR Risk is ORANGE).
        -> Pre-evacuation staging and standby alert.
    - MONITOR:
        Risk is YELLOW (20 <= Risk Score < 40) with non-critical vulnerability.
        -> In-situ monitoring and telemetry tracking.
    - NO IMMEDIATE ACTION:
        Risk is GREEN (< 20) and Priority is LOW.
        -> Standard baseline advisory.
    """
    if priority_level == "IMMEDIATE" or (risk_level == "RED" and vulnerability_level == "HIGH") or risk_score >= 80.0:
        decision = ACTION_IMMEDIATE
        relocation_required = True
        urgency_code = 1
        action_plan = "Initiate immediate evacuation. Route household to nearest medical-ready shelter with wheelchair access if applicable."
    elif priority_level == "HIGH" or (risk_level == "RED") or (risk_score >= 65.0):
        decision = ACTION_HIGH
        relocation_required = True
        urgency_code = 2
        action_plan = "Prioritize relocation in Wave-1 evacuation. Pre-allocate emergency shelter capacity and transit support."
    elif priority_level == "MODERATE" or (risk_level == "ORANGE") or (risk_score >= 40.0):
        decision = ACTION_PREPARE
        relocation_required = True
        urgency_code = 3
        action_plan = "Place on pre-evacuation alert. Verify shelter availability and notify village emergency coordinator."
    elif risk_level == "YELLOW" or (risk_score >= 20.0):
        decision = ACTION_MONITOR
        relocation_required = False
        urgency_code = 4
        action_plan = "No immediate transit required. Continuously monitor local river telemetry, rainfall gauges, and alert bulletins."
    else:
        decision = ACTION_SAFE
        relocation_required = False
        urgency_code = 5
        action_plan = "Standard advisory status. Low environmental and demographic hazard exposure."

    return {
        "decision": decision,
        "relocation_required": relocation_required,
        "urgency_tier": urgency_code,
        "recommended_action": action_plan
    }


# ============================================================================
# END-TO-END ASSESSMENT ENGINE
# ============================================================================
class DisasterAssessmentEngine:
    """
    Main intelligence service connecting Households, Hazard Processing,
    Risk Evaluation, Vulnerability, and Shelter Relocation.
    """
    _instance = None

    def get_household_assessment(self, household_id: str, db: Optional[Any] = None) -> Dict[str, Any]:
        """
        Executes the complete end-to-end intelligence workflow for a registered household:
        1. Household demographics retrieval
        2. Real geospatial multi-hazard exposure calculation
        3. Compound multi-hazard risk engine evaluation
        4. Demographic vulnerability & emergency priority scoring
        5. Actionable relocation decision categorization
        6. Intelligent shelter suitability ranking & capacity matching
        """
        hh = None
        if db is not None:
            try:
                hh_row = db.query(HouseholdModel).filter(HouseholdModel.household_id == household_id).first()
                if hh_row:
                    hh = hh_row.to_dict()
            except Exception:
                pass

        if not hh:
            if household_id not in HOUSEHOLDS_DB:
                raise KeyError(f"Household '{household_id}' not found in registry.")
            hh = HOUSEHOLDS_DB[household_id]

        lat = float(hh.get("latitude", 0.0))
        lon = float(hh.get("longitude", 0.0))
        state = hh.get("state", "Uttarakhand")
        district = hh.get("district", "Chamoli")
        village = hh.get("village", "")

        # --------------------------------------------------------------------
        # 1. Real State-Specific Hazard Exposure
        # --------------------------------------------------------------------
        if state == "Uttarakhand":
            hp = get_hazard_processor()
            hazard_profile = hp.calculate_multi_hazard_exposure(lat, lon, district, household_id)
            hazards = hazard_profile["hazards"]
            composite_hazard = hazard_profile["composite_hazard_exposure"]
            hazard_tier = hazard_profile["hazard_tier"]
            elevation_m = hazard_profile.get("elevation_meters")
            slope_deg = hazard_profile.get("slope_degrees")
            terrain_cat = hazard_profile.get("terrain_category")
            detailed_breakdown = hazard_profile.get("detailed_breakdown", {})
        elif state == "Assam":
            f = float(hh.get("hazard_exposure", 0.85))
            r = round(f * 0.90, 2)
            rn = 0.80
            ls = 0.20
            hazards = {"flood": f, "river": r, "rainfall": rn, "landslide": ls}
            composite_hazard = round((f * 0.30) + (r * 0.30) + (rn * 0.25) + (ls * 0.15), 3)
            hazard_tier = "CRITICAL" if composite_hazard >= 0.80 else "HIGH" if composite_hazard >= 0.60 else "MODERATE"
            elevation_m, slope_deg, terrain_cat = None, None, "Brahmaputra Floodplain Basin"
            detailed_breakdown = {
                "flood": {"hazard": "flood", "exposure_score": f, "status": "PHASE_2_GIS_DATASET_PENDING"},
                "river": {"hazard": "river_flooding", "exposure_score": r, "status": "PHASE_2_GIS_DATASET_PENDING"},
                "rainfall": {"hazard": "heavy_rainfall", "exposure_score": rn, "status": "PHASE_2_GIS_DATASET_PENDING"},
                "landslide": {"hazard": "landslide", "exposure_score": ls, "status": "PHASE_2_GIS_DATASET_PENDING"}
            }
        else:
            # Odisha
            dist_lower = district.lower()
            is_coastal = any(cd in dist_lower for cd in ["puri", "kendrapara", "balasore", "ganjam"])
            cyc = 0.92 if is_coastal else 0.50
            cst = 0.85 if is_coastal else 0.25
            fl = 0.80
            rn = 0.75
            hazards = {"cyclone": cyc, "coastal": cst, "flood": fl, "rainfall": rn}
            composite_hazard = round((cyc * 0.35) + (cst * 0.25) + (fl * 0.25) + (rn * 0.15), 3)
            hazard_tier = "CRITICAL" if composite_hazard >= 0.80 else "HIGH" if composite_hazard >= 0.60 else "MODERATE"
            elevation_m, slope_deg, terrain_cat = None, None, "Coastal Inundation Zone"
            detailed_breakdown = {
                "cyclone": {"hazard": "cyclone", "exposure_score": cyc, "status": "PHASE_2_GIS_DATASET_PENDING"},
                "coastal": {"hazard": "coastal_flooding", "exposure_score": cst, "status": "PHASE_2_GIS_DATASET_PENDING"},
                "flood": {"hazard": "flood", "exposure_score": fl, "status": "PHASE_2_GIS_DATASET_PENDING"},
                "rainfall": {"hazard": "heavy_rainfall", "exposure_score": rn, "status": "PHASE_2_GIS_DATASET_PENDING"}
            }

        # --------------------------------------------------------------------
        # 2. Risk Engine Evaluation
        # --------------------------------------------------------------------
        risk_score = calculate_risk(hazards, state=state)
        risk_level = get_risk_level(risk_score)

        # --------------------------------------------------------------------
        # 3. Demographic Vulnerability & Priority
        # --------------------------------------------------------------------
        eval_record = dict(hh)
        eval_record["hazard_exposure"] = composite_hazard
        vuln_score = calculate_vulnerability_score(eval_record)
        vuln_level = get_vulnerability_level(vuln_score)
        priority_level = get_priority_level(vuln_level, composite_hazard)

        # --------------------------------------------------------------------
        # 4. Relocation Decision Engine
        # --------------------------------------------------------------------
        decision_info = determine_relocation_decision(
            risk_score=risk_score,
            risk_level=risk_level,
            vulnerability_score=vuln_score,
            vulnerability_level=vuln_level,
            priority_level=priority_level,
            hazard_exposure=composite_hazard
        )

        # --------------------------------------------------------------------
        # 5. Intelligent Shelter Matching (Capacity, Distance, Amenities)
        # --------------------------------------------------------------------
        household_context = {
            "household_id": household_id,
            "state": state,
            "latitude": lat,
            "longitude": lon,
            "population": hh.get("population", 1),
            "disabled": hh.get("disabled", 0),
            "elderly": hh.get("elderly", 0),
            "priority_level": priority_level,
            "vulnerability_level": vuln_level
        }

        all_shelters = list(SHELTERS_DB.values())
        ranked_shelters = recommend_shelters(household_context, all_shelters)

        recommended_centers: List[Dict[str, Any]] = []
        shelter_status_message = "Suitable relocation shelters identified and ranked."

        if decision_info["relocation_required"]:
            if ranked_shelters:
                # Provide top 3 best matching shelters
                recommended_centers = ranked_shelters[:3]
            else:
                shelter_status_message = "Relocation required, but no active shelters with available capacity were found within range."
        else:
            # Standby / nearest shelter options for non-emergency households
            recommended_centers = ranked_shelters[:2] if ranked_shelters else []
            shelter_status_message = "Household in monitor/safe status; standby shelters identified."

        # --------------------------------------------------------------------
        # 6. Comprehensive Frontend-Ready Response Structure
        # --------------------------------------------------------------------
        result = {
            "household_id": household_id,
            "location": {
                "state": state,
                "district": district,
                "village": village,
                "latitude": lat,
                "longitude": lon,
                "elevation_meters": elevation_m,
                "slope_degrees": slope_deg,
                "terrain_category": terrain_cat
            },
            "demographics": {
                "population": hh.get("population", 1),
                "children": hh.get("children", 0),
                "elderly": hh.get("elderly", 0),
                "disabled": hh.get("disabled", 0),
                "low_income": hh.get("low_income", False),
                "previous_disaster_exposure": hh.get("previous_disaster_exposure", False)
            },
            "hazards": hazards,
            "hazard_summary": {
                "composite_hazard_exposure": composite_hazard,
                "hazard_tier": hazard_tier
            },
            "risk": {
                "score": risk_score,
                "level": risk_level
            },
            "vulnerability": {
                "score": vuln_score,
                "level": vuln_level
            },
            "priority": priority_level,
            "relocation_decision": {
                "decision": decision_info["decision"],
                "relocation_required": decision_info["relocation_required"],
                "urgency_tier": decision_info["urgency_tier"],
                "recommended_action": decision_info["recommended_action"],
                "shelter_status": shelter_status_message
            },
            "recommended_centers": recommended_centers,
            "detailed_hazard_breakdown": detailed_breakdown
        }

        # Persist to SQLite hazard_assessments table if db session is provided
        if db is not None:
            try:
                rec_shelter = recommended_centers[0] if recommended_centers else {}
                existing_ass = db.query(HazardAssessmentModel).filter(HazardAssessmentModel.household_id == household_id).first()
                if existing_ass:
                    existing_ass.composite_hazard_exposure = composite_hazard
                    existing_ass.hazard_tier = hazard_tier
                    existing_ass.vulnerability_score = vuln_score
                    existing_ass.vulnerability_level = vuln_level
                    existing_ass.risk_score = risk_score
                    existing_ass.risk_level = risk_level
                    existing_ass.priority_level = priority_level
                    existing_ass.recommended_shelter_id = rec_shelter.get("center_id")
                    existing_ass.recommended_shelter_name = rec_shelter.get("name")
                    existing_ass.shelter_distance_km = rec_shelter.get("distance_km")
                else:
                    new_ass = HazardAssessmentModel(
                        assessment_id=f"ASS-{household_id}",
                        household_id=household_id,
                        state=state,
                        district=district,
                        village=village,
                        latitude=lat,
                        longitude=lon,
                        elevation_meters=elevation_m,
                        slope_degrees=slope_deg,
                        composite_hazard_exposure=composite_hazard,
                        hazard_tier=hazard_tier,
                        vulnerability_score=vuln_score,
                        vulnerability_level=vuln_level,
                        risk_score=risk_score,
                        risk_level=risk_level,
                        priority_level=priority_level,
                        recommended_shelter_id=rec_shelter.get("center_id"),
                        recommended_shelter_name=rec_shelter.get("name"),
                        shelter_distance_km=rec_shelter.get("distance_km")
                    )
                    db.add(new_ass)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Notice: caching assessment to SQLite: {e}")

        return result

    def get_high_risk_households(self, state: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves all households identified as requiring relocation,
        sorted by urgency tier (Tier 1 first) and risk score descending.
        """
        results = []
        target_state = state.strip().lower() if state else None

        for hid, hh in HOUSEHOLDS_DB.items():
            if target_state and hh.get("state", "").strip().lower() != target_state:
                continue
            assessment = self.get_household_assessment(hid)
            if assessment["relocation_decision"]["relocation_required"] or assessment["risk"]["level"] == "RED":
                results.append(assessment)

        # Sort: urgency_tier ASC (1 is highest urgency), risk score DESC, vulnerability score DESC
        results.sort(
            key=lambda x: (
                x["relocation_decision"]["urgency_tier"],
                -x["risk"]["score"],
                -x["vulnerability"]["score"]
            )
        )
        return results[:limit]

    def get_state_assessment(self, state: str) -> Dict[str, Any]:
        """
        Calculates an aggregate strategic disaster and relocation assessment for an entire state.
        """
        target_state = state.strip().lower()
        matching_hids = [
            hid for hid, hh in HOUSEHOLDS_DB.items()
            if hh.get("state", "").strip().lower() == target_state
        ]

        if not matching_hids:
            raise KeyError(f"No households registered for state '{state}'.")

        assessments = [self.get_household_assessment(hid) for hid in matching_hids]

        total_households = len(assessments)
        total_population = sum(a["demographics"]["population"] for a in assessments)

        risk_levels = {"RED": 0, "ORANGE": 0, "YELLOW": 0, "GREEN": 0}
        decisions = {
            ACTION_IMMEDIATE: 0,
            ACTION_HIGH: 0,
            ACTION_PREPARE: 0,
            ACTION_MONITOR: 0,
            ACTION_SAFE: 0
        }
        priorities = {"IMMEDIATE": 0, "HIGH": 0, "MODERATE": 0, "LOW": 0}

        relocation_needed_count = 0
        relocation_population = 0
        total_risk_score = 0.0
        total_vuln_score = 0.0
        district_data: Dict[str, Dict[str, Any]] = {}

        for a in assessments:
            rl = a["risk"]["level"]
            risk_levels[rl] = risk_levels.get(rl, 0) + 1
            total_risk_score += a["risk"]["score"]
            total_vuln_score += a["vulnerability"]["score"]

            dec = a["relocation_decision"]["decision"]
            decisions[dec] = decisions.get(dec, 0) + 1

            prio = a["priority"]
            priorities[prio] = priorities.get(prio, 0) + 1

            if a["relocation_decision"]["relocation_required"]:
                relocation_needed_count += 1
                relocation_population += a["demographics"]["population"]

            dist = a["location"]["district"]
            if dist not in district_data:
                district_data[dist] = {
                    "district": dist,
                    "households_count": 0,
                    "total_population": 0,
                    "relocation_required_count": 0,
                    "relocation_population": 0,
                    "risk_sum": 0.0
                }
            district_data[dist]["households_count"] += 1
            district_data[dist]["total_population"] += a["demographics"]["population"]
            district_data[dist]["risk_sum"] += a["risk"]["score"]
            if a["relocation_decision"]["relocation_required"]:
                district_data[dist]["relocation_required_count"] += 1
                district_data[dist]["relocation_population"] += a["demographics"]["population"]

        district_summaries = []
        for dist, data in district_data.items():
            avg_r = round(data["risk_sum"] / max(1, data["households_count"]), 2)
            district_summaries.append({
                "district": dist,
                "households_assessed": data["households_count"],
                "total_population": data["total_population"],
                "relocation_required_households": data["relocation_required_count"],
                "evacuation_headcount": data["relocation_population"],
                "average_risk_score": avg_r
            })
        district_summaries.sort(key=lambda d: (-d["relocation_required_households"], -d["average_risk_score"]))

        shelters_in_state = [
            s for s in SHELTERS_DB.values()
            if s.get("state", "").strip().lower() == target_state and s.get("active", True)
        ]
        total_shelter_capacity = sum(s.get("total_capacity", s.get("capacity", 0)) for s in shelters_in_state)
        total_available_capacity = sum(s.get("available_capacity", 0) for s in shelters_in_state)

        high_risk_sample = sorted(
            [a for a in assessments if a["relocation_decision"]["relocation_required"]],
            key=lambda x: (x["relocation_decision"]["urgency_tier"], -x["risk"]["score"])
        )[:5]

        canonical_state = assessments[0]["location"]["state"]

        return {
            "state": canonical_state,
            "total_households_assessed": total_households,
            "total_population_indexed": total_population,
            "average_risk_score": round(total_risk_score / max(1, total_households), 2),
            "average_vulnerability_score": round(total_vuln_score / max(1, total_households), 2),
            "relocation_overview": {
                "households_requiring_relocation": relocation_needed_count,
                "evacuation_headcount": relocation_population,
                "percentage_requiring_relocation": round((relocation_needed_count / max(1, total_households)) * 100, 1),
                "decisions_breakdown": decisions
            },
            "risk_distribution": risk_levels,
            "priority_distribution": priorities,
            "shelter_infrastructure": {
                "active_shelters_in_state": len(shelters_in_state),
                "total_shelter_capacity": total_shelter_capacity,
                "total_available_capacity": total_available_capacity,
                "capacity_surplus_deficit": total_available_capacity - relocation_population
            },
            "district_breakdown": district_summaries,
            "highest_urgency_households": high_risk_sample
        }

    def get_district_assessment(self, district: str, state: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates a district-level disaster assessment and operational relocation plan.
        """
        target_dist = district.strip().lower()
        target_state = state.strip().lower() if state else None

        matching_hids = []
        for hid, hh in HOUSEHOLDS_DB.items():
            if hh.get("district", "").strip().lower() == target_dist:
                if target_state is None or hh.get("state", "").strip().lower() == target_state:
                    matching_hids.append(hid)

        if not matching_hids:
            raise KeyError(f"No households registered for district '{district}'.")

        assessments = [self.get_household_assessment(hid) for hid in matching_hids]

        total_households = len(assessments)
        total_population = sum(a["demographics"]["population"] for a in assessments)

        risk_levels = {"RED": 0, "ORANGE": 0, "YELLOW": 0, "GREEN": 0}
        decisions = {
            ACTION_IMMEDIATE: 0,
            ACTION_HIGH: 0,
            ACTION_PREPARE: 0,
            ACTION_MONITOR: 0,
            ACTION_SAFE: 0
        }

        relocation_households = []
        relocation_population = 0
        total_risk = 0.0

        for a in assessments:
            rl = a["risk"]["level"]
            risk_levels[rl] = risk_levels.get(rl, 0) + 1
            total_risk += a["risk"]["score"]

            dec = a["relocation_decision"]["decision"]
            decisions[dec] = decisions.get(dec, 0) + 1

            if a["relocation_decision"]["relocation_required"]:
                relocation_households.append(a)
                relocation_population += a["demographics"]["population"]

        canonical_district = assessments[0]["location"]["district"]
        canonical_state = assessments[0]["location"]["state"]

        relocation_households.sort(
            key=lambda x: (x["relocation_decision"]["urgency_tier"], -x["risk"]["score"])
        )

        return {
            "district": canonical_district,
            "state": canonical_state,
            "total_households_assessed": total_households,
            "total_population": total_population,
            "average_risk_score": round(total_risk / max(1, total_households), 2),
            "evacuation_summary": {
                "households_requiring_relocation": len(relocation_households),
                "evacuation_headcount": relocation_population,
                "decisions_breakdown": decisions
            },
            "risk_distribution": risk_levels,
            "households_requiring_relocation": relocation_households,
            "all_household_assessments": assessments
        }


# Global engine singleton
_engine_instance: Optional[DisasterAssessmentEngine] = None


def get_assessment_engine() -> DisasterAssessmentEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = DisasterAssessmentEngine()
    return _engine_instance

