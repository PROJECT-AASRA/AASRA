"""
Project AASRA - Comprehensive Live REST API & Database Persistence Verification Script
Tests 20 live API endpoints and verifies SQLite table persistence directly.
"""
import urllib.request
import json
import sqlite3
import sys

BASE_URL = "http://127.0.0.1:8000"

ENDPOINTS = [
    ("/", "Root Information Endpoint"),
    ("/health", "Health Check"),
    ("/states", "States Pilot Directory"),
    ("/households?limit=5", "List Households (SQLite Backed)"),
    ("/households/HH-UK-001", "Get Household by ID"),
    ("/households/HH-UK-001/vulnerability", "Household Vulnerability Score"),
    ("/relocation/?limit=5", "List Relocation Shelters (SQLite Backed)"),
    ("/relocation/SHELTER-UK-001", "Get Shelter by ID"),
    ("/relocation/recommend/HH-UK-001", "Shelter Recommendation Engine"),
    ("/hazards/household/HH-UK-001/multi", "Multi-Hazard Household Evaluation"),
    ("/hazards/exposure/point?latitude=30.556&longitude=79.563&district=Chamoli", "Hazard Exposure Point Evaluation"),
    ("/hazards/districts", "Districts Hazard Rankings"),
    ("/assessment/household/HH-UK-001", "Disaster Assessment Evaluation & Cache"),
    ("/assessment/high-risk?state=Uttarakhand&limit=5", "High-Risk Prioritization Queue"),
    ("/assessment/state/Uttarakhand", "Statewide Assessment Aggregation"),
    ("/gis/shelters", "GIS Shelters GeoJSON"),
    ("/gis/households", "GIS Households GeoJSON"),
    ("/gis/flood-zones", "GIS Flood Zones GeoJSON"),
    ("/gis/rivers", "GIS Rivers GeoJSON"),
    ("/gis/landslides", "GIS Landslides GeoJSON"),
    ("/map", "Interactive Leaflet GIS Map HTML")
]

def test_live_apis():
    print("=" * 80)
    print("  PROJECT AASRA - LIVE REST API ENDPOINT VERIFICATION")
    print("=" * 80)
    print(f"{'ENDPOINT':<55} | {'STATUS':<10} | {'RESPONSE TYPE'}")
    print("-" * 80)

    passed = 0
    for ep, name in ENDPOINTS:
        url = f"{BASE_URL}{ep}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                code = resp.getcode()
                ctype = resp.headers.get("Content-Type", "")
                if "json" in ctype:
                    data = json.loads(resp.read().decode())
                    detail = f"JSON ({len(data)} items)" if isinstance(data, (list, dict)) else "JSON"
                else:
                    body = resp.read().decode()
                    detail = f"HTML ({len(body)} chars)"
                print(f"{ep:<55} | HTTP {code:<5} | {detail}")
                passed += 1
        except Exception as e:
            print(f"{ep:<55} | FAILED     | {e}")

    print("=" * 80)
    print(f"RESULT: {passed}/{len(ENDPOINTS)} LIVE ENDPOINTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    return passed == len(ENDPOINTS)


def test_sqlite_persistence():
    print("\n" + "=" * 80)
    print("  PROJECT AASRA - SQLITE DATABASE PERSISTENCE VERIFICATION")
    print("=" * 80)
    
    conn = sqlite3.connect("disaster.db")
    c = conn.cursor()

    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    print(f"Database File: disaster.db")
    print(f"Tables Found: {tables}")

    expected_tables = ["households", "relocation_centers", "hazard_assessments"]
    all_ok = True

    for tbl in expected_tables:
        if tbl in tables:
            cnt = c.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]
            cols = [col[1] for col in c.execute(f"PRAGMA table_info({tbl})").fetchall()]
            print(f"\n[PASS] Table '{tbl}':")
            print(f"       Total Records: {cnt}")
            print(f"       Column Count : {len(cols)}")
            sample = c.execute(f"SELECT * FROM {tbl} LIMIT 1").fetchone()
            if sample:
                print(f"       Sample Primary Key: {sample[0]}")
        else:
            print(f"\n[FAIL] Table '{tbl}' does NOT exist!")
            all_ok = False

    conn.close()
    print("=" * 80)
    print("SQLITE PERSISTENCE CHECK COMPLETED SUCCESSFULLY.")
    print("=" * 80)
    return all_ok


if __name__ == "__main__":
    api_ok = test_live_apis()
    db_ok = test_sqlite_persistence()
    if api_ok and db_ok:
        sys.exit(0)
    else:
        sys.exit(1)
