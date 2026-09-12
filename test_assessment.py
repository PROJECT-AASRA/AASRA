"""
Test Suite for Project AASRA - Final Disaster Assessment & Intelligent Relocation Decision Engine
Verifies:
1. End-to-end assessment calculation (Real hazards + Risk + Vulnerability + Relocation decision + Shelter matching)
2. Relocation decision heuristics (Immediate, High Priority, Prepare, Monitor, No Action)
3. High-risk prioritization queue sorting (Urgency Tier 1 -> 2 -> 3, Risk Score DESC)
4. State strategic disaster overview & aggregation
5. District operational evacuation report & shelter capacity
6. Live HTTP REST API endpoints (/assessment/household, /high-risk, /state, /district)
"""

import json
import urllib.request
from app.services.assessment import (
    get_assessment_engine,
    determine_relocation_decision,
    ACTION_IMMEDIATE,
    ACTION_HIGH,
    ACTION_PREPARE,
    ACTION_MONITOR,
    ACTION_SAFE
)
from app.routes.households import HOUSEHOLDS_DB


def test_decision_heuristics():
    print("\n--- TEST 1: Relocation Decision Heuristics ---")
    d1 = determine_relocation_decision(risk_score=85.0, risk_level="RED", vulnerability_score=75.0, vulnerability_level="HIGH", priority_level="IMMEDIATE", hazard_exposure=0.9)
    assert d1["decision"] == ACTION_IMMEDIATE
    assert d1["relocation_required"] is True
    assert d1["urgency_tier"] == 1

    d2 = determine_relocation_decision(risk_score=68.0, risk_level="RED", vulnerability_score=50.0, vulnerability_level="MEDIUM", priority_level="HIGH", hazard_exposure=0.7)
    assert d2["decision"] == ACTION_HIGH
    assert d2["relocation_required"] is True
    assert d2["urgency_tier"] == 2

    d3 = determine_relocation_decision(risk_score=45.0, risk_level="ORANGE", vulnerability_score=40.0, vulnerability_level="LOW", priority_level="MODERATE", hazard_exposure=0.5)
    assert d3["decision"] == ACTION_PREPARE
    assert d3["relocation_required"] is True
    assert d3["urgency_tier"] == 3

    d4 = determine_relocation_decision(risk_score=25.0, risk_level="YELLOW", vulnerability_score=30.0, vulnerability_level="LOW", priority_level="LOW", hazard_exposure=0.3)
    assert d4["decision"] == ACTION_MONITOR
    assert d4["relocation_required"] is False
    assert d4["urgency_tier"] == 4

    d5 = determine_relocation_decision(risk_score=12.0, risk_level="GREEN", vulnerability_score=15.0, vulnerability_level="LOW", priority_level="LOW", hazard_exposure=0.1)
    assert d5["decision"] == ACTION_SAFE
    assert d5["relocation_required"] is False
    assert d5["urgency_tier"] == 5
    print("[PASS] All 5 relocation decision heuristic tiers verified.")


def test_household_assessment():
    print("\n--- TEST 2: End-to-End Household Assessment (HH-UK-001) ---")
    engine = get_assessment_engine()
    res = engine.get_household_assessment("HH-UK-001")

    assert res["household_id"] == "HH-UK-001"
    assert res["location"]["district"] == "Chamoli"
    assert res["risk"]["level"] in ["RED", "ORANGE", "YELLOW", "GREEN"]
    assert res["vulnerability"]["level"] in ["HIGH", "MEDIUM", "LOW"]
    assert res["relocation_decision"]["decision"] in [
        ACTION_IMMEDIATE, ACTION_HIGH, ACTION_PREPARE, ACTION_MONITOR, ACTION_SAFE
    ]
    assert len(res["recommended_centers"]) > 0

    shelter0 = res["recommended_centers"][0]
    assert "center_id" in shelter0
    assert "distance_km" in shelter0
    assert "available_capacity" in shelter0
    assert shelter0["available_capacity"] > 0
    print(f"[PASS] HH-UK-001 assessed: Risk={res['risk']['score']} ({res['risk']['level']}), Priority={res['priority']}, Decision={res['relocation_decision']['decision']}")
    print(f"       Assigned Shelter: {shelter0['name']} ({shelter0['distance_km']} km away, cap={shelter0['available_capacity']})")


def test_high_risk_queue():
    print("\n--- TEST 3: High-Risk Prioritization Queue ---")
    engine = get_assessment_engine()
    queue = engine.get_high_risk_households(limit=10)
    assert len(queue) > 0

    # Verify sorting: urgency_tier ascending, risk score descending
    for i in range(len(queue) - 1):
        curr_tier = queue[i]["relocation_decision"]["urgency_tier"]
        next_tier = queue[i + 1]["relocation_decision"]["urgency_tier"]
        assert curr_tier <= next_tier, f"Queue ordering violation: tier {curr_tier} before {next_tier}"
        if curr_tier == next_tier:
            curr_risk = queue[i]["risk"]["score"]
            next_risk = queue[i + 1]["risk"]["score"]
            assert curr_risk >= next_risk, f"Queue risk violation: {curr_risk} < {next_risk} in same tier"

    print(f"[PASS] High-risk queue sorted correctly across {len(queue)} priority households.")


def test_state_and_district_assessment():
    print("\n--- TEST 4: State & District Assessment Aggregations ---")
    engine = get_assessment_engine()
    st = engine.get_state_assessment("Uttarakhand")
    assert st["state"] == "Uttarakhand"
    assert st["total_households_assessed"] == 40
    assert st["relocation_overview"]["households_requiring_relocation"] > 0
    assert st["shelter_infrastructure"]["active_shelters_in_state"] == 256
    assert st["shelter_infrastructure"]["total_available_capacity"] > 0
    print(f"[PASS] State Uttarakhand: {st['total_households_assessed']} households, {st['relocation_overview']['households_requiring_relocation']} need relocation, {st['shelter_infrastructure']['total_available_capacity']} available shelter capacity.")

    dist = engine.get_district_assessment("Chamoli")
    assert dist["district"] == "Chamoli"
    assert dist["total_households_assessed"] == 8
    assert dist["evacuation_summary"]["households_requiring_relocation"] > 0
    print(f"[PASS] District Chamoli: {dist['total_households_assessed']} households assessed, {dist['evacuation_summary']['evacuation_headcount']} persons in evacuation headcount.")


def test_live_rest_api():
    print("\n--- TEST 5: Live HTTP REST API Endpoints ---")
    base_url = "http://127.0.0.1:8000/assessment"

    # 1. Household
    req = urllib.request.urlopen(f"{base_url}/household/HH-UK-001")
    assert req.getcode() == 200
    data = json.loads(req.read())
    assert data["household_id"] == "HH-UK-001"
    print("[PASS] GET /assessment/household/HH-UK-001 -> HTTP 200 OK")

    # 2. High Risk
    req = urllib.request.urlopen(f"{base_url}/high-risk?state=Uttarakhand&limit=5")
    assert req.getcode() == 200
    data = json.loads(req.read())
    assert data["status"] == "success"
    assert len(data["households"]) == 5
    print(f"[PASS] GET /assessment/high-risk?state=Uttarakhand&limit=5 -> HTTP 200 OK ({len(data['households'])} records)")

    # 3. State
    req = urllib.request.urlopen(f"{base_url}/state/Uttarakhand")
    assert req.getcode() == 200
    data = json.loads(req.read())
    assert data["state"] == "Uttarakhand"
    print(f"[PASS] GET /assessment/state/Uttarakhand -> HTTP 200 OK ({data['total_households_assessed']} households)")

    # 4. District
    req = urllib.request.urlopen(f"{base_url}/district/Chamoli")
    assert req.getcode() == 200
    data = json.loads(req.read())
    assert data["district"] == "Chamoli"
    print(f"[PASS] GET /assessment/district/Chamoli -> HTTP 200 OK ({data['total_households_assessed']} households)")


if __name__ == "__main__":
    test_decision_heuristics()
    test_household_assessment()
    test_high_risk_queue()
    test_state_and_district_assessment()
    test_live_rest_api()
    print("\n========================================================")
    print("ALL 5 ASSESSMENT & RELOCATION DECISION ENGINE TESTS PASSED!")
    print("========================================================\n")
