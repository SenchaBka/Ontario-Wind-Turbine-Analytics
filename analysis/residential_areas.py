"""
residential_areas.py
Loads Ontario.geojson (~3.8 M land parcels), simplifies geometries,
applies a 550 m buffer (Ontario wind-turbine setback), dissolves to a
single exclusion-zone polygon, then renders a Folium map:

  • Light red fill  – 550 m exclusion zone around every parcel
  • Black outline   – simplified individual parcel boundaries

Expensive processing is cached to GeoPackage files so subsequent runs
are instant.
"""

import os
import geopandas as gpd
import folium
from shapely.ops import unary_union
from shapely.validation import make_valid

# ── Paths ──────────────────────────────────────────────────────────
DATA_DIR       = "data"
INPUT          = os.path.join(DATA_DIR, "Ontario.geojson")
CACHE_PARCELS  = os.path.join(DATA_DIR, "residential_parcels.gpkg")
CACHE_BUFFER   = os.path.join(DATA_DIR, "residential_buffer.gpkg")
OUT_HTML       = "residential_areas_map.html"

# ── Parameters ─────────────────────────────────────────────────────
BUFFER_M         = 550    # Ontario wind-turbine setback (metres)
SIMPLIFY_PRE_M   = 25     # simplify before buffering (metres) – speeds up buffer
SIMPLIFY_WEB_DEG = 0.001  # final simplify for browser GeoJSON (~100 m)

# ══════════════════════════════════════════════════════════════════
# 1.  Heavy processing  (skipped when cache exists)
# ══════════════════════════════════════════════════════════════════
if not (os.path.exists(CACHE_PARCELS) and os.path.exists(CACHE_BUFFER)):

    print("─── Loading Ontario.geojson  (809 MB – this takes a few minutes) ───")
    gdf = gpd.read_file(INPUT)
    print(f"    {len(gdf):,} features loaded   CRS={gdf.crs}")

    # Project to Statistics Canada Lambert (metres)
    print("─── Projecting to EPSG:3347 ───")
    gdf_m = gdf.to_crs("EPSG:3347")
    del gdf  # free RAM

    # Simplify in metres to shrink coordinate count before buffering
    print(f"─── Simplifying ({SIMPLIFY_PRE_M} m tolerance) ───")
    gdf_m["geometry"] = gdf_m.geometry.simplify(
        SIMPLIFY_PRE_M, preserve_topology=True
    )
    # Repair any geometries that became invalid after simplification
    # (using make_valid keeps all buildings instead of dropping them)
    gdf_m = gdf_m[gdf_m.geometry.notna()].copy()
    gdf_m["geometry"] = gdf_m.geometry.apply(
        lambda g: make_valid(g) if not g.is_valid else g
    )
    gdf_m = gdf_m[~gdf_m.geometry.is_empty].copy()
    print(f"    {len(gdf_m):,} features after simplification + repair")

    # Cache simplified parcels
    print("─── Caching simplified parcels ───")
    gdf_m.to_file(CACHE_PARCELS, driver="GPKG")

    # Buffer by 550 m
    print(f"─── Buffering by {BUFFER_M} m ───")
    gdf_buf = gdf_m.copy()
    gdf_buf["geometry"] = gdf_m.geometry.buffer(BUFFER_M)

    # Dissolve all buffered polygons into one exclusion-zone shape
    print("─── Dissolving buffer (unary_union – slow for 3.8 M features) ───")
    buf_union = unary_union(gdf_buf.geometry)
    buf_gdf   = gpd.GeoDataFrame(geometry=[buf_union], crs="EPSG:3347")
    del gdf_buf, gdf_m

    # Cache buffer
    print("─── Caching buffer ───")
    buf_gdf.to_file(CACHE_BUFFER, driver="GPKG")
    print("─── Processing complete – cached files written ───\n")

else:
    print("✓  Using cached files (re-run will skip heavy processing)")


# ══════════════════════════════════════════════════════════════════
# 2.  Load cached data + convert to EPSG:4326
# ══════════════════════════════════════════════════════════════════
print("Loading cached buffer …")
buf = gpd.read_file(CACHE_BUFFER).to_crs("EPSG:4326")

# ══════════════════════════════════════════════════════════════════
# 3.  Simplify for web rendering
# ══════════════════════════════════════════════════════════════════
print("Simplifying for browser …")
buf["geometry"] = buf.geometry.simplify(
    SIMPLIFY_WEB_DEG, preserve_topology=True
)
buf = buf[~buf.geometry.is_empty]

buf_json = buf.to_json()
print(f"  Buffer GeoJSON   : {len(buf_json) / 1024:.0f} KB")


# ══════════════════════════════════════════════════════════════════
# 4.  Folium map
# ══════════════════════════════════════════════════════════════════
print("Building Folium map …")
m = folium.Map(
    location=[49.0, -85.0],
    zoom_start=6,
    tiles="CartoDB positron",
)

# 550 m exclusion zone – light red fill
folium.GeoJson(
    buf_json,
    name="550 m exclusion zone",
    style_function=lambda _: {
        "fillColor": "#ff6b6b",
        "color":     "#cc0000",
        "weight":    0.8,
        "fillOpacity": 0.35,
    },
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# Legend
legend_html = """
<div style="
    position:fixed; bottom:30px; left:50%;
    transform:translateX(-50%);
    z-index:9999;
    background:rgba(255,255,255,0.92);
    padding:10px 18px; border-radius:8px;
    box-shadow:0 2px 8px rgba(0,0,0,0.2);
    font-family:sans-serif; font-size:12px; text-align:center;">
  <b>Ontario Wind-Turbine Setback</b><br>
  <span style="display:inline-block;width:14px;height:14px;
    background:#ff6b6b;opacity:0.6;border:1px solid #cc0000;
    vertical-align:middle;margin-right:5px;border-radius:2px;"></span>
  550 m exclusion zone (dissolved)
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

m.save(OUT_HTML)
print(f"\nMap saved → {OUT_HTML}")
