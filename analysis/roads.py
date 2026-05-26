import os
import json
import geopandas as gpd
import folium
from shapely.ops import unary_union

GDB_PATH       = "analysis/data/ORNELEM_tmp/Non_Sensitive.gdb"
OUT_HTML       = "analysis/results/roads_map.html"
OUT_ZONES_JSON = "analysis/results/road_zones.geojson"

# ---------------------------------------------------------------------------
# Suitability rings — drawn largest first so smaller sit on top
# (radius_m, label, colour)
# ---------------------------------------------------------------------------
RINGS = [
    (5000, "Poor (2–5 km)",         "#d7191c"),
    (2000, "Moderate (500 m–2 km)", "#fdae61"),
    (500,  "Excellent (60–100 m)",  "#ffffbf"),
    (60,   "No Build (< 60 m)",     "#333333"),
]

# ---------------------------------------------------------------------------
# 1. Load & summarise
# ---------------------------------------------------------------------------
print("Loading road network (583 K segments — takes ~30 s)…")
roads = gpd.read_file(GDB_PATH, layer="ORN_ROAD_NET_ELEMENT")

print(f"\n=== Ontario Road Network ===")
print(f"Total segments : {len(roads):,}")
print(f"CRS            : {roads.crs}")
bounds = roads.total_bounds
print(f"Bounding box   : lon {bounds[0]:.3f}→{bounds[2]:.3f}  lat {bounds[1]:.3f}→{bounds[3]:.3f}")

# ---------------------------------------------------------------------------
# 2. Project + simplify + union into one geometry
#    (union first → buffer once per ring → much faster than per-segment buffer)
# ---------------------------------------------------------------------------
print("\nProjecting to EPSG:3347 and simplifying (100 m tolerance)…")
roads_proj = roads[["geometry"]].to_crs(epsg=3347)
roads_proj["geometry"] = roads_proj.geometry.simplify(100, preserve_topology=False)
roads_proj = roads_proj[~roads_proj.geometry.is_empty]

print("Unioning all road geometries (slow step — ~1–2 min)…")
roads_union = unary_union(roads_proj.geometry.values)
print("Union done.")

# ---------------------------------------------------------------------------
# 3. Buffer each ring and collect into one GeoDataFrame
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)

zone_parts = []
for radius_m, label, colour in RINGS:
    print(f"  Buffering {label} ({radius_m} m)…")
    zone_geom = roads_union.buffer(radius_m)
    zone_gdf  = gpd.GeoDataFrame(
        {"label": [label], "colour": [colour]},
        geometry=[zone_geom],
        crs="EPSG:3347",
    ).to_crs(epsg=4326)
    zone_parts.append(zone_gdf)

import pandas as pd
zones = gpd.GeoDataFrame(pd.concat(zone_parts, ignore_index=True), crs="EPSG:4326")

# Simplify output polygons to reduce file size
zones["geometry"] = zones.geometry.simplify(0.001, preserve_topology=True)
zones.to_file(OUT_ZONES_JSON, driver="GeoJSON")
print(f"\nZones saved → {OUT_ZONES_JSON}")

# ---------------------------------------------------------------------------
# 4. Build map — zones only, no raw road lines
# ---------------------------------------------------------------------------
m = folium.Map(location=[51.25, -85.32], zoom_start=6, tiles="CartoDB positron")

with open(OUT_ZONES_JSON) as f:
    zones_geojson = json.load(f)

for (_, label, colour), feature in zip(RINGS, zones_geojson["features"]):
    layer = folium.FeatureGroup(name=label, show=True).add_to(m)
    folium.GeoJson(
        data=feature,
        style_function=lambda _, c=colour: {
            "color":       c,
            "weight":      1,
            "fillColor":   c,
            "fillOpacity": 0.2,
        },
    ).add_to(layer)

legend_html = """
<div style="
    position:fixed; bottom:30px; left:30px; z-index:9999;
    background:rgba(255,255,255,0.92); padding:10px 16px;
    border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.25);
    font-family:sans-serif; font-size:13px;">
  <b>Distance to Nearest Road</b><br>
  <span style="color:#333333">&#9679;</span> No Build (&lt; 60 m)<br>
  <span style="color:#ffffbf; -webkit-text-stroke:1px #aaa">&#9679;</span> Excellent (60–100 m)<br>
  <span style="color:#1a9641">&#9679;</span> Good (100–500 m)<br>
  <span style="color:#fdae61">&#9679;</span> Moderate (500 m–2 km)<br>
  <span style="color:#d7191c">&#9679;</span> Poor (2–5 km)<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl(collapsed=False).add_to(m)

m.save(OUT_HTML)
print(f"Map saved → {OUT_HTML}")

m.save(OUT_HTML)
print(f"\nMap saved → {OUT_HTML}")
