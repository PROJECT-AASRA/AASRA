"""
Comprehensive verification test script for Project AASRA (Uttarakhand Pilot).
Tests:
1. Root & Health
2. Regional Telemetry & Uttarakhand Intelligence
3. Geospatial Engine (Point-in-Polygon flood check, river distance, hospital distance)
4. Hazard Engine Endpoints (Point lookup, household exposure)
5. Household Demographic & Spatial Registry
6. Shelter Management & Personalized Allocation Engine
7. GIS Map Endpoints (GeoJSON FeatureCollections)
8. Upcoming Pilot Stubs (Assam & Odisha)
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.main import root, health, states
from app.routers.uttarakhand import (
    uttarakhand,
    uttarakhand_summary,
    uttarakhand_hazards,
    uttarakhand_risk,
    uttarakhand_districts
)
from app.routers.assam import assam
from app.routers.odisha import odisha
from app.routes.households import list_households, get_households_by_district, HOUSEHOLDS_DB
from app.routes.relocation import list_relocation_centers, recommend_shelters_for_household, SHELTERS_DB
from app.routes.hazards import get_point_hazard_exposure, get_household_hazard_exposure, list_district_hazards
from app.routes.gis import get_shelters_geojson, get_households_geojson, get_historical_flood_zones, get_emergency_services_geojson


def run_all_tests():
    print("==================================================")
    print("RUNNING COMPLETE AASRA GEOSPATIAL & HAZARD VERIFICATION")
    print("==================================================")

    # 1. Main endpoints
    print("\n[1] Testing Main / Root Endpoints:")
    r_root = root()
    print("  Root message:", r_root["message"])
    print("  Active pilot:", r_root["active_pilot"])
    print("  Pilot stats:", r_root["pilot_stats"])
    assert r_root["active_pilot"] == "Uttarakhand"

    # 2. Uttarakhand Router
    print("\n[2] Testing Uttarakhand Regional Intelligence:")
    r_summary = uttarakhand_summary()
    print(f"  Shelters ready: {r_summary['total_shelters_loaded']}")
    print(f"  Total capacity: {r_summary['total_shelter_capacity']:,} people")
    assert r_summary["total_shelters_loaded"] >= 256

    r_hazards = uttarakhand_hazards()
    print(f"  Telemetry summary: {r_hazards['telemetry_summary']}")
    assert r_hazards["telemetry_summary"]["historical_recorded_disasters"] > 3000

    # 3. Geospatial Engine Analysis
    print("\n[3] Testing Real Geospatial Processing Engine:")
    # Joshimath coordinates
    point_eval = get_point_hazard_exposure(latitude=30.556, longitude=79.563, district="Chamoli")
    print("  Point Evaluation (Joshimath: 30.556°N, 79.563°E):")
    print(f"    In Historical Flood Polygon: {point_eval['in_historical_flood_zone']}")
    print(f"    Distance to Nearest River: {point_eval['distance_to_nearest_river_km']} km")
    print(f"    Distance to Hospital: {point_eval['distance_to_nearest_hospital_km']} km ({point_eval['nearest_hospital_name']})")
    print(f"    Composite Geospatial Exposure: {point_eval['composite_geospatial_hazard_exposure']} ({point_eval['geospatial_hazard_tier']})")
    assert point_eval["in_historical_flood_zone"] is True
    assert point_eval["distance_to_nearest_river_km"] < 5.0
    assert point_eval["distance_to_nearest_hospital_km"] < 5.0

    # 4. Household Geospatial Integration
    print("\n[4] Testing Household + Spatial Hazard Integration:")
    hh_eval = get_household_hazard_exposure("HH-UK-001")
    print(f"  Household: {hh_eval['household_id']} in {hh_eval['village']}, {hh_eval['district']}")
    print(f"    In Flood Zone: {hh_eval['geospatial_assessment']['in_historical_flood_zone']}")
    print(f"    Nearest River: {hh_eval['geospatial_assessment']['distance_to_nearest_river_km']} km")
    print(f"    Nearest Medical: {hh_eval['geospatial_assessment']['nearest_hospital_name']}")
    print(f"    Vulnerability Level: {hh_eval['vulnerability_level']} | Priority: {hh_eval['priority_level']}")

    # 5. Households Demographic Registry
    print("\n[5] Testing Households Demographic Registry:")
    all_hh = list_households(limit=5)
    print(f"  Sample households retrieved: {len(all_hh)} (Total registered: {len(HOUSEHOLDS_DB)})")
    h0 = all_hh[0]
    print(f"  Household {h0['household_id']}: River Distance={h0.get('distance_to_nearest_river_km')} km, Hospital={h0.get('nearest_hospital')}")

    # 6. Shelters & Personalized Recommendations
    print("\n[6] Testing Relocation Shelter Recommendation Engine:")
    recom = recommend_shelters_for_household("HH-UK-001")
    print(f"  Personalized Recommendations for HH-UK-001 ({recom['priority_level']} Priority):")
    for i, rec in enumerate(recom["recommended_centers"][:3], 1):
        print(f"    #{i} {rec['center_id']}: {rec['name']} | Distance: {rec['distance_km']} km | Suitability: {rec['suitability']}")
    assert len(recom["recommended_centers"]) > 0

    # 7. GIS Map Endpoints
    print("\n[7] Testing GIS Map Layers (GeoJSON):")
    sh_geojson = get_shelters_geojson()
    print(f"  Shelters GeoJSON features: {len(sh_geojson['features'])} ({sh_geojson['type']})")
    assert sh_geojson["type"] == "FeatureCollection"
    assert len(sh_geojson["features"]) >= 256

    hh_geojson = get_households_geojson()
    print(f"  Households GeoJSON features: {len(hh_geojson['features'])} ({hh_geojson['type']})")
    assert hh_geojson["type"] == "FeatureCollection"

    flood_geojson = get_historical_flood_zones()
    print(f"  Historical Flood Polygons: {len(flood_geojson.get('features', []))} ({flood_geojson.get('type')})")
    assert len(flood_geojson.get("features", [])) > 0

    med_geojson = get_emergency_services_geojson(service_type="healthcare")
    print(f"  Emergency Healthcare points: {len(med_geojson['features'])}")
    assert len(med_geojson["features"]) > 0

    # 8. Pending pilots
    print("\n[8] Testing Assam & Odisha Phase 2 Pending Status:")
    assert assam()["status"] == "PILOT_PENDING_PHASE_2"
    assert odisha()["status"] == "PILOT_PENDING_PHASE_2"
    print("  Assam & Odisha gracefully configured as upcoming pilots.")

    print("\n==================================================")
    print("[SUCCESS] ALL 8 MODULES PASSED WITH REAL DATA & GIS!")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()
