"""
Step 1 Verification Test Suite: Database & ORM Models
Validates SQLite connection, session factory, and ORM models for AASRA.
"""

from sqlalchemy import inspect
from app.database import engine, SessionLocal, get_db, DB_PATH
from app.models import HouseholdModel, RelocationCenterModel, HazardAssessmentModel


def test_database_engine_and_file():
    """Verify that the database file exists and the engine connects properly."""
    assert DB_PATH.exists(), "disaster.db file should exist on disk"
    with engine.connect() as conn:
        assert conn is not None
    print("[PASS] Database engine connected successfully to disaster.db")


def test_tables_exist():
    """Verify that all required tables exist in the SQLite database."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    required = ["households", "relocation_centers", "hazard_assessments"]
    for table in required:
        assert table in tables, f"Table {table} must exist in SQLite database"
    print(f"[PASS] All tables present in database: {tables}")


def test_household_model_crud():
    """Verify inserting and reading a HouseholdModel record."""
    db = SessionLocal()
    test_hh_id = "TEST_HH_001"
    try:
        # Clean existing test record if any
        existing = db.query(HouseholdModel).filter(HouseholdModel.household_id == test_hh_id).first()
        if existing:
            db.delete(existing)
            db.commit()

        # Insert test household
        hh = HouseholdModel(
            household_id=test_hh_id,
            state="Uttarakhand",
            district="Chamoli",
            village="Joshimath",
            latitude=30.556,
            longitude=79.567,
            population=5,
            children=1,
            elderly=1,
            disabled=0,
            low_income=True,
            hazard_exposure=0.75,
            previous_disaster_exposure=1.0,
            vulnerability_score=68.5,
            vulnerability_level="High",
            priority_level="Priority 1 (Immediate Evacuation)",
            risk_score=72.0,
            risk_level="High"
        )
        db.add(hh)
        db.commit()

        # Retrieve and verify
        retrieved = db.query(HouseholdModel).filter(HouseholdModel.household_id == test_hh_id).first()
        assert retrieved is not None
        assert retrieved.district == "Chamoli"
        assert retrieved.population == 5
        assert retrieved.to_dict()["vulnerability_level"] == "High"
        print(f"[PASS] HouseholdModel CRUD verified for ID: {retrieved.household_id}")

        # Cleanup
        db.delete(retrieved)
        db.commit()
    finally:
        db.close()


def test_relocation_center_model_crud():
    """Verify inserting and reading a RelocationCenterModel record."""
    db = SessionLocal()
    test_rc_id = "TEST_RC_001"
    try:
        # Clean existing test record if any
        existing = db.query(RelocationCenterModel).filter(RelocationCenterModel.center_id == test_rc_id).first()
        if existing:
            db.delete(existing)
            db.commit()

        # Insert test shelter
        rc = RelocationCenterModel(
            center_id=test_rc_id,
            name="Joshimath Primary School Relief Shelter",
            state="Uttarakhand",
            district="Chamoli",
            village="Joshimath",
            latitude=30.559,
            longitude=79.562,
            total_capacity=150,
            current_occupancy=45,
            medical_support=True,
            food_available=True,
            water_available=True,
            sanitation_available=True,
            accessible_for_disabled=True,
            active=True
        )
        db.add(rc)
        db.commit()

        # Retrieve and verify
        retrieved = db.query(RelocationCenterModel).filter(RelocationCenterModel.center_id == test_rc_id).first()
        assert retrieved is not None
        assert retrieved.total_capacity == 150
        data_dict = retrieved.to_dict()
        assert data_dict["available_capacity"] == 105
        print(f"[PASS] RelocationCenterModel CRUD verified for ID: {retrieved.center_id} (Available: {data_dict['available_capacity']})")

        # Cleanup
        db.delete(retrieved)
        db.commit()
    finally:
        db.close()


def test_get_db_generator():
    """Verify that get_db generator yields an active session and closes it."""
    gen = get_db()
    session = next(gen)
    assert session.is_active
    try:
        next(gen)
    except StopIteration:
        pass
    print("[PASS] FastAPI get_db() dependency session lifecycle verified")


if __name__ == "__main__":
    print("==================================================")
    print("  RUNNING STEP 1 DATABASE VERIFICATION TESTS")
    print("==================================================")
    test_database_engine_and_file()
    test_tables_exist()
    test_get_db_generator()
    test_household_model_crud()
    test_relocation_center_model_crud()
    print("==================================================")
    print("  ALL STEP 1 TESTS PASSED SUCCESSFULLY! (5/5)")
    print("==================================================")
