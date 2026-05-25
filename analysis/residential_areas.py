import geopandas as gpd
import folium
from folium.plugins import FastMarkerCluster

# Load built-up areas
gdf = gpd.read_file("data/Built_Up_Area.geojson")
print(f"Loaded {len(gdf)} built-up area polygons")

# --- 550 m buffer ---
# Reproject to metric CRS (EPSG:3347 Statistics Canada Lambert)
gdf_metric = gdf.to_crs(epsg=3347)
gdf_metric["geometry"] = gdf_metric.geometry.buffer(550)

# Dissolve overlapping buffers and reproject back to WGS84 for mapping
buffer_dissolved = gdf_metric.dissolve().to_crs(epsg=4326)
print("550 m buffer created and dissolved")

# Drop timestamp columns (not JSON-serialisable) and keep only useful fields
keep_cols = ["COMMUNITY_CLASS", "LOCATION_DESCR", "geometry"]
gdf_map = gdf[[c for c in keep_cols if c in gdf.columns]]

# --- Interactive HTML map ---
bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
m = folium.Map(location=center, zoom_start=6, tiles="CartoDB positron")

# Add built-up areas (original)
folium.GeoJson(
    gdf_map.to_json(),
    name="Built-Up Areas",
    style_function=lambda _: {
        "fillColor": "#ff7800",
        "color": "#cc5500",
        "weight": 0.5,
        "fillOpacity": 0.5,
    },
    tooltip=folium.GeoJsonTooltip(fields=["COMMUNITY_CLASS", "LOCATION_DESCR"],
                                   aliases=["Class", "Location"]),
).add_to(m)

# Add 550 m buffer (geometry only)
buffer_geom = buffer_dissolved[["geometry"]]
folium.GeoJson(
    buffer_geom.to_json(),
    name="550 m Buffer",
    style_function=lambda _: {
        "fillColor": "#3388ff",
        "color": "#1155cc",
        "weight": 0.5,
        "fillOpacity": 0.2,
    },
).add_to(m)

folium.LayerControl().add_to(m)

output_path = "built_up_areas_map.html"
m.save(output_path)
print(f"Map saved to {output_path}")
