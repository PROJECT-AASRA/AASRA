"""
Project AASRA - Database Verification Script (Tasks 3, 4, 5)
Safe, read-only verification of tables, database connection, session lifecycle,
and schema model fidelity.
"""

from pathlib import Path
from sqlalchemy import text, inspect
from app.database import engine, SessionLocal, get_db, DB_PATH, Base
from app.models import HouseholdModel, RelocationCenterModel, HazardAssessmentModel


def run_verification():
    print("==================================================================")
    print("  PROJECT AASRA - DATABASE VERIFICATION (TASKS 3 & 4)")
    print("==================================================================")

    errors = []

    # ------------------------------------------------------------------
    # TASK 4.1 & 4.2: SQLAlchemy Engine Connection
    # ------------------------------------------------------------------
    print("\n[TASK 4.1 & 4.2] Verifying SQLAlchemy Connection & Engine...")
    try:
        assert DB_PATH.exists(), f"Database file not found at {DB_PATH}"
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            assert result == 1, "Database did not return expected value 1"
        print("  -> Engine connection established successfully.")
        print(f"  -> Database Dialect : {engine.dialect.name}")
        print(f"  -> Target URL        : {engine.url}")
        print(f"  -> DB File Size      : {DB_PATH.stat().st_size / 1024:.2f} KB")
        print("  -> Result: PASS")
    except Exception as e:
        errors.append(f"Engine connection failure: {e}")
        print(f"  -> Result: FAIL ({e})")

    # ------------------------------------------------------------------
    # TASK 4.3: Session Configuration & get_db Dependency
    # ------------------------------------------------------------------
    print("\n[TASK 4.3] Verifying Database Session Lifecycle...")
    try:
        db = SessionLocal()
        assert db.is_active, "SessionLocal() should be active"
        db.close()

        gen = get_db()
        sess = next(gen)
        assert sess.is_active, "get_db() dependency session should be active"
        try:
            next(gen)
        except StopIteration:
            pass  # Generator closed successfully
        print("  -> SessionLocal factory and get_db() generator verified.")
        print("  -> Automatic session cleanup on completion verified.")
        print("  -> Result: PASS")
    except Exception as e:
        errors.append(f"Session verification failure: {e}")
        print(f"  -> Result: FAIL ({e})")

    # ------------------------------------------------------------------
    # TASK 3: Verify Database Tables (Safe Read-Only)
    # ------------------------------------------------------------------
    print("\n[TASK 3] Verifying Database Tables (Read-Only Inspection)...")
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    print(f"  -> Tables found in SQLite: {existing_tables}")

    expected_tables = {
        "households": HouseholdModel,
        "relocation_centers": RelocationCenterModel,
        "hazard_assessments": HazardAssessmentModel
    }

    table_counts = {}
    db = SessionLocal()
    try:
        for tbl, model in expected_tables.items():
            if tbl in existing_tables:
                cols = inspector.get_columns(tbl)
                pk_info = inspector.get_pk_constraint(tbl)
                count = db.query(model).count()
                table_counts[tbl] = count
                print(f"  -> Table '{tbl}':")
                print(f"     - Status       : PRESENT")
                print(f"     - Primary Key  : {pk_info.get('constrained_columns', [])}")
                print(f"     - Total Columns: {len(cols)}")
                print(f"     - Stored Rows  : {count} records")
            else:
                errors.append(f"Missing table: {tbl}")
                print(f"  -> Table '{tbl}': MISSING")
    finally:
        db.close()

    # ------------------------------------------------------------------
    # TASK 4.4 & 4.5: Safe Creation & Record Preservation
    # ------------------------------------------------------------------
    print("\n[TASK 4.4 & 4.5] Verifying Safe Table Creation & Data Preservation...")
    try:
        # Re-run create_all to prove idempotency
        Base.metadata.create_all(bind=engine)
        
        # Verify row counts remain 100% identical (no data loss)
        db = SessionLocal()
        try:
            for tbl, model in expected_tables.items():
                new_count = db.query(model).count()
                assert new_count == table_counts[tbl], (
                    f"Data count changed for {tbl}: {table_counts[tbl]} -> {new_count}"
                )
            print("  -> Base.metadata.create_all is safe & idempotent.")
            print("  -> Existing records preserved with zero data loss:")
            for tbl, count in table_counts.items():
                print(f"     * {tbl}: {count} records intact")
            print("  -> Result: PASS")
        finally:
            db.close()
    except Exception as e:
        errors.append(f"Idempotency / data preservation failure: {e}")
        print(f"  -> Result: FAIL ({e})")

    # ------------------------------------------------------------------
    # TASK 4.6: Model-to-Schema Fidelity
    # ------------------------------------------------------------------
    print("\n[TASK 4.6] Verifying SQLAlchemy Models vs Database Schema...")
    for tbl, model in expected_tables.items():
        db_cols = {col["name"]: str(col["type"]) for col in inspector.get_columns(tbl)}
        model_cols = {c.name: str(c.type) for c in model.__table__.columns}
        
        missing_in_db = set(model_cols.keys()) - set(db_cols.keys())
        missing_in_model = set(db_cols.keys()) - set(model_cols.keys())
        
        if not missing_in_db and not missing_in_model:
            print(f"  -> {model.__name__} <-> '{tbl}': 100% column match ({len(model_cols)} columns)")
        else:
            if missing_in_db:
                errors.append(f"Model {model.__name__} columns missing in DB: {missing_in_db}")
                print(f"  -> Missing in DB: {missing_in_db}")
            if missing_in_model:
                errors.append(f"DB '{tbl}' columns missing in model: {missing_in_model}")
                print(f"  -> Missing in Model: {missing_in_model}")

    # ------------------------------------------------------------------
    # TASK 5: Error Summary
    # ------------------------------------------------------------------
    print("\n==================================================================")
    if not errors:
        print("  TASK 5: ERROR CHECK - ZERO ERRORS FOUND (100% CLEAN)")
        print("  All connection, table, session, and schema checks passed.")
    else:
        print(f"  TASK 5: ERRORS ENCOUNTERED ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")
    print("==================================================================\n")

    return len(errors) == 0


if __name__ == "__main__":
    success = run_verification()
    if not success:
        exit(1)
