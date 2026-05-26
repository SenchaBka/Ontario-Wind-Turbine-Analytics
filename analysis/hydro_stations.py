import os
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
UTILITY_PATH = "analysis/data/Utility_Site.geojson"
OUT_HTML     = "analysis/results/hydro_distance_suitability_map.html"

# ---------------------------------------------------------------------------
# Suitability rings — drawn largest first so smaller ones sit on top
# (radius_km, label, colour)
# ---------------------------------------------------------------------------
RINGS = [
    (50, "Poor (25–50 km)",      "#d7191c"),
    (25, "Moderate (10–25 km)",  "#fdae61"),
    (10, "Good (5–10 km)",       "#ffffbf"),
    (5,  "Excellent (< 5 km)",   "#1a9641"),
]

# ---------------------------------------------------------------------------
# 1. Load hydro stations
# ---------------------------------------------------------------------------
utility = gpd.read_file(UTILITY_PATH)
hydro   = utility[utility["CLASS_SUBTYPE"] == "Hydro Station"].copy()
hydro_wgs = hydro.to_crs(epsg=4326)
print(f"Hydro stations: {len(hydro_wgs)}")

# ---------------------------------------------------------------------------
# 2. Build map
# ---------------------------------------------------------------------------
m = folium.Map(location=[51.25, -85.32], zoom_start=6, tiles="CartoDB positron")

# Draw rings per station (largest radius first)
for radius_km, label, colour in RINGS:
    layer = folium.FeatureGroup(name=label, show=True).add_to(m)
    for _, row in hydro_wgs.iterrows():
        folium.Circle(
            location=[row.geometry.y, row.geometry.x],
            radius=radius_km * 1000,
            color=colour,
            weight=1,
            fill=True,
            fill_color=colour,
            fill_opacity=0.15,
        ).add_to(layer)

# Hydro station markers on top
hydro_cluster = MarkerCluster(name="Hydro Stations").add_to(m)
for _, row in hydro_wgs.iterrows():
    desc = row.get("GEOG_UNIT_DESCR")
    label = desc if pd.notna(desc) else "Hydro Station"
    folium.Marker(
        location=[row.geometry.y, row.geometry.x],
        tooltip=label,
        popup=folium.Popup(f"<b>{label}</b>", max_width=200),
        icon=folium.Icon(color="blue", icon="bolt", prefix="fa"),
    ).add_to(hydro_cluster)

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
  <span style="color:blue">&#9679;</span> Hydro Station<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl(collapsed=False).add_to(m)

os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
m.save(OUT_HTML)
print(f"Map saved → {OUT_HTML}")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TURBINE_PATH = "analysis/data/Wind_Turbine_Database_en.xlsx"
UTILITY_PATH = "analysis/data/Utility_Site.geojson"
OUT_HTML     = "analysis/results/hydro_distance_suitability_map.html"

# ---------------------------------------------------------------------------
# Suitability bands  (upper_km, label, colour)
# ---------------------------------------------------------------------------
BANDS = [
    (5,           "Excellent", "#1a9641"),
    (10,          "Good",      "#a6d96a"),
    (25,          "Moderate",  "#ffffbf"),
    (50,          "Poor",      "#fdae61"),
    (float("inf"),"Exclude",   "#d7191c"),
]

def classify(dist_km):
    for threshold, label, colour in BANDS:
        if dist_km < threshold:
            return label, colour
    return "Exclude", "#d7191c"

# ---------------------------------------------------------------------------
# 1. Load hydro stations
# ---------------------------------------------------------------------------
utility = gpd.read_file(UTILITY_PATH)
hydro   = utility[utility["CLASS_SUBTYPE"] == "Hydro Station"].copy()
hydro   = hydro.to_crs(epsg=3347)   # Canada Albers Equal Area (metres)
print(f"Hydro stations  : {len(hydro)}")

# ---------------------------------------------------------------------------
# 2. Load Ontario wind turbines
# ---------------------------------------------------------------------------
df = pd.read_excel(TURBINE_PATH)
df = df[df["Province_Territory"] == "Ontario"].dropna(subset=["Latitude", "Longitude"])
turbines = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
    crs="EPSG:4326",
).to_crs(epsg=3347)
print(f"Ontario turbines: {len(turbines)}")

# ---------------------------------------------------------------------------
# 3. Distance to nearest hydro station per turbine
# ---------------------------------------------------------------------------
joined = gpd.sjoin_nearest(
    turbines[["geometry"]],
    hydro[["geometry"]],
    how="left",
    distance_col="dist_m",
)
turbines["dist_km"] = joined["dist_m"].values / 1000
turbines[["suitability", "colour"]] = turbines["dist_km"].apply(
    lambda d: pd.Series(classify(d))
)

print("\n=== Turbines by suitability ===")
print(turbines["suitability"].value_counts().to_string())
print(f"\nDistance stats — min: {turbines['dist_km'].min():.1f} km, "
      f"max: {turbines['dist_km'].max():.1f} km, "
      f"mean: {turbines['dist_km'].mean():.1f} km")

# ---------------------------------------------------------------------------
# 4. Build map
# ---------------------------------------------------------------------------
turbines_wgs = turbines.to_crs(epsg=4326)
hydro_wgs    = hydro.to_crs(epsg=4326)

m = folium.Map(location=[51.25, -85.32], zoom_start=6, tiles="CartoDB positron")

# Hydro station markers
hydro_cluster = MarkerCluster(name="Hydro Stations").add_to(m)
for _, row in hydro_wgs.iterrows():
    desc = row.get("GEOG_UNIT_DESCR")
    label = desc if pd.notna(desc) else "Hydro Station"
    folium.Marker(
        location=[row.geometry.y, row.geometry.x],
        tooltip=label,
        popup=folium.Popup(f"<b>{label}</b>", max_width=200),
        icon=folium.Icon(color="blue", icon="bolt", prefix="fa"),
    ).add_to(hydro_cluster)

# Turbines coloured by suitability band
for threshold, label, colour in BANDS:
    subset = turbines_wgs[turbines_wgs["suitability"] == label]
    if subset.empty:
        continue
    layer = folium.FeatureGroup(name=f"Turbines – {label} ({len(subset)})").add_to(m)
    for _, row in subset.iterrows():
        project = row.get("Project_Name")
        popup_html = (
            f"<b>{row.get('Turbine_Identifier', 'Turbine')}</b><br>"
            f"<b>Project:</b> {project if pd.notna(project) else '—'}<br>"
            f"<b>Distance to hydro:</b> {row['dist_km']:.1f} km<br>"
            f"<b>Suitability:</b> {label}"
        )
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=5,
            color=colour,
            fill=True,
            fill_color=colour,
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{label} ({row['dist_km']:.1f} km)",
        ).add_to(layer)

# Legend
band_rows = "".join(
    f'<span style="color:{c}">&#9679;</span> {l} '
    f'({"&lt; 5 km" if i == 0 else f"{BANDS[i-1][0]}–{t} km" if t != float("inf") else "&gt; 50 km"})<br>'
    for i, (t, l, c) in enumerate(BANDS)
)
legend_html = f"""
<div style="
    position:fixed; bottom:30px; left:30px; z-index:9999;
    background:rgba(255,255,255,0.92); padding:10px 16px;
    border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.25);
    font-family:sans-serif; font-size:13px;">
  <b>Distance to Nearest Hydro Station</b><br>
  {band_rows}
  <span style="color:blue">&#9679;</span> Hydro Station<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl(collapsed=False).add_to(m)

os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
m.save(OUT_HTML)
print(f"\nMap saved → {OUT_HTML}")
