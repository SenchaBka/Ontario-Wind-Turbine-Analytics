import os
import geopandas as gpd
import folium

GDB_PATH      = "analysis/data/ORNELEM_tmp/Non_Sensitive.gdb"
BUILT_UP_PATH = "analysis/data/Built_Up_Area.geojson"
OUT_HTML      = "analysis/results/roads_map.html"

ROAD_CLASSES = ["Freeway", "Expressway / Highway", "Arterial"]

CLASS_STYLES = {
    "Freeway":               {"color": "#1a1a1a", "weight": 1.5, "opacity": 0.9},
    "Expressway / Highway":  {"color": "#3a3a3a", "weight": 1.2, "opacity": 0.85},
    "Arterial":              {"color": "#666666", "weight": 0.8, "opacity": 0.7},
}

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

# ---------------------------------------------------------------------------
# 4. Build map
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
m = folium.Map(location=[51.25, -85.32], zoom_start=6, tiles="CartoDB positron")

for road_class_name, style in CLASS_STYLES.items():
    subset = merged[merged["ROAD_CLASS"] == road_class_name]
    if subset.empty:
        continue
    layer = folium.FeatureGroup(name=road_class_name, show=True).add_to(m)
    folium.GeoJson(
        data=subset[["geometry"]].__geo_interface__,
        style_function=lambda _, s=style: s,
    ).add_to(layer)
    print(f"  Added {len(subset):,} {road_class_name} segments")

legend_html = """
<div style="
    position:fixed; bottom:30px; left:30px; z-index:9999;
    background:rgba(255,255,255,0.92); padding:10px 16px;
    border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.25);
    font-family:sans-serif; font-size:13px;">
  <b>Road Class</b><br>
  <span style="color:#1a1a1a">&#9473;</span> Freeway<br>
  <span style="color:#3a3a3a">&#9473;</span> Expressway / Highway<br>
  <span style="color:#666666">&#9473;</span> Arterial (rural only)<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl(collapsed=False).add_to(m)

m.save(OUT_HTML)
print(f"\nMap saved → {OUT_HTML}")
