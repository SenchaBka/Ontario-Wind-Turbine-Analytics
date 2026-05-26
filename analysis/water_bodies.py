import os
import geopandas as gpd

BASE = os.path.dirname(__file__)
INPUT  = os.path.join(BASE, "data", "Ontario_Hydro_Network_(OHN)_-_Waterbody",
                       "Ontario_Hydro_Network_(OHN)_-_Waterbody.shp")
OUTPUT = os.path.join(BASE, "results", "lakes.geojson")

# Lakes smaller than this are skipped entirely during reading (10 km²)
MIN_AREA_M2 = 10_000_000

# ── Filter to large lakes only while streaming (avoids loading 5.8 GB into memory) ─
print("Reading lakes from OHN Waterbody (5.8 GB file — this will take a few minutes)...")
gdf = gpd.read_file(INPUT, where=f"WATERBODY_ = 'Lake' AND SYSTEM_CAL >= {MIN_AREA_M2}")
print(f"✓ {len(gdf)} lakes loaded")

# ── Keep only the columns needed for the website ──────────────────────────────
gdf = gdf[["OGF_ID", "OFFICIAL_N", "SYSTEM_CAL", "geometry"]].rename(columns={
    "OGF_ID":     "id",
    "OFFICIAL_N": "name",
    "SYSTEM_CAL": "area_m2",
})

# ── Simplify boundaries for web display (~100 m tolerance) ────────────────────
print("Simplifying geometries...")
gdf["geometry"] = gdf.geometry.simplify(0.001, preserve_topology=True)
gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

# ── Save ──────────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
gdf.to_file(OUTPUT, driver="GeoJSON")

size_mb = os.path.getsize(OUTPUT) / 1_000_000
print(f"✓ Saved {len(gdf)} lakes → {OUTPUT}  ({size_mb:.1f} MB)")
