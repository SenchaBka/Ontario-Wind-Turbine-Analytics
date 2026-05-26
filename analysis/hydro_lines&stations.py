import os
import json
import pandas as pd
import geopandas as gpd
import folium

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
UTILITY_PATH         = "analysis/data/Utility_Site.geojson"
LINE_PATH            = "analysis/data/Utility_Line.geojson"
OUT_HTML             = "analysis/results/hydro_distance_suitability_map.html"
OUT_STATIONS_JSON    = "analysis/results/hydro_stations.geojson"
OUT_STATION_ZONES    = "analysis/results/hydro_station_zones.geojson"
OUT_LINES_JSON       = "analysis/results/hydro_lines.geojson"
OUT_LINE_ZONES       = "analysis/results/hydro_line_zones.geojson"

# ---------------------------------------------------------------------------
# Suitability rings — drawn largest first so smaller ones sit on top
# (radius_km, label, colour)
# ---------------------------------------------------------------------------
RINGS = [
    (50, "Poor (25–50 km)",      "#4A1820"),
    (25, "Moderate (10–25 km)",  "#B92E2C"),
    (10, "Good (5–10 km)",       "#F77B2C"),
    (5,  "Excellent (< 5 km)",   "#6ECE58"),
]

# ---------------------------------------------------------------------------
# 1. Load utility sites & summarise
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
# 1b. Load utility lines & summarise
# ---------------------------------------------------------------------------
lines = gpd.read_file(LINE_PATH)

print("\n=== Utility lines by CLASS_SUBTYPE ===")
print(lines["CLASS_SUBTYPE"].value_counts().to_string())
print(f"\nTotal utility lines: {len(lines)}\n")

# Suitability rings around hydro lines — largest first so smaller sit on top
# (radius_km, label, colour)
LINE_RINGS = [
    (30, "Line: Poor (15–30 km)",      "#4A1820"),
    (15, "Line: Moderate (5–15 km)",   "#B92E2C"),
    (5,  "Line: Good (1–5 km)",        "#F77B2C"),
    (1,  "Line: Excellent (< 1 km)",   "#6ECE58"),
]

# Colour map for line subtypes
LINE_COLOURS = {
    "Hydro Line":                  "#1f78b4",
    "Unknown Transmission Line":   "#a6cee3",
    "Submerged Hydro Line":        "#33a02c",
}

# ---------------------------------------------------------------------------
# 2. Build map
# ---------------------------------------------------------------------------
m = folium.Map(location=[51.25, -85.32], zoom_start=6, tiles="CartoDB positron")

# Draw merged buffer rings (largest first so smaller sit on top)
for radius_km, label, colour in RINGS:
    # Buffer in projected CRS, dissolve overlapping buffers, reproject to WGS84
    buffered = gpd.GeoDataFrame(geometry=hydro_proj.geometry.buffer(radius_km * 1000), crs=hydro_proj.crs)
    dissolved = buffered.dissolve().to_crs(epsg=4326)

    layer = folium.FeatureGroup(name=label, show=True).add_to(m)
    folium.GeoJson(
        data=json.loads(dissolved.to_json()),
        style_function=lambda _, c=colour: {
            "color":       c,
            "weight":      1.5,
            "fillColor":   c,
            "fillOpacity": 0.15,
        },
    ).add_to(layer)

# Suitability buffers around all hydro lines combined (largest first)
hydro_lines = lines[lines["CLASS_SUBTYPE"].isin(LINE_COLOURS.keys())].to_crs(epsg=3347)
for radius_km, label, colour in LINE_RINGS:
    buffered = gpd.GeoDataFrame(geometry=hydro_lines.geometry.buffer(radius_km * 1000), crs=hydro_lines.crs)
    dissolved = buffered.dissolve().to_crs(epsg=4326)
    layer = folium.FeatureGroup(name=label, show=True).add_to(m)
    folium.GeoJson(
        data=json.loads(dissolved.to_json()),
        style_function=lambda _, c=colour: {
            "color":       c,
            "weight":      1.5,
            "fillColor":   c,
            "fillOpacity": 0.15,
        },
    ).add_to(layer)

# Utility lines — one toggleable layer per subtype
for subtype, colour in LINE_COLOURS.items():
    subset = lines[lines["CLASS_SUBTYPE"] == subtype][["geometry", "CLASS_SUBTYPE", "GEOG_UNIT_DESCR"]]
    if subset.empty:
        continue
    geojson_data = json.loads(subset.to_json())
    line_layer = folium.FeatureGroup(name=f"Line: {subtype} ({len(subset)})", show=False).add_to(m)
    folium.GeoJson(
        data=geojson_data,
        style_function=lambda _, c=colour: {
            "color":   c,
            "weight":  1.5,
            "opacity": 0.8,
        },
        tooltip=folium.GeoJsonTooltip(fields=["CLASS_SUBTYPE", "GEOG_UNIT_DESCR"],
                                      aliases=["Type", "Description"]),
    ).add_to(line_layer)

# Hydro station markers on top
hydro_layer = folium.FeatureGroup(name="Hydro Stations", show=True).add_to(m)
for _, row in hydro_wgs.iterrows():
    desc = row.get("GEOG_UNIT_DESCR")
    label = desc if pd.notna(desc) else "Hydro Station"
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=6,
        color="#E04E27",
        fill=True,
        fill_color="#F77B2C",
        fill_opacity=1.0,
        tooltip=label,
        popup=folium.Popup(f"<b>{label}</b>", max_width=200),
    ).add_to(hydro_layer)

# Legend
legend_html = """
<div style="
    position:fixed; bottom:30px; left:30px; z-index:9999;
    background:rgba(255,255,255,0.92); padding:10px 16px;
    border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.25);
    font-family:sans-serif; font-size:13px;">
  <b>Distance to Hydro Station</b><br>
  <span style="color:#1a9641">&#9679;</span> Excellent (&lt; 5 km)<br>
  <span style="color:#ffffbf; -webkit-text-stroke:1px #aaa">&#9679;</span> Good (5–10 km)<br>
  <span style="color:#fdae61">&#9679;</span> Moderate (10–25 km)<br>
  <span style="color:#d7191c">&#9679;</span> Poor (25–50 km)<br>
  <span style="color:#003f88">&#9679;</span> Hydro Station<br>
  <hr style="margin:6px 0">
  <b>Distance to Hydro Line</b><br>
  <span style="color:#1a9641">&#9644;</span> Excellent (&lt; 1 km)<br>
  <span style="color:#ffffbf; -webkit-text-stroke:1px #aaa">&#9644;</span> Good (1–5 km)<br>
  <span style="color:#fdae61">&#9644;</span> Moderate (5–15 km)<br>
  <span style="color:#d7191c">&#9644;</span> Poor (15–30 km)<br>
  <hr style="margin:6px 0">
  <span style="color:#1f78b4">&#9644;</span> Hydro Line<br>
  <span style="color:#a6cee3">&#9644;</span> Unknown Transmission Line<br>
  <span style="color:#33a02c">&#9644;</span> Submerged Hydro Line<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl(collapsed=False).add_to(m)

os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)

# ---------------------------------------------------------------------------
# Save GeoJSON data files for the backend to serve
# ---------------------------------------------------------------------------
def compute_zones(gdf_proj, rings):
    parts = []
    for radius_km, label, colour in rings:
        buf = gpd.GeoDataFrame(geometry=gdf_proj.geometry.buffer(radius_km * 1000), crs=gdf_proj.crs)
        dis = buf.dissolve().to_crs(epsg=4326)
        dis["label"]  = label
        dis["colour"] = colour
        parts.append(dis)
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs="EPSG:4326")

hydro_wgs[["geometry", "GEOG_UNIT_DESCR", "CLASS_SUBTYPE"]].to_file(OUT_STATIONS_JSON, driver="GeoJSON")
print(f"Saved → {OUT_STATIONS_JSON}")

compute_zones(hydro_proj, RINGS).to_file(OUT_STATION_ZONES, driver="GeoJSON")
print(f"Saved → {OUT_STATION_ZONES}")

hydro_lines_wgs = lines[lines["CLASS_SUBTYPE"].isin(LINE_COLOURS.keys())][["geometry", "CLASS_SUBTYPE", "GEOG_UNIT_DESCR"]]
hydro_lines_wgs.to_file(OUT_LINES_JSON, driver="GeoJSON")
print(f"Saved → {OUT_LINES_JSON}")

compute_zones(lines[lines["CLASS_SUBTYPE"].isin(LINE_COLOURS.keys())].to_crs(epsg=3347), LINE_RINGS).to_file(OUT_LINE_ZONES, driver="GeoJSON")
print(f"Saved → {OUT_LINE_ZONES}")

m.save(OUT_HTML)
print(f"Map saved → {OUT_HTML}")
