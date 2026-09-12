"""
Database Initialization and Schema Verification Script for Project AASRA.
Creates tables in SQLite (disaster.db) if they do not already exist.
Ensures zero data loss (tables are never dropped or wiped).
"""

import sys
from pathlib import Path
from sqlalchemy import inspect
from app.database import engine, Base, DB_PATH
from app.models import HouseholdModel, RelocationCenterModel, HazardAssessmentModel


def init_database() -> dict:
    """
    Creates all declared database tables and returns inspection results.
    """
    print("==================================================")
    print("  PROJECT AASRA - DATABASE INITIALIZATION & SCHEMA")
    print("==================================================")
    print(f"Target Database URL : sqlite:///{DB_PATH}")
    print(f"Database File Path  : {DB_PATH.resolve()}")

    # 1. Create tables if they don't already exist
    print("\n[1/3] Creating database tables (safe idempotent creation)...")
    Base.metadata.create_all(bind=engine)
    print("      Table definitions registered with SQLite engine.")

    # 2. Verify file creation on disk
    print("\n[2/3] Verifying SQLite database file on disk...")
    if DB_PATH.exists():
        file_size_kb = DB_PATH.stat().st_size / 1024
        print(f"      SUCCESS: disaster.db exists on disk ({file_size_kb:.2f} KB).")
    else:
        print("      ERROR: disaster.db file was not found!")
        sys.exit(1)

    # 3. Inspect database schema and tables
    print("\n[3/3] Inspecting SQLite database tables & schema...")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"      Discovered tables in database: {tables}")

    required_tables = ["households", "relocation_centers", "hazard_assessments"]
    table_details = {}

    for table_name in required_tables:
        if table_name in tables:
            columns = inspector.get_columns(table_name)
            col_names = [col["name"] for col in columns]
            table_details[table_name] = {
                "status": "EXISTS",
                "column_count": len(columns),
                "columns": col_names
            }
            print(f"      - Table '{table_name}': OK ({len(columns)} columns)")
        else:
            table_details[table_name] = {"status": "MISSING"}
            print(f"      - Table '{table_name}': MISSING!")

    all_present = all(t in tables for t in required_tables)
    print("\n--------------------------------------------------")
    if all_present:
        print("DATABASE SCHEMA VERIFICATION: PASSED (All tables confirmed)")
    else:
        print("DATABASE SCHEMA VERIFICATION: FAILED (Some tables missing)")
    print("==================================================\n")

    return {
        "database_file": str(DB_PATH.resolve()),
        "file_exists": DB_PATH.exists(),
        "tables": table_details,
        "success": all_present
    }


if __name__ == "__main__":
    result = init_database()
    if not result["success"]:
        sys.exit(1)
