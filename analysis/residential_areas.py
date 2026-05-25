import geopandas as gpd
import folium

# Load built-up areas
gdf = gpd.read_file("data/Built_Up_Area.geojson")
print(f"Loaded {len(gdf)} built-up area polygons")

# --- Buffer 550 m then dissolve into one unified polygon ---
# (buffer already contains the original area, so this is house + surroundings)
gdf_metric = gdf.to_crs(epsg=3347)
gdf_metric["geometry"] = gdf_metric.geometry.buffer(550)

unified = gdf_metric.dissolve()[["geometry"]]

# Simplify in metric CRS to reduce vertex count (100 m tolerance)
unified["geometry"] = unified.geometry.simplify(100, preserve_topology=True)

# Reproject back to WGS84
unified = unified.to_crs(epsg=4326)
print("Buffer + dissolve + simplify done")

# Export simplified polygon for reuse
unified.to_file("data/residential_buffer.gpkg", driver="GPKG")
print("Saved to data/residential_buffer.gpkg")

# --- Interactive HTML map ---
bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
m = folium.Map(location=center, zoom_start=6, tiles="CartoDB positron")

folium.GeoJson(
    unified.to_json(),
    name="Residential Areas + 550 m Buffer",
    style_function=lambda _: {
        "fillColor": "#ff7800",
        "color": "#cc5500",
        "weight": 0.8,
        "fillOpacity": 0.4,
    },
).add_to(m)

folium.LayerControl().add_to(m)

output_path = "built_up_areas_map.html"
m.save(output_path)
import os
size_mb = os.path.getsize(output_path) / 1_000_000
print(f"Map saved to {output_path} ({size_mb:.1f} MB)")
