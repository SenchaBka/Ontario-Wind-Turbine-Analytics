import os
import geopandas as gpd
import folium

GDB_PATH = "analysis/data/ORNELEM_tmp/Non_Sensitive.gdb"
OUT_HTML = "analysis/results/roads_map.html"

# ---------------------------------------------------------------------------
# 1. Load road network
# ---------------------------------------------------------------------------
print("Loading road network (this may take a moment)…")
roads = gpd.read_file(GDB_PATH, layer="ORN_ROAD_NET_ELEMENT")

print(f"\n=== Ontario Road Network ===")
print(f"Total road segments : {len(roads):,}")
print(f"CRS                 : {roads.crs}")
print(f"Geometry types      :\n{roads.geometry.geom_type.value_counts().to_string()}")

bounds = roads.total_bounds  # [minx, miny, maxx, maxy]
print(f"\nBounding box:")
print(f"  Longitude : {bounds[0]:.4f} → {bounds[2]:.4f}")
print(f"  Latitude  : {bounds[1]:.4f} → {bounds[3]:.4f}")

print(f"\nTotal length (degrees, approx): {roads['SHAPE_Length'].sum():,.0f}")
print(f"Avg segment length            : {roads['SHAPE_Length'].mean():.4f}°")

# ---------------------------------------------------------------------------
# 2. Simplify geometries for visualisation
#    Project to EPSG:3347 (metres), simplify at 300 m tolerance, back to 4326
# ---------------------------------------------------------------------------
print("\nSimplifying geometries for map rendering…")
roads_proj      = roads.to_crs(epsg=3347)
roads_proj["geometry"] = roads_proj.geometry.simplify(300, preserve_topology=True)
roads_simple    = roads_proj[["geometry"]].to_crs(epsg=4326)
roads_simple    = roads_simple[~roads_simple.geometry.is_empty]
print(f"Simplified segments : {len(roads_simple):,}")

# ---------------------------------------------------------------------------
# 3. Build map
# ---------------------------------------------------------------------------
m = folium.Map(location=[51.25, -85.32], zoom_start=6, tiles="CartoDB positron")

folium.GeoJson(
    data=roads_simple.__geo_interface__,
    name="Ontario Roads",
    style_function=lambda _: {
        "color":   "#555555",
        "weight":  0.4,
        "opacity": 0.6,
    },
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
m.save(OUT_HTML)
print(f"\nMap saved → {OUT_HTML}")
