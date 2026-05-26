import os
import json
import pandas as pd
import geopandas as gpd
from flask import Flask, jsonify, request, send_file, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATA_PATH        = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'data', 'Wind_Turbine_Database_en.xlsx')
WIND_PNG_PATH    = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'wind_speed_overlay.png')
WIND_JSON_PATH   = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'wind_speed_overlay.json')
RES_BUFFER_PATH  = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'data', 'residential_buffer.gpkg')
UTILITY_SITE_PATH    = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'data', 'Utility_Site.geojson')
UTILITY_LINE_PATH    = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'data', 'Utility_Line.geojson')
HYDRO_STATIONS_PATH  = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'hydro_stations.geojson')
HYDRO_ST_ZONES_PATH  = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'hydro_station_zones.geojson')
HYDRO_LINES_PATH     = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'hydro_lines.geojson')
HYDRO_LN_ZONES_PATH  = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'results', 'hydro_line_zones.geojson')


def extract_year(val):
    """Extract year from commissioning value (handles ranges like '2006/2008')."""
    if pd.isna(val) or str(val).strip() == 'nan':
        return None
    try:
        val_str = str(val).strip()
        if '/' in val_str:
            val_str = val_str.split('/')[0]
        return int(float(val_str))
    except (ValueError, TypeError):
        return None


def load_data():
    df = pd.read_excel(DATA_PATH)
    df = df[df['Province_Territory'] == 'Ontario']
    df = df.dropna(subset=['Latitude', 'Longitude'])
    df['_year'] = df['Commissioning'].apply(extract_year)
    return df


# Load once at startup
df = load_data()

# ── Hydro data — loaded from pre-built GeoJSON files ─────────────────────
with open(HYDRO_STATIONS_PATH)  as f: _hydro_pts_json     = f.read()
with open(HYDRO_ST_ZONES_PATH)  as f: _station_zones_json = f.read()
with open(HYDRO_LINES_PATH)     as f: _hydro_lines_json   = f.read()
with open(HYDRO_LN_ZONES_PATH)  as f: _line_zones_json    = f.read()


@app.route('/api/years')
def get_years():
    years = sorted(df['_year'].dropna().unique().astype(int).tolist())
    return jsonify({'min': years[0], 'max': years[-1]})


@app.route('/api/turbines')
def get_turbines():
    year = request.args.get('year', type=int)

    if year is None:
        filtered = df
    else:
        filtered = df[df['_year'].notna() & (df['_year'] <= year)]

    # Return only the columns needed for the map + popup
    result = filtered.drop(columns=['_year']).fillna('N/A')
    return jsonify(result.to_dict(orient='records'))


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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
