import os
import json
import pandas as pd
import geopandas as gpd
from flask import Flask, jsonify, send_file, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

TURBINES_PATH        = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'turbines.geojson')
WIND_PNG_PATH        = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'wind_speed_overlay.png')
WIND_JSON_PATH       = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'wind_speed_overlay.json')
RES_BUFFER_PATH      = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'data', 'residential_buffer.gpkg')
HYDRO_STATIONS_PATH  = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'hydro_stations.geojson')
HYDRO_ST_ZONES_PATH  = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'hydro_station_zones.geojson')
HYDRO_LINES_PATH     = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'hydro_lines.geojson')
HYDRO_LN_ZONES_PATH  = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'hydro_line_zones.geojson')
ROADS_PATH           = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'roads.geojson')
PROTECTED_AREAS_PATH = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'protected_areas.geojson')
TOP_SITES_PATH       = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'top_candidate_sites.geojson')
LAKES_PATH           = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'lakes.geojson')

# ── Pre-load GeoJSON files ────────────────────────────────────────────────
with open(HYDRO_STATIONS_PATH)  as f: _hydro_pts_json     = f.read()
with open(HYDRO_ST_ZONES_PATH)  as f: _station_zones_json = f.read()
with open(HYDRO_LINES_PATH)     as f: _hydro_lines_json   = f.read()
with open(HYDRO_LN_ZONES_PATH)  as f: _line_zones_json    = f.read()
with open(TOP_SITES_PATH)       as f: _top_sites_json      = f.read()
with open(LAKES_PATH)           as f: _lakes_json           = f.read()


@app.route('/api/turbines')
def get_turbines():
    """Return turbines GeoJSON with all properties."""
    gdf = gpd.read_file(TURBINES_PATH)
    return Response(gdf.to_json(), mimetype='application/json')


@app.route('/api/wind-overlay')
def get_wind_overlay():
    """Return pre-computed wind-speed overlay bounds and colour metadata."""
    with open(WIND_JSON_PATH) as f:
        return jsonify(json.load(f))


@app.route('/api/wind-overlay/image')
def get_wind_overlay_image():
    """Serve the pre-built EPSG:3857 wind-speed overlay PNG."""
    return send_file(WIND_PNG_PATH, mimetype='image/png')


@app.route('/api/residential-buffer')
def get_residential_buffer():
    """Return the dissolved 550 m residential buffer as GeoJSON."""
    gdf = gpd.read_file(RES_BUFFER_PATH)
    return Response(gdf.to_json(), mimetype='application/json')


@app.route('/api/hydro-stations')
def get_hydro_stations():
    return Response(_hydro_pts_json, mimetype='application/json')


@app.route('/api/hydro-station-zones')
def get_hydro_station_zones():
    return Response(_station_zones_json, mimetype='application/json')


@app.route('/api/hydro-lines')
def get_hydro_lines():
    return Response(_hydro_lines_json, mimetype='application/json')


@app.route('/api/hydro-line-zones')
def get_hydro_line_zones():
    return Response(_line_zones_json, mimetype='application/json')


@app.route('/api/roads')
def get_roads():
    """Return the roads GeoJSON with road_class property for frontend styling."""
    gdf = gpd.read_file(ROADS_PATH)
    return Response(gdf.to_json(), mimetype='application/json')


@app.route('/api/protected-areas')
def get_protected_areas():
    """Return the protected areas GeoJSON with protected_type property."""
    gdf = gpd.read_file(PROTECTED_AREAS_PATH)
    return Response(gdf.to_json(), mimetype='application/json')


@app.route('/api/top-sites')
def get_top_sites():
    """Return top 100 ML-scored candidate sites."""
    return Response(_top_sites_json, mimetype='application/json')


@app.route('/api/lakes')
def get_lakes():
    """Return Ontario lakes (≥ 10 km²) as GeoJSON."""
    return Response(_lakes_json, mimetype='application/json')


if __name__ == '__main__':
    app.run(debug=True, port=5000)
