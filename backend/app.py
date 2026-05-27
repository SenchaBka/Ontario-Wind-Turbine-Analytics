import os
import json
import pandas as pd
import geopandas as gpd
from flask import Flask, jsonify, send_file, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

TURBINES_PATH        = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'turbines.geojson')
WIND_PNG_PATH        = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'wind_speed_overlay.png')
WIND_JSON_PATH       = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'wind_speed_overlay.json')
RES_BUFFER_PATH      = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'residential_buffer.gpkg')
HYDRO_STATIONS_PATH  = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'hydro_stations.geojson')
HYDRO_ST_ZONES_PATH  = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'hydro_station_zones.geojson')
HYDRO_LINES_PATH     = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'hydro_lines.geojson')
HYDRO_LN_ZONES_PATH  = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'hydro_line_zones.geojson')
ROADS_PATH           = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'roads.geojson')
PROTECTED_AREAS_PATH = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'protected_areas.geojson')
TOP_SITES_PATH       = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'top_candidate_sites.geojson')
LAKES_PATH           = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'lakes.geojson')
TURBINE_BUFFER_PATH = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'api', 'turbine_buffer.geojson')

# ── Pre-load GeoJSON files ────────────────────────────────────────────────
with open(HYDRO_STATIONS_PATH)  as f: _hydro_pts_json     = f.read()
with open(HYDRO_ST_ZONES_PATH)  as f: _station_zones_json = f.read()
with open(HYDRO_LINES_PATH)     as f: _hydro_lines_json   = f.read()
with open(HYDRO_LN_ZONES_PATH)  as f: _line_zones_json    = f.read()
with open(TOP_SITES_PATH)       as f: _top_sites_json      = f.read()
with open(LAKES_PATH)           as f: _lakes_json           = f.read()



# Returns all wind turbine locations and properties as GeoJSON
@app.route('/api/turbines')
def get_turbines():
    """Return turbines GeoJSON with all properties."""
    gdf = gpd.read_file(TURBINES_PATH)
    return Response(gdf.to_json(), mimetype='application/json')



# Returns metadata (bounds, color scale) for wind speed overlay
@app.route('/api/wind-overlay')
def get_wind_overlay():
    """Return pre-computed wind-speed overlay bounds and colour metadata."""
    with open(WIND_JSON_PATH) as f:
        return jsonify(json.load(f))



# Returns PNG image for wind speed overlay (for map display)
@app.route('/api/wind-overlay/image')
def get_wind_overlay_image():
    """Serve the pre-built EPSG:3857 wind-speed overlay PNG."""
    return send_file(WIND_PNG_PATH, mimetype='image/png')



# Returns the dissolved 550m residential buffer as GeoJSON (exclusion zone)
@app.route('/api/residential-buffer')
def get_residential_buffer():
    """Return the dissolved 550 m residential buffer as GeoJSON."""
    gdf = gpd.read_file(RES_BUFFER_PATH)
    return Response(gdf.to_json(), mimetype='application/json')



# Returns the 300m turbine exclusion buffer as GeoJSON
@app.route('/api/turbine-buffer')
def get_turbine_buffer():
    """Return the 300m turbine exclusion buffer as GeoJSON."""
    with open(TURBINE_BUFFER_PATH, encoding='utf-8') as f:
        return Response(f.read(), mimetype='application/geo+json')

# Returns all hydro station point locations as GeoJSON
@app.route('/api/hydro-stations')
def get_hydro_stations():
    return Response(_hydro_pts_json, mimetype='application/json')



# Returns hydro station buffer zones as GeoJSON
@app.route('/api/hydro-station-zones')
def get_hydro_station_zones():
    return Response(_station_zones_json, mimetype='application/json')



# Returns hydro transmission line geometries as GeoJSON
@app.route('/api/hydro-lines')
def get_hydro_lines():
    return Response(_hydro_lines_json, mimetype='application/json')



# Returns hydro line buffer zones as GeoJSON
@app.route('/api/hydro-line-zones')
def get_hydro_line_zones():
    return Response(_line_zones_json, mimetype='application/json')



# Returns filtered major roads (with road_class) as GeoJSON
@app.route('/api/roads')
def get_roads():
    """Return the roads GeoJSON with road_class property for frontend styling."""
    gdf = gpd.read_file(ROADS_PATH)
    return Response(gdf.to_json(), mimetype='application/json')



# Returns protected areas (parks, reserves, etc.) as GeoJSON
@app.route('/api/protected-areas')
def get_protected_areas():
    """Return the protected areas GeoJSON with protected_type property."""
    gdf = gpd.read_file(PROTECTED_AREAS_PATH)
    return Response(gdf.to_json(), mimetype='application/json')



# Returns top ML-scored wind turbine candidate sites as GeoJSON
@app.route('/api/top-sites')
def get_top_sites():
    """Return top 100 ML-scored candidate sites."""
    return Response(_top_sites_json, mimetype='application/json')



# Returns Ontario lakes (≥ 10 km²) as GeoJSON
@app.route('/api/lakes')
def get_lakes():
    """Return Ontario lakes (≥ 10 km²) as GeoJSON."""
    return Response(_lakes_json, mimetype='application/json')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=False, port=port)
