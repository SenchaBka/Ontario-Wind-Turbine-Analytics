import os
import json
import pandas as pd
import geopandas as gpd
from flask import Flask, jsonify, request, send_file, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATA_PATH       = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'data', 'Wind_Turbine_Database_en.xlsx')
WIND_PNG_PATH   = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'wind_speed_overlay.png')
WIND_JSON_PATH  = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'wind_speed_overlay.json')
RES_BUFFER_PATH = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'data', 'residential_buffer.gpkg')


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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
