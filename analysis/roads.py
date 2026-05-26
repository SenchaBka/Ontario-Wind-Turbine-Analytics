import os
import geopandas as gpd

GDB_PATH       = "analysis/data/ORNELEM_tmp/Non_Sensitive.gdb"
BUILT_UP_PATH  = "analysis/data/Built_Up_Area.geojson"
OUT_GEOJSON    = "analysis/api/roads.geojson"
OUT_HTML       = "analysis/results/roads_map.html"

ROAD_CLASSES = ["Freeway", "Expressway / Highway", "Arterial"]

# ---------------------------------------------------------------------------
# 1. Load classification table and keep only highway / arterial rows
# ---------------------------------------------------------------------------
print("Loading road class table…")
road_class = gpd.read_file(
    GDB_PATH,
    layer="ORN_ROAD_CLASS",
    columns=["ORN_ROAD_NET_ELEMENT_ID", "ROAD_CLASS"],
)
road_class = road_class[road_class["ROAD_CLASS"].isin(ROAD_CLASSES)].copy()
print(f"Matching segments in class table: {len(road_class):,}")

# ---------------------------------------------------------------------------
# 2. Load geometry and join road class
# ---------------------------------------------------------------------------
print("Loading road geometries…")
roads = gpd.read_file(GDB_PATH, layer="ORN_ROAD_NET_ELEMENT", columns=["OGF_ID"])

roads["OGF_ID"] = roads["OGF_ID"].astype(float)
road_class["ORN_ROAD_NET_ELEMENT_ID"] = road_class["ORN_ROAD_NET_ELEMENT_ID"].astype(float)

merged = roads.merge(
    road_class[["ORN_ROAD_NET_ELEMENT_ID", "ROAD_CLASS"]],
    left_on="OGF_ID",
    right_on="ORN_ROAD_NET_ELEMENT_ID",
    how="inner",
).to_crs(epsg=4326)
print(f"Roads after join: {len(merged):,}")

# ---------------------------------------------------------------------------
# 3. Remove arterial roads inside built-up (urban) areas
# ---------------------------------------------------------------------------
print("Loading built-up areas to filter urban arterials…")
built_up = gpd.read_file(BUILT_UP_PATH)[["geometry"]].to_crs(epsg=4326)
built_up_union = built_up.geometry.union_all()

arterial_mask = merged["ROAD_CLASS"] == "Arterial"
arterials = merged[arterial_mask].copy()
others    = merged[~arterial_mask].copy()

# Keep only arterials whose centroid falls outside built-up areas
arterials_outside = arterials[~arterials.geometry.centroid.within(built_up_union)]
print(f"  Arterials kept (rural only): {len(arterials_outside):,} / {len(arterials):,}")

merged = gpd.GeoDataFrame(
    gpd.pd.concat([others, arterials_outside], ignore_index=True),
    crs="EPSG:4326",
)

# Keep only road_class property for frontend
merged = merged[["geometry", "ROAD_CLASS"]].rename(columns={"ROAD_CLASS": "road_class"})

# ---------------------------------------------------------------------------
# 4. Save GeoJSON for backend/frontend
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(OUT_GEOJSON), exist_ok=True)
merged.to_file(OUT_GEOJSON, driver="GeoJSON")
print(f"\nGeoJSON saved → {OUT_GEOJSON}")
