import geopandas as gpd

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
