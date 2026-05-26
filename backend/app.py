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
UTILITY_SITE_PATH = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'data', 'Utility_Site.geojson')
UTILITY_LINE_PATH = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'data', 'Utility_Line.geojson')

STATION_RINGS = [
    (50, "Poor (25–50 km)",     "#d7191c"),
    (25, "Moderate (10–25 km)", "#fdae61"),
    (10, "Good (5–10 km)",      "#ffffbf"),
    (5,  "Excellent (< 5 km)",  "#1a9641"),
]
LINE_RINGS = [
    (30, "Poor (15–30 km)",     "#d7191c"),
    (15, "Moderate (5–15 km)",  "#fdae61"),
    (5,  "Good (1–5 km)",       "#ffffbf"),
    (1,  "Excellent (< 1 km)",  "#1a9641"),
]
HYDRO_LINE_SUBTYPES = ["Hydro Line", "Unknown Transmission Line", "Submerged Hydro Line"]


def compute_zones(gdf_proj, rings):
    parts = []
    for radius_km, label, colour in rings:
        buf = gpd.GeoDataFrame(geometry=gdf_proj.geometry.buffer(radius_km * 1000), crs=gdf_proj.crs)
        dis = buf.dissolve().to_crs(epsg=4326)
        dis["label"]  = label
        dis["colour"] = colour
        parts.append(dis)
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs="EPSG:4326")


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

# ── Hydro data — precomputed at startup ──────────────────────────────────
print("Precomputing hydro station zones…")
_util_site   = gpd.read_file(UTILITY_SITE_PATH)
_hydro_pts   = _util_site[_util_site["CLASS_SUBTYPE"] == "Hydro Station"]
_hydro_pts_json          = _hydro_pts.to_crs(epsg=4326)[["geometry", "GEOG_UNIT_DESCR", "CLASS_SUBTYPE"]].to_json()
_station_zones_json      = compute_zones(_hydro_pts.to_crs(epsg=3347), STATION_RINGS).to_json()

print("Precomputing hydro line zones…")
_util_line   = gpd.read_file(UTILITY_LINE_PATH)
_hydro_lines = _util_line[_util_line["CLASS_SUBTYPE"].isin(HYDRO_LINE_SUBTYPES)]
_hydro_lines_json        = _hydro_lines[["geometry", "CLASS_SUBTYPE", "GEOG_UNIT_DESCR"]].to_json()
_line_zones_json         = compute_zones(_hydro_lines.to_crs(epsg=3347), LINE_RINGS).to_json()
print("Hydro data ready.")


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
