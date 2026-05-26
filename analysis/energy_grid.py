import os
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
DATA_PATH = "analysis/data/Utility_Site.geojson"
OUT_HTML  = "analysis/results/utility_sites_map.html"

gdf = gpd.read_file(DATA_PATH)
print(f"Total records  : {len(gdf)}")
print(f"CRS            : {gdf.crs}")
print(f"Geometry types : {gdf.geom_type.value_counts().to_dict()}")
print()

# ---------------------------------------------------------------------------
# 2. Breakdown by facility type
# ---------------------------------------------------------------------------
print("=== Sites by CLASS_SUBTYPE ===")
subtype_counts = gdf["CLASS_SUBTYPE"].value_counts()
print(subtype_counts.to_string())
print()

# ---------------------------------------------------------------------------
# 3. Operating status
# ---------------------------------------------------------------------------
print("=== Operating Status ===")
status_counts = gdf["OPERATING_STATUS_IND"].fillna("Unknown").value_counts()
print(status_counts.to_string())
print()

# ---------------------------------------------------------------------------
# 4. Verification status
# ---------------------------------------------------------------------------
print("=== Verification Status ===")
verif_counts = gdf["VERIFICATION_STATUS_FLG"].fillna("Unknown").value_counts()
print(verif_counts.to_string())
print()

# ---------------------------------------------------------------------------
# 5. Location accuracy breakdown
# ---------------------------------------------------------------------------
print("=== Location Accuracy ===")
accuracy_counts = gdf["LOCATION_ACCURACY"].fillna("Unknown").value_counts()
print(accuracy_counts.to_string())
print()

# ---------------------------------------------------------------------------
# 6. Bounding box
# ---------------------------------------------------------------------------
bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
print(f"Bounding box   : W={bounds[0]:.3f}, S={bounds[1]:.3f}, "
      f"E={bounds[2]:.3f}, N={bounds[3]:.3f}")
print()

# ---------------------------------------------------------------------------
# 7. Interactive map – markers coloured by CLASS_SUBTYPE
# ---------------------------------------------------------------------------
COLOUR_MAP = {
    "Dam":                "#1f77b4",   # blue
    "Pumping Station":    "#ff7f0e",   # orange
    "Fibre Optic Station":"#2ca02c",   # green
    "Hydro Station":      "#d62728",   # red
}
DEFAULT_COLOUR = "#9467bd"             # purple for any other type

centre_lat = (bounds[1] + bounds[3]) / 2
centre_lon = (bounds[0] + bounds[2]) / 2

m = folium.Map(location=[centre_lat, centre_lon], zoom_start=6,
               tiles="CartoDB positron")

# One cluster per subtype so colours are preserved
for subtype, colour in {**COLOUR_MAP,
                         **{s: DEFAULT_COLOUR for s in gdf["CLASS_SUBTYPE"].unique()
                            if s not in COLOUR_MAP}}.items():
    subset = gdf[gdf["CLASS_SUBTYPE"] == subtype]
    if subset.empty:
        continue
    cluster = MarkerCluster(name=subtype).add_to(m)
    for _, row in subset.iterrows():
        lon, lat = row.geometry.x, row.geometry.y
        op_status = row["OPERATING_STATUS_IND"] or "Unknown"
        popup_html = (
            f"<b>{subtype}</b><br>"
            f"<b>OGF ID:</b> {row['OGF_ID']}<br>"
            f"<b>Operating:</b> {op_status}<br>"
            f"<b>Location:</b> {row['LOCATION_DESCR'] or '—'}<br>"
            f"<b>Description:</b> {row['GEOG_UNIT_DESCR'] or '—'}<br>"
            f"<b>Verified:</b> {row['VERIFICATION_STATUS_FLG']}"
        )
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color=colour,
            fill=True,
            fill_color=colour,
            fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=subtype,
        ).add_to(cluster)

# Legend
legend_html = """
<div style="
    position: fixed; bottom: 30px; left: 30px; z-index: 9999;
    background: rgba(255,255,255,0.92); padding: 10px 16px;
    border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    font-family: sans-serif; font-size: 13px;">
  <b>Utility Site Type</b><br>
  <span style="color:#1f77b4">&#9679;</span> Dam<br>
  <span style="color:#ff7f0e">&#9679;</span> Pumping Station<br>
  <span style="color:#2ca02c">&#9679;</span> Fibre Optic Station<br>
  <span style="color:#d62728">&#9679;</span> Hydro Station<br>
  <span style="color:#9467bd">&#9679;</span> Other<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl(collapsed=False).add_to(m)

os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
m.save(OUT_HTML)
print(f"Map saved → {OUT_HTML}")
