"""
Comprehensive Test Suite for Real Hazard Exposure Engine
Validates:
1. UttarakhandHazardProcessor core algorithms & spatial indices
2. Risk Engine calibration with Himalayan hazard weights
3. REST API modular endpoints (/flood, /river, /landslide, /rainfall, /multi, /calculate)
4. Household vulnerability & emergency priority calibration
5. Automated shelter routing based on real hazard exposure
"""

import json
import urllib.request
import urllib.error
from app.services.hazard_processor import get_hazard_processor
from app.services.risk import calculate_risk, get_risk_level

BASE_URL = "http://127.0.0.1:8000"

def get_api(path: str):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status, json.loads(response.read().decode("utf-8"))

def run_tests():
    print("=" * 70)
    print("STARTING PROJECT AASRA - REAL HAZARD EXPOSURE ENGINE TEST SUITE")
    print("=" * 70)
    passed = 0
    total = 0

    # ------------------------------------------------------------------------
    # TEST 1: Hazard Processor Spatial Containment & Buffer (Flood)
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 1] Flood Layer Spatial R-Tree Indexing...")
    hp = get_hazard_processor()
    f_in = hp.calculate_flood_exposure(30.558, 79.565, "Chamoli")
    assert f_in["inside_hazard_zone"] is True, "Expected inside_hazard_zone to be True for Joshimath"
    assert f_in["exposure_score"] >= 0.90, f"Expected high score, got {f_in['exposure_score']}"
    assert f_in["exposure_level"] == "CRITICAL"
    print(f"  -> Joshimath Flood Zone: Score={f_in['exposure_score']}, ID={f_in.get('historical_disaster_id')}, Cause={f_in.get('disaster_cause')}")

    # Point far away from any flood polygon (Udham Singh Nagar plains: 28.98, 79.40)
    f_out = hp.calculate_flood_exposure(28.98, 79.40, "Udham Singh Nagar")
    assert f_out["inside_hazard_zone"] is False
    assert f_out["distance_to_flood_zone_km"] > 5.0
    print(f"  -> Udham Singh Nagar: Distance={f_out['distance_to_flood_zone_km']} km, Score={f_out['exposure_score']}, Tier={f_out['exposure_level']}")
    passed += 1
    print("  [PASS] Test 1: Flood spatial indexing validated.")

    # ------------------------------------------------------------------------
    # TEST 2: River Proximity Great-Circle Calculation (525 River Polygons)
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 2] River Geometry Proximity Analysis...")
    r_res = hp.calculate_river_exposure(30.558, 79.565, "Chamoli")
    assert "distance_to_river_km" in r_res
    assert 0.0 <= r_res["exposure_score"] <= 1.0
    assert r_res["source_dataset"] == "uttarakhand_river_4326.geojson"
    print(f"  -> Distance to river: {r_res['distance_to_river_km']} km, Score: {r_res['exposure_score']}, Tier: {r_res['exposure_level']}")
    passed += 1
    print("  [PASS] Test 2: River proximity calculations validated.")

    # ------------------------------------------------------------------------
    # TEST 3: Landslide Empirical Disaster Damage & Geomorphology
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 3] Landslide Historical Disaster Damage Ingestion (3,945 Events)...")
    ls_chamoli = hp.calculate_landslide_exposure(30.558, 79.565, "Chamoli")
    assert ls_chamoli["historical_houses_destroyed"] > 0
    assert ls_chamoli["historical_houses_damaged"] > 0
    assert ls_chamoli["exposure_score"] >= 0.80
    print(f"  -> Chamoli: Landslides={ls_chamoli['historical_landslides_in_district']}, Destroyed Houses={ls_chamoli['historical_houses_destroyed']}, Score={ls_chamoli['exposure_score']}")

    ls_plains = hp.calculate_landslide_exposure(28.98, 79.40, "Udham Singh Nagar")
    assert ls_plains["exposure_score"] < ls_chamoli["exposure_score"]
    assert ls_plains["exposure_level"] == "LOW"
    assert ls_plains["distance_to_nearest_landslide_km"] > 15.0
    print(f"  -> Udham Singh Nagar (Plains): Nearest Landslide={ls_plains['distance_to_nearest_landslide_km']} km, Score={ls_plains['exposure_score']}, Tier={ls_plains['exposure_level']}")
    passed += 1
    print("  [PASS] Test 3: Landslide GSI proximity & DEM slope model validated.")


    # ------------------------------------------------------------------------
    # TEST 4: Rainfall Station Telemetry & Cloudburst Thresholds
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 4] Rainfall Telemetry Analysis & IMD Benchmarks (7,200+ Readings)...")
    rn_res = hp.calculate_rainfall_exposure(30.558, 79.565, "Chamoli")
    assert rn_res["peak_daily_rainfall_mm"] > 50.0
    assert rn_res["exposure_score"] >= 0.75
    print(f"  -> Station: '{rn_res['monitored_station']}', Peak Rainfall: {rn_res['peak_daily_rainfall_mm']} mm, Score: {rn_res['exposure_score']}")
    passed += 1
    print("  [PASS] Test 4: Rainfall telemetry evaluation validated.")

    # ------------------------------------------------------------------------
    # TEST 5: Risk Engine Calibration (Himalayan Hazard Weights)
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 5] Risk Engine Calibration with Himalayan Weights...")
    himalayan_hazards = {"flood": 0.95, "river": 0.55, "landslide": 0.89, "rainfall": 0.95}
    risk_score = calculate_risk(himalayan_hazards, state="Uttarakhand")
    risk_tier = get_risk_level(risk_score)
    assert 80.0 <= risk_score <= 90.0, f"Expected ~83.5, got {risk_score}"
    assert risk_tier == "RED"
    print(f"  -> Himalayan Hazard Profile: Risk Score={risk_score}%, Alert Tier={risk_tier}")
    passed += 1
    print("  [PASS] Test 5: Risk Engine calibration validated.")

    # ------------------------------------------------------------------------
    # TEST 6: Modular REST API Endpoints (/flood, /river, /landslide, /rainfall)
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 6] Testing Modular Hazard Endpoints via Live REST API...")
    endpoints = ["flood", "river", "landslide", "rainfall", "multi"]
    for ep in endpoints:
        status, data = get_api(f"/hazards/household/HH-UK-001/{ep}")
        assert status == 200, f"Failed GET /hazards/household/HH-UK-001/{ep}: status {status}"
        assert data["household_id"] == "HH-UK-001"
        print(f"  -> GET /hazards/household/HH-UK-001/{ep} [HTTP 200 OK]")
    passed += 1
    print("  [PASS] Test 6: All modular household hazard endpoints returned HTTP 200.")

    # ------------------------------------------------------------------------
    # TEST 7: Dynamic Coordinate Calculation Endpoint (/hazards/calculate)
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 7] Testing Dynamic Coordinate Calculation Endpoint...")
    status, data = get_api("/hazards/calculate?latitude=30.41&longitude=79.32&district=Chamoli")
    assert status == 200
    assert "composite_hazard_exposure" in data
    assert "compound_risk_score" in data
    assert "detailed_breakdown" in data
    print(f"  -> Point (30.41, 79.32): Composite Exposure={data['composite_hazard_exposure']}, Risk={data['compound_risk_score']}%, Alert={data['risk_level']}")
    passed += 1
    print("  [PASS] Test 7: Dynamic coordinate calculation validated.")

    # ------------------------------------------------------------------------
    # TEST 8: Household API Integration (Real Hazard Exposure & Priority)
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 8] Testing Household API Integration...")
    status, hh = get_api("/households/HH-UK-001")
    assert status == 200
    assert hh["priority_level"] == "IMMEDIATE"
    assert hh["vulnerability_level"] == "HIGH"
    assert hh["hazard_tier"] == "CRITICAL"
    assert hh["risk_level"] == "RED"
    print(f"  -> HH-UK-001: Vulnerability={hh['vulnerability_score']} ({hh['vulnerability_level']}), Hazard={hh['hazard_exposure']}, Priority={hh['priority_level']}")
    passed += 1
    print("  [PASS] Test 8: Household API real hazard calibration validated.")

    # ------------------------------------------------------------------------
    # TEST 9: Shelter Recommendation for High-Hazard Evacuee
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 9] Testing Shelter Recommendation Integration...")
    status, recs = get_api("/relocation/recommend/HH-UK-001")
    assert status == 200
    assert recs["priority_level"] == "IMMEDIATE"
    assert len(recs["recommended_centers"]) > 0
    top_shelter = recs["recommended_centers"][0]
    assert top_shelter["available_capacity"] > 0
    assert top_shelter["distance_km"] < 25.0
    print(f"  -> Recommended: '{top_shelter['name']}' at {top_shelter['distance_km']} km (Capacity: {top_shelter['available_capacity']})")
    passed += 1
    print("  [PASS] Test 9: Relocation recommendation validated.")

    # ------------------------------------------------------------------------
    # TEST 10: Multi-Hazard Evaluation for Assam (Brahmaputra Flood Basin)
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 10] Testing Assam State-Specific Multi-Hazard Profile...")
    status, as_data = get_api("/hazards/household/HH-AS-001/multi")
    assert status == 200
    assert as_data["state"] == "Assam"
    assert "flood" in as_data["hazards"]
    assert "river" in as_data["hazards"]
    assert "rainfall" in as_data["hazards"]
    assert "cyclone" not in as_data["hazards"]  # Non-coastal
    print(f"  -> Assam (Dhubri): Flood={as_data['hazards']['flood']}, River={as_data['hazards']['river']}, Risk={as_data['compound_risk_score']}%, Alert={as_data['risk_level']}")
    passed += 1
    print("  [PASS] Test 10: Assam state-specific hazard profile validated.")

    # ------------------------------------------------------------------------
    # TEST 11: Multi-Hazard & Cyclone Evaluation for Odisha (Bay of Bengal)
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 11] Testing Odisha State-Specific Cyclone & Coastal Profile...")
    status, od_data = get_api("/hazards/household/HH-OD-001/multi")
    assert status == 200
    assert od_data["state"] == "Odisha"
    assert "cyclone" in od_data["hazards"]
    assert "coastal" in od_data["hazards"]
    assert "landslide" not in od_data["hazards"]  # Coastal plain
    assert od_data["hazards"]["cyclone"] >= 0.85

    # Test individual cyclone endpoint
    status_cyc, cyc_data = get_api("/hazards/household/HH-OD-001/cyclone")
    assert status_cyc == 200
    assert cyc_data["hazard"] == "cyclone"
    print(f"  -> Odisha (Puri): Cyclone={od_data['hazards']['cyclone']}, Coastal={od_data['hazards']['coastal']}, Risk={od_data['compound_risk_score']}%, Alert={od_data['risk_level']}")
    passed += 1
    print("  [PASS] Test 11: Odisha cyclone & coastal hazard profile validated.")

    # ------------------------------------------------------------------------
    # TEST 12: Hazard State Applicability & Error Handling
    # ------------------------------------------------------------------------
    total += 1
    print("\n[TEST 12] Testing Hazard State Applicability Validation...")
    # Cyclone in Himalayan Uttarakhand should return HTTP 400
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/hazards/household/HH-UK-001/cyclone")
        assert False, "Expected HTTP 400 for cyclone in Uttarakhand"
    except urllib.error.HTTPError as e:
        assert e.code == 400
        print("  -> Cyclone on Uttarakhand correctly rejected: HTTP 400")

    # Landslide in coastal Odisha should return HTTP 400
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/hazards/household/HH-OD-001/landslide")
        assert False, "Expected HTTP 400 for landslide in coastal Odisha"
    except urllib.error.HTTPError as e:
        assert e.code == 400
        print("  -> Landslide on coastal Odisha correctly rejected: HTTP 400")
    passed += 1
    print("  [PASS] Test 12: Hazard state applicability and error handling validated.")

    # ------------------------------------------------------------------------
    # TEST 13: Continuous 30m DEM Elevation & Slope Topographic Profiling
    # ------------------------------------------------------------------------
    total += 1

    print("\n[TEST 13] Testing Continuous 30m DEM Elevation & Slope Topographic Profiling...")
    status_t, terrain = get_api("/hazards/household/HH-UK-001/terrain")
    assert status_t == 200
    assert terrain["elevation_meters"] > 1500.0, f"Expected mountain elevation >1500m, got {terrain['elevation_meters']}"
    assert terrain["slope_degrees"] > 15.0, f"Expected steep slope >15 deg, got {terrain['slope_degrees']}"
    assert "source_dataset" in terrain

    status_e, elev_data = get_api("/hazards/household/HH-UK-001/elevation")
    assert status_e == 200
    assert elev_data["elevation_meters"] == terrain["elevation_meters"]

    status_s, slope_data = get_api("/hazards/household/HH-UK-001/slope")
    assert status_s == 200
    assert slope_data["slope_degrees"] == terrain["slope_degrees"]
    print(f"  -> Joshimath DEM: Elevation = {terrain['elevation_meters']} m ({terrain['elevation_category']}), Slope = {terrain['slope_degrees']}° ({terrain['slope_category']})")
    passed += 1
    print("  [PASS] Test 13: Continuous DEM elevation, slope, and terrain endpoints validated.")

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{total} TESTS PASSED SUCCESSFULLY! (100% PASS RATE)")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()


