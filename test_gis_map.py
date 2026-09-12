"""
Automated Test Suite for Project AASRA - GIS Map Visualization Layer
Verifies:
1. Web Map Endpoint (/map) serving responsive HTML Leaflet client
2. GeoJSON Vector Layers:
   - District Boundaries (/gis/districts)
   - Historical Flood Polygons (/gis/flood-zones)
   - River Networks (/gis/rivers)
   - GSI Landslides (/gis/landslides)
   - Earthquakes (/gis/earthquakes)
   - Rainfall Stations (/gis/rainfall)
3. Household Risk Marker Attributes (RED, ORANGE, YELLOW, GREEN)
4. Relocation Shelter Attributes & Capacity Matching
5. Evacuation Transit Routing (/relocation/recommend/{household_id})
6. Multi-State Filtering (Uttarakhand, Assam, Odisha)
"""

import json
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def test_map_page():
    print("\n--- TEST 1: GIS Map HTML Page Delivery ---")
    req = urllib.request.urlopen(f"{BASE_URL}/map")
    assert req.getcode() == 200
    html_content = req.read().decode("utf-8")
    assert "leaflet.js" in html_content
    assert "leaflet.css" in html_content
    assert "PROJECT AASRA" in html_content
    assert "flyTo" in html_content or "switchState" in html_content
    print("[PASS] Interactive Leaflet GIS HTML client served successfully at /map.")


def test_geojson_hazard_layers():
    print("\n--- TEST 2: Real GeoJSON Hazard & Boundary Layers ---")

    layers = [
        ("/gis/state-boundary", "State Boundary Outline", 1),
        ("/gis/districts", "District Boundaries", 1),
        ("/gis/flood-zones", "Historical Flood Polygons", 1),
        ("/gis/rivers", "River Networks", 1),
        ("/gis/landslides?limit=100", "GSI Landslide Points", 1),
        ("/gis/earthquakes", "Earthquake Epicenters", 1),
        ("/gis/rainfall", "Rainfall Monitoring Stations", 1),
    ]

    for endpoint, name, min_features in layers:
        req = urllib.request.urlopen(f"{BASE_URL}{endpoint}")
        assert req.getcode() == 200
        data = json.loads(req.read().decode("utf-8"))
        assert data.get("type") == "FeatureCollection"
        features = data.get("features", [])
        assert len(features) >= min_features
        print(f"[PASS] {name:<32}: {len(features):>4} GeoJSON features loaded.")


def test_households_risk_visualization():
    print("\n--- TEST 3: Household Risk Visualization ---")
    req = urllib.request.urlopen(f"{BASE_URL}/gis/households?state=Uttarakhand")
    assert req.getcode() == 200
    data = json.loads(req.read().decode("utf-8"))
    features = data["features"]
    assert len(features) > 0

    risk_colors = set(f["properties"]["marker_color"] for f in features)
    # Ensure standard AASRA risk colors are present (e.g. Red, Orange, Yellow)
    assert any(c in risk_colors for c in ["#d32f2f", "#f57c00", "#fbc02d", "#388e3c"])

    sample = features[0]["properties"]
    assert "household_id" in sample
    assert "risk_score" in sample
    assert "risk_level" in sample
    assert "vulnerability_score" in sample
    assert "vulnerability_level" in sample
    assert "priority_level" in sample
    assert "relocation_required" in sample
    print(f"[PASS] {len(features)} households indexed with risk levels & vulnerability attributes.")
    print(f"       Sample {sample['household_id']}: Risk={sample['risk_score']} ({sample['risk_level']}), Color={sample['marker_color']}, Evac={sample['relocation_required']}")


def test_shelters_layer():
    print("\n--- TEST 4: Relocation Shelters Layer ---")
    req = urllib.request.urlopen(f"{BASE_URL}/gis/shelters?state=Uttarakhand")
    assert req.getcode() == 200
    data = json.loads(req.read().decode("utf-8"))
    features = data["features"]
    assert len(features) > 0

    sample = features[0]["properties"]
    assert "center_id" in sample
    assert "name" in sample
    assert "total_capacity" in sample
    assert "available_capacity" in sample
    assert "medical_support" in sample
    assert "accessible_for_disabled" in sample
    print(f"[PASS] {len(features)} operational shelters indexed with capacities and facility amenities.")
    print(f"       Sample {sample['center_id']}: {sample['name']} (Available: {sample['available_capacity']}/{sample['total_capacity']})")


def test_evacuation_recommendation_and_routing():
    print("\n--- TEST 5: Evacuation Routing API (Household -> Shelter) ---")
    req = urllib.request.urlopen(f"{BASE_URL}/relocation/recommend/HH-UK-001")
    assert req.getcode() == 200
    data = json.loads(req.read().decode("utf-8"))

    assert data["household_id"] == "HH-UK-001"
    assert len(data["recommended_centers"]) > 0
    top = data["recommended_centers"][0]
    assert "distance_km" in top
    assert "available_capacity" in top
    assert "suitability" in top
    print(f"[PASS] Recommendation route calculated: HH-UK-001 -> {top['name']}")
    print(f"       Distance: {top['distance_km']} km | Available Capacity: {top['available_capacity']} | Suitability: {top['suitability']}")


def test_multi_state_support():
    print("\n--- TEST 6: Multi-State GIS Filtering ---")
    for st in ["Uttarakhand", "Assam", "Odisha"]:
        req_hh = urllib.request.urlopen(f"{BASE_URL}/gis/households?state={st}")
        assert req_hh.getcode() == 200
        hh_count = len(json.loads(req_hh.read().decode("utf-8"))["features"])

        req_sh = urllib.request.urlopen(f"{BASE_URL}/gis/shelters?state={st}")
        assert req_sh.getcode() == 200
        sh_count = len(json.loads(req_sh.read().decode("utf-8"))["features"])

        print(f"[PASS] State {st:<12}: {hh_count:>2} Households, {sh_count:>3} Shelters loaded.")


if __name__ == "__main__":
    test_map_page()
    test_geojson_hazard_layers()
    test_households_risk_visualization()
    test_shelters_layer()
    test_evacuation_recommendation_and_routing()
    test_multi_state_support()
    print("\n========================================================")
    print("ALL 6 GIS MAP VISUALIZATION TESTS PASSED SUCCESSFULLY!")
    print("========================================================\n")
