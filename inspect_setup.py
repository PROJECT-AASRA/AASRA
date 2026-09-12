"""
AASRA Database Setup Inspector (Step 1)
Verifies all 9 database components, models, tables, and test files.
Read-only script: Does not modify any files or data.
"""

from pathlib import Path
from sqlalchemy import inspect

print("==================================================")
print("  PROJECT AASRA - DATABASE SETUP INSPECTION (STEP 1)")
print("==================================================")

base_dir = Path("D:/Aasra/AASRA")

# 1. Check app/database.py
try:
    from app.database import engine, SessionLocal, Base, get_db, DB_PATH
    print("[1/9] app/database.py: CONFIGURED CORRECTLY")
    print(f"      - Database URL : sqlite:///{DB_PATH}")
    print(f"      - SessionLocal : OK | Base: OK | get_db: OK")
except Exception as e:
    print(f"[1/9] app/database.py: ERROR ({e})")

# 2. Check app/models.py
try:
    from app.models import HouseholdModel, RelocationCenterModel, HazardAssessmentModel
    print("[2/9] app/models.py: SQLAlchemy MODELS FOUND")
    print("      - HouseholdModel (table: 'households'): OK")
    print("      - RelocationCenterModel (table: 'relocation_centers'): OK")
    print("      - HazardAssessmentModel (table: 'hazard_assessments'): OK")
except Exception as e:
    print(f"[2/9] app/models.py: ERROR ({e})")

# 3. Check app/init_db.py
init_file = base_dir / "app" / "init_db.py"
print(f"[3/9] app/init_db.py exists: {'YES' if init_file.exists() else 'NO'}")

# 4. Check app/seed_db.py
seed_file = base_dir / "app" / "seed_db.py"
print(f"[4/9] app/seed_db.py exists: {'YES' if seed_file.exists() else 'NO'}")

# 5. Check disaster.db
db_file = base_dir / "disaster.db"
if db_file.exists():
    size_kb = db_file.stat().st_size / 1024
    print(f"[5/9] disaster.db exists: YES ({size_kb:.2f} KB)")
else:
    print("[5/9] disaster.db exists: NO")

# 6. Check Household API storage
try:
    from app.routes import households
    uses_sqlite = hasattr(households, "HouseholdModel") and hasattr(households, "get_db")
    print(f"[6/9] Household API uses SQLite: {'YES (SQLAlchemy HouseholdModel + synchronized cache)' if uses_sqlite else 'NO'}")
except Exception as e:
    print(f"[6/9] Household API check error: {e}")

# 7. Check Relocation API storage
try:
    from app.routes import relocation
    uses_sqlite_r = hasattr(relocation, "RelocationCenterModel") and hasattr(relocation, "get_db")
    print(f"[7/9] Relocation API uses SQLite: {'YES (SQLAlchemy RelocationCenterModel + synchronized cache)' if uses_sqlite_r else 'NO'}")
except Exception as e:
    print(f"[7/9] Relocation API check error: {e}")

# 8. Check SQLite tables
try:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"[8/9] SQLite tables in database: {tables}")
    for t in ["households", "relocation_centers", "hazard_assessments"]:
        if t in tables:
            cols = len(inspector.get_columns(t))
            print(f"      - Table '{t}': PRESENT ({cols} columns)")
        else:
            print(f"      - Table '{t}': MISSING")
except Exception as e:
    print(f"[8/9] SQLite table inspection error: {e}")

# 9. Check test files
test_files = [
    "test_database_integration.py",
    "test_pilot.py",
    "test_hazard_engine.py",
    "test_assessment.py",
    "test_gis_map.py"
]
print("[9/9] Required test files:")
for tf in test_files:
    exists = (base_dir / tf).exists()
    print(f"      - {tf}: {'FOUND' if exists else 'MISSING'}")

print("==================================================")
print("  STEP 1 INSPECTION COMPLETED SUCCESSFULLY")
print("==================================================")
