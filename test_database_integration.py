"""
Comprehensive Database Integration Test Suite for Project AASRA.
Validates SQLite (disaster.db) and SQLAlchemy ORM across:
- Schema generation and table inspection
- Demographic household CRUD & SQLite persistence
- Relocation shelter CRUD & SQLite capacity tracking
- Shelter recommendation engine reading from SQLite
- Disaster assessment pipeline caching into hazard_assessments table
- GIS GeoJSON layers reading active SQLite records
"""

import os
from sqlalchemy import inspect
from fastapi.testclient import TestClient

from app.main import app
from app.database import engine, SessionLocal, DB_PATH
from app.models import HouseholdModel, RelocationCenterModel, HazardAssessmentModel
from app.seed_db import seed_database


client = TestClient(app)


def test_1_database_schema_and_seeding():
    """Verify tables exist and baseline records are loaded in SQLite."""
    print("\n--- TEST 1: Database Schema & Baseline Seeding ---")
    assert DB_PATH.exists(), "disaster.db must exist on disk"
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "households" in tables, "Table 'households' must exist"
    assert "relocation_centers" in tables, "Table 'relocation_centers' must exist"
    assert "hazard_assessments" in tables, "Table 'hazard_assessments' must exist"

    db = SessionLocal()
    try:
        hh_count = db.query(HouseholdModel).count()
        rc_count = db.query(RelocationCenterModel).count()
        assert hh_count >= 50, f"Expected >= 50 households, found {hh_count}"
        assert rc_count >= 260, f"Expected >= 260 shelters, found {rc_count}"
        print(f"[PASS] Schema verified. Total SQLite Households: {hh_count}, Shelters: {rc_count}")
    finally:
        db.close()


def test_2_household_crud_sqlite():
    """Verify Household CRUD operations persist directly to SQLite."""
    print("\n--- TEST 2: Household SQLite CRUD & Recalculation ---")
    test_id = "HH-TEST-SQLITE-01"

    # 1. Create household
    payload = {
        "household_id": test_id,
        "state": "Uttarakhand",
        "district": "Chamoli",
        "village": "Pipalkoti Riverside",
        "latitude": 30.43,
        "longitude": 79.33,
        "population": 6,
        "children": 2,
        "elderly": 1,
        "disabled": 1,
        "low_income": True,
        "hazard_exposure": 0.85,
        "previous_disaster_exposure": True
    }
    res_post = client.post("/households/", json=payload)
    assert res_post.status_code == 201, f"POST failed: {res_post.text}"
    data_post = res_post.json()
    assert data_post["household_id"] == test_id
    assert data_post["vulnerability_level"] in ["HIGH", "CRITICAL"]

    # Verify presence in SQLite
    db = SessionLocal()
    try:
        hh_db = db.query(HouseholdModel).filter(HouseholdModel.household_id == test_id).first()
        assert hh_db is not None, "Created household must exist in SQLite database"
        assert hh_db.population == 6
        assert hh_db.disabled == 1
    finally:
        db.close()
    print(f"[PASS] Household {test_id} created and verified in SQLite table 'households'")

    # 2. Read household via API
    res_get = client.get(f"/households/{test_id}")
    assert res_get.status_code == 200
    assert res_get.json()["village"] == "Pipalkoti Riverside"

    # 3. Update household
    update_payload = {"population": 7, "elderly": 2}
    res_put = client.put(f"/households/{test_id}", json=update_payload)
    assert res_put.status_code == 200
    assert res_put.json()["population"] == 7

    # Verify update in SQLite
    db = SessionLocal()
    try:
        hh_db = db.query(HouseholdModel).filter(HouseholdModel.household_id == test_id).first()
        assert hh_db.population == 7
        assert hh_db.elderly == 2
    finally:
        db.close()
    print(f"[PASS] Household {test_id} updated and verified in SQLite")

    # 4. Check vulnerability & priority endpoints
    res_v = client.get(f"/households/{test_id}/vulnerability")
    assert res_v.status_code == 200
    assert "vulnerability_score" in res_v.json()

    res_p = client.get(f"/households/{test_id}/priority")
    assert res_p.status_code == 200
    assert "priority_level" in res_p.json()

    # 5. Delete household
    res_del = client.delete(f"/households/{test_id}")
    assert res_del.status_code == 200

    # Verify deletion in SQLite
    db = SessionLocal()
    try:
        hh_db = db.query(HouseholdModel).filter(HouseholdModel.household_id == test_id).first()
        assert hh_db is None, "Household must be deleted from SQLite"
    finally:
        db.close()
    print(f"[PASS] Household {test_id} deleted and confirmed removed from SQLite")


def test_3_shelter_crud_sqlite():
    """Verify Relocation Center CRUD operations persist directly to SQLite."""
    print("\n--- TEST 3: Relocation Center SQLite CRUD & Capacity Tracking ---")
    test_shelter_id = "SHELTER-TEST-SQLITE-01"

    # 1. Create shelter
    payload = {
        "center_id": test_shelter_id,
        "name": "Chamoli Municipal Relief Center",
        "state": "Uttarakhand",
        "district": "Chamoli",
        "village": "Gopeshwar",
        "latitude": 30.415,
        "longitude": 79.330,
        "total_capacity": 250,
        "current_occupancy": 50,
        "medical_support": True,
        "food_available": True,
        "water_available": True,
        "sanitation_available": True,
        "accessible_for_disabled": True,
        "active": True
    }
    res_post = client.post("/relocation/", json=payload)
    assert res_post.status_code == 201
    assert res_post.json()["available_capacity"] == 200

    # Verify in SQLite
    db = SessionLocal()
    try:
        rc_db = db.query(RelocationCenterModel).filter(RelocationCenterModel.center_id == test_shelter_id).first()
        assert rc_db is not None
        assert rc_db.total_capacity == 250
    finally:
        db.close()
    print(f"[PASS] Shelter {test_shelter_id} created and verified in SQLite table 'relocation_centers'")

    # 2. Read shelter capacity
    res_cap = client.get(f"/relocation/{test_shelter_id}/capacity")
    assert res_cap.status_code == 200
    assert res_cap.json()["available_capacity"] == 200

    # 3. Update occupancy
    res_put = client.put(f"/relocation/{test_shelter_id}", json={"current_occupancy": 150})
    assert res_put.status_code == 200
    assert res_put.json()["available_capacity"] == 100

    # 4. Delete shelter
    res_del = client.delete(f"/relocation/{test_shelter_id}")
    assert res_del.status_code == 200

    # Verify deletion in SQLite
    db = SessionLocal()
    try:
        rc_db = db.query(RelocationCenterModel).filter(RelocationCenterModel.center_id == test_shelter_id).first()
        assert rc_db is None
    finally:
        db.close()
    print(f"[PASS] Shelter {test_shelter_id} deleted and confirmed removed from SQLite")


def test_4_shelter_recommendation_with_sqlite():
    """Verify shelter recommendation reads from SQLite."""
    print("\n--- TEST 4: Evacuation Recommendations via SQLite Shelters ---")
    res = client.get("/relocation/recommend/HH-UK-001")
    assert res.status_code == 200
    data = res.json()
    assert data["household_id"] == "HH-UK-001"
    assert len(data["recommended_centers"]) > 0
    top_shelter = data["recommended_centers"][0]
    assert "center_id" in top_shelter
    assert "distance_km" in top_shelter
    print(f"[PASS] Top shelter recommended for HH-UK-001: {top_shelter['name']} ({top_shelter['distance_km']} km away)")


def test_5_disaster_assessment_sqlite_caching():
    """Verify disaster assessment runs and caches results into hazard_assessments table."""
    print("\n--- TEST 5: Assessment Engine & SQLite Assessment Caching ---")
    res = client.get("/assessment/household/HH-UK-001")
    assert res.status_code == 200
    data = res.json()
    assert data["relocation_decision"]["relocation_required"] is True

    # Verify SQLite table 'hazard_assessments'
    db = SessionLocal()
    try:
        ass_db = db.query(HazardAssessmentModel).filter(HazardAssessmentModel.household_id == "HH-UK-001").first()
        assert ass_db is not None, "Computed assessment must be cached in SQLite table 'hazard_assessments'"
        assert ass_db.risk_level == data["risk"]["level"]
        assert ass_db.composite_hazard_exposure > 0
        print(f"[PASS] Assessment cached in SQLite: Assessment ID={ass_db.assessment_id}, Risk={ass_db.risk_score} ({ass_db.risk_level})")
    finally:
        db.close()


def test_6_gis_layers_powered_by_sqlite():
    """Verify GIS GeoJSON endpoints deliver complete datasets backed by SQLite."""
    print("\n--- TEST 6: GIS GeoJSON Layers Powered by SQLite ---")
    res_shelters = client.get("/gis/shelters")
    assert res_shelters.status_code == 200
    features_s = res_shelters.json()["features"]
    assert len(features_s) >= 260, f"Expected >= 260 shelter GeoJSON features, got {len(features_s)}"

    res_hh = client.get("/gis/households")
    assert res_hh.status_code == 200
    features_h = res_hh.json()["features"]
    assert len(features_h) >= 50, f"Expected >= 50 household GeoJSON features, got {len(features_h)}"
    print(f"[PASS] GIS GeoJSON layers verified: {len(features_s)} shelters, {len(features_h)} households")


if __name__ == "__main__":
    print("==========================================================")
    print("  PROJECT AASRA - COMPREHENSIVE DATABASE INTEGRATION TEST")
    print("==========================================================")
    test_1_database_schema_and_seeding()
    test_2_household_crud_sqlite()
    test_3_shelter_crud_sqlite()
    test_4_shelter_recommendation_with_sqlite()
    test_5_disaster_assessment_sqlite_caching()
    test_6_gis_layers_powered_by_sqlite()
    print("==========================================================")
    print("  ALL 6 DATABASE INTEGRATION TESTS PASSED! (100% SUCCESS)")
    print("==========================================================")
