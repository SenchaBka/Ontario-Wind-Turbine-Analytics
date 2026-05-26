import os
import pandas as pd
import geopandas as gpd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
UTILITY_PATH         = "analysis/data/Utility_Site.geojson"
LINE_PATH            = "analysis/data/Utility_Line.geojson"
OUT_STATIONS_JSON    = "analysis/results/hydro_stations.geojson"
OUT_STATION_ZONES    = "analysis/results/hydro_station_zones.geojson"
OUT_LINES_JSON       = "analysis/results/hydro_lines.geojson"
OUT_LINE_ZONES       = "analysis/results/hydro_line_zones.geojson"

# ---------------------------------------------------------------------------
# Suitability rings for hydro stations (radius_km, la
# Colors are defined in frontend/index.html
# ---------------------------------------------------------------------------
RINGS = [
    (50, "Poor (25–50 km)"),
    (25, "Moderate (10–25 km)"),
    (10, "Good (5–10 km)"),
    (5,  "Excellent (< 5 km)"),
]

# ---------------------------------------------------------------------------
# Suitability rings for hydro lines (radius_km, label)
# Colors are defined in frontend/index.html
# ---------------------------------------------------------------------------
LINE_RINGS = [
    (30, "Line: Poor (15–30 km)"),
    (15, "Line: Moderate (5–15 km)"),
    (5,  "Line: Good (1–5 km)"),
    (1,  "Line: Excellent (< 1 km)"),
]

# ---------------------------------------------------------------------------
# Line type filter (just the types, colors in frontend)
# ---------------------------------------------------------------------------
LINE_TYPES = [
    "Hydro Line",
    "Unknown Transmission Line",
    "Submerged Hydro Line",
]

# ---------------------------------------------------------------------------
# 1. Load utility sites & filter hydro stations
# ---------------------------------------------------------------------------
utility = gpd.read_file(UTILITY_PATH)

print("=== Utility sites by CLASS_SUBTYPE ===")
print(utility["CLASS_SUBTYPE"].value_counts().to_string())
print(f"\nTotal utility sites: {len(utility)}\n")

hydro   = utility[utility["CLASS_SUBTYPE"] == "Hydro Station"].copy()
hydro_wgs = hydro.to_crs(epsg=4326)
hydro_proj = hydro.to_crs(epsg=3347)   # Canada Albers — metres, for accurate buffering
print(f"Hydro stations selected: {len(hydro_wgs)}")

# ---------------------------------------------------------------------------
# 2. Load utility lines & filter
# ---------------------------------------------------------------------------
lines = gpd.read_file(LINE_PATH)

print("\n=== Utility lines by CLASS_SUBTYPE ===")
print(lines["CLASS_SUBTYPE"].value_counts().to_string())
print(f"\nTotal utility lines: {len(lines)}\n")

# ---------------------------------------------------------------------------
# 3. Generate GeoJSON data files for backend
# ---------------------------------------------------------------------------
def compute_zones(gdf_proj, rings):
    """Generate suitability zone polygons. Colors applied in frontend."""
    parts = []
    for radius_km, label in rings:
        buf = gpd.GeoDataFrame(geometry=gdf_proj.geometry.buffer(radius_km * 1000), crs=gdf_proj.crs)
        dis = buf.dissolve().to_crs(epsg=4326)
        dis["label"] = label
        dis["radius_km"] = radius_km
        parts.append(dis)
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs="EPSG:4326")

os.makedirs(os.path.dirname(OUT_STATIONS_JSON), exist_ok=True)

# Save hydro stations
hydro_wgs[["geometry", "GEOG_UNIT_DESCR", "CLASS_SUBTYPE"]].to_file(OUT_STATIONS_JSON, driver="GeoJSON")
print(f"✓ Saved → {OUT_STATIONS_JSON}")

# Save hydro station zones
compute_zones(hydro_proj, RINGS).to_file(OUT_STATION_ZONES, driver="GeoJSON")
print(f"✓ Saved → {OUT_STATION_ZONES}")

# Save hydro lines
hydro_lines_wgs = lines[lines["CLASS_SUBTYPE"].isin(LINE_TYPES)][["geometry", "CLASS_SUBTYPE", "GEOG_UNIT_DESCR"]]
hydro_lines_wgs.to_file(OUT_LINES_JSON, driver="GeoJSON")
print(f"✓ Saved → {OUT_LINES_JSON}")

# Save hydro line zones
compute_zones(lines[lines["CLASS_SUBTYPE"].isin(LINE_TYPES)].to_crs(epsg=3347), LINE_RINGS).to_file(OUT_LINE_ZONES, driver="GeoJSON")
print(f"✓ Saved → {OUT_LINE_ZONES}")

print("\n" + "="*60)
print(f"Generated {len(hydro_wgs)} hydro stations")
print(f"Generated {len(hydro_lines_wgs)} hydro lines")
print("All GeoJSON files ready for backend/frontend")
print("="*60)
