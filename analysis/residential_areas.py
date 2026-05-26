import geopandas as gpd

# Load built-up areas
gdf = gpd.read_file("analysis/data/Built_Up_Area.geojson")
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
unified.to_file("analysis/api/residential_buffer.gpkg", driver="GPKG")
print("Saved to analysis/api/residential_buffer.gpkg")
# Styling is applied in frontend/index.html
