import geopandas as gpd
from shapely.geometry import Point
from pyproj import Transformer

buf = gpd.read_file('data/residential_buffer.gpkg')
print('CRS:', buf.crs)
print('Bounds:', buf.total_bounds)
geom = buf.geometry[0]
print('Geom type:', geom.geom_type)
if hasattr(geom, 'geoms'):
    parts = list(geom.geoms)
    print('Num sub-polygons:', len(parts))
    areas = sorted([p.area for p in parts], reverse=True)
    print('Largest 5 sub-polygon areas (m2):', areas[:5])

t = Transformer.from_crs('EPSG:4326', 'EPSG:3347', always_xy=True)

cities = {
    'Toronto downtown':  (-79.383, 43.653),
    'Ottawa downtown':   (-75.695, 45.421),
    'Hamilton':          (-79.866, 43.256),
    'Mississauga':       (-79.643, 43.589),
    'London ON':         (-81.249, 42.984),
    'Windsor':           (-83.034, 42.317),
}
for name, (lon, lat) in cities.items():
    x, y = t.transform(lon, lat)
    covered = geom.contains(Point(x, y))
    status = 'COVERED' if covered else 'MISSING'
    print(f'  {name}: {status}')
