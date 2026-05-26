import os
import geopandas as gpd
import folium

OUT_HTML = "analysis/results/protected_areas_map.html"
OUT_GEOJSON = "analysis/results/protected_areas.geojson"

print("=" * 70)
print("PROTECTED AREAS ANALYSIS")
print("=" * 70)

# Conservation Reserves
print("\n### CONSERVATION RESERVES ###")
cr = gpd.read_file('analysis/data/Conservation_reserve_regulated.geojson')
print(f"Total reserves: {len(cr)}")
print(f"\nTypes:")
print(cr['TYPE_ENG'].value_counts())
print(f"\nStatus:")
print(cr['STATUS_ENG'].value_counts())
cr_area = cr.to_crs(epsg=3347).area.sum() / 1e6
print(f"\nTotal area: {cr_area:,.0f} km²")

# Provincial Parks
print("\n" + "=" * 70)
print("### PROVINCIAL PARKS ###")
pp = gpd.read_file('analysis/data/Provincial_park_regulated.geojson')
print(f"Total parks: {len(pp)}")
print(f"\nPark Classes:")
print(pp['PROVINCIAL_PARK_CLASS_ENG'].value_counts())
print(f"\nStatus:")
print(pp['STATUS_ENG'].value_counts())
print(f"\nOperating Status:")
print(pp['OPERATING_STATUS_IND'].value_counts())
pp_area = pp.to_crs(epsg=3347).area.sum() / 1e6
print(f"\nTotal area: {pp_area:,.0f} km²")

# Greenbelt
print("\n" + "=" * 70)
print("### GREENBELT ###")
gb = gpd.read_file('analysis/data/Greenbelt_designation.geojson')
print(f"Total polygons: {len(gb)}")
print(f"\nDesignations:")
print(gb['DESIGNATION'].value_counts())
gb_area = gb.to_crs(epsg=3347).area.sum() / 1e6
print(f"\nTotal area: {gb_area:,.0f} km²")

# Summary
print("\n" + "=" * 70)
print("### SUMMARY ###")
total_area = cr_area + pp_area + gb_area
ontario_area = 1076395  # km²
print(f"Conservation Reserves:  {cr_area:>10,.0f} km²  ({len(cr):>3} polygons)")
print(f"Provincial Parks:       {pp_area:>10,.0f} km²  ({len(pp):>3} polygons)")
print(f"Greenbelt:              {gb_area:>10,.0f} km²  ({len(gb):>3} polygons)")
print(f"{'─' * 70}")
print(f"Total Protected:        {total_area:>10,.0f} km²  ({cr_area/ontario_area*100:.1f}% + {pp_area/ontario_area*100:.1f}% + {gb_area/ontario_area*100:.1f}%)")
print(f"Ontario Total Area:     {ontario_area:>10,.0f} km²")

# ---------------------------------------------------------------------------
# MAPPING
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("GENERATING MAP")
print("=" * 70)

# Prepare data
cr_map = cr[["geometry"]].to_crs(epsg=4326)
cr_map["protected_type"] = "Conservation Reserve"

pp_map = pp[["geometry"]].to_crs(epsg=4326)
pp_map["protected_type"] = "Provincial Park"

gb_map = gb[["geometry"]].to_crs(epsg=4326)
gb_map["protected_type"] = "Greenbelt"

# Merge all into one GeoDataFrame
all_protected = gpd.GeoDataFrame(
    gpd.pd.concat([cr_map, pp_map, gb_map], ignore_index=True),
    crs="EPSG:4326"
)
print(f"Total polygons: {len(all_protected):,}")

# Save combined GeoJSON for backend
os.makedirs(os.path.dirname(OUT_GEOJSON), exist_ok=True)
all_protected.to_file(OUT_GEOJSON, driver="GeoJSON")
print(f"GeoJSON saved → {OUT_GEOJSON}")

# Build interactive map with toggle layers
m = folium.Map(location=[51.25, -85.32], zoom_start=6, tiles="CartoDB positron")

# Conservation Reserves - green
cr_layer = folium.FeatureGroup(name="Conservation Reserves", show=True).add_to(m)
folium.GeoJson(
    cr_map,
    style_function=lambda _: {
        "color": "#2ca25f",
        "weight": 1,
        "fillColor": "#2ca25f",
        "fillOpacity": 0.3,
    }
).add_to(cr_layer)

# Provincial Parks - dark green
pp_layer = folium.FeatureGroup(name="Provincial Parks", show=True).add_to(m)
folium.GeoJson(
    pp_map,
    style_function=lambda _: {
        "color": "#006d2c",
        "weight": 1,
        "fillColor": "#006d2c",
        "fillOpacity": 0.35,
    }
).add_to(pp_layer)

# Greenbelt - light green
gb_layer = folium.FeatureGroup(name="Greenbelt", show=True).add_to(m)
folium.GeoJson(
    gb_map,
    style_function=lambda _: {
        "color": "#99d8c9",
        "weight": 1,
        "fillColor": "#99d8c9",
        "fillOpacity": 0.25,
    }
).add_to(gb_layer)

legend_html = """
<div style="
    position:fixed; bottom:30px; left:30px; z-index:9999;
    background:rgba(255,255,255,0.92); padding:10px 16px;
    border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.25);
    font-family:sans-serif; font-size:13px;">
  <b>Protected Areas (No Build Zones)</b><br>
  <span style="color:#99d8c9">&#9632;</span> Greenbelt (8,574 km²)<br>
  <span style="color:#2ca25f">&#9632;</span> Conservation Reserves (15,057 km²)<br>
  <span style="color:#006d2c">&#9632;</span> Provincial Parks (81,324 km²)<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl(collapsed=False).add_to(m)

m.save(OUT_HTML)
print(f"Map saved → {OUT_HTML}")
