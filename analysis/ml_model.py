"""
Wind Turbine Suitability Model
Combines rule-based scoring with ML prediction from existing turbines
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from shapely.geometry import Point, box
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
import json

# ============================================================================
# CONFIGURATION
# ============================================================================
ONTARIO_BOUNDARY = "analysis/data/ontario_boundary.gpkg"
WIND_RASTER = "analysis/data/CAN_wind-speed_100m.tif"

# Constraint layers
PROTECTED_AREAS = "analysis/results/protected_areas.geojson"
RESIDENTIAL_BUFFER = "analysis/data/residential_buffer.gpkg"
HYDRO_STATIONS = "analysis/results/hydro_stations.geojson"
HYDRO_STATION_ZONES = "analysis/results/hydro_station_zones.geojson"
HYDRO_LINES = "analysis/results/hydro_lines.geojson"
HYDRO_LINE_ZONES = "analysis/results/hydro_line_zones.geojson"
ROADS = "analysis/results/roads.geojson"

# Existing turbines for training
TURBINES_EXCEL = "analysis/data/Wind_Turbine_Database_en.xlsx"

# Output paths
OUT_SUITABILITY_GEOJSON = "analysis/results/suitability_grid.geojson"
OUT_ML_MODEL = "analysis/results/turbine_model.json"
OUT_TOP_SITES = "analysis/results/top_candidate_sites.geojson"

# Grid resolution for candidate points
GRID_SPACING = 0.05  # ~5km spacing - MIGHT NEED ADJUSTMENT BASED ON PERFORMANCE

# Suitability weights (rule-based scoring)
WEIGHTS = {
    'wind_speed': 0.35,      # Most important: need wind
    'road_proximity': 0.15,  # Access for construction - MIGHT BE LESS IMMPORTANT SINCE ONLY LARGE ROADS ARE INCLUDED
    'hydro_proximity': 0.20, # Connection to grid
    'exclusion': 0.30        # Hard constraints (protected, residential)
}

# Distance thresholds
THRESHOLDS = {
    'min_wind_speed': 6.0,        # m/s minimum
    'max_road_distance': 20.0,    # km - too far = harder to build
    'max_hydro_distance': 50.0,   # km - too far = expensive connection
    'min_protected_distance': 1.0 # km - buffer from parks
}


# ============================================================================
# 1. LOAD ALL DATA
# ============================================================================
print("Loading data layers...")

# Ontario boundary
ontario = gpd.read_file(ONTARIO_BOUNDARY).to_crs("EPSG:4326")
ontario_bounds = ontario.total_bounds  # [minx, miny, maxx, maxy]

# Existing turbines
turbines_df = pd.read_excel(TURBINES_EXCEL)
turbines_gdf = gpd.GeoDataFrame(
    turbines_df,
    geometry=gpd.points_from_xy(turbines_df.Longitude, turbines_df.Latitude),
    crs="EPSG:4326"
)

# Constraint layers - load and immediately project to metric CRS for distance calcs
print("  Loading and projecting constraint layers...")
protected = gpd.read_file(PROTECTED_AREAS).to_crs("EPSG:3347")
residential = gpd.read_file(RESIDENTIAL_BUFFER).to_crs("EPSG:3347")
roads = gpd.read_file(ROADS).to_crs("EPSG:3347")
hydro_stations = gpd.read_file(HYDRO_STATIONS).to_crs("EPSG:3347")
hydro_lines = gpd.read_file(HYDRO_LINES).to_crs("EPSG:3347")

# Combine hydro for proximity calculation
hydro_all = pd.concat([hydro_stations, hydro_lines], ignore_index=True)

# Load wind speed raster
with rasterio.open(WIND_RASTER) as src:
    ontario_geom = ontario.geometry.values
    wind_data, wind_transform = mask(src, ontario_geom, crop=True)
    wind_data = wind_data[0]  # First band
    wind_data = np.where(wind_data < 0, np.nan, wind_data)  # Mask invalid

print(f"✓ Loaded {len(turbines_gdf)} existing turbines")
print(f"✓ Loaded {len(protected)} protected areas")
print(f"✓ Loaded {len(residential)} residential buffers")
print(f"✓ Loaded {len(roads)} road segments")
print(f"✓ Loaded {len(hydro_all)} hydro features")


# ============================================================================
# 2. CREATE CANDIDATE GRID
# ============================================================================
print("\nGenerating candidate grid...")

# Create grid of points across Ontario
minx, miny, maxx, maxy = ontario_bounds
lons = np.arange(minx, maxx, GRID_SPACING)
lats = np.arange(miny, maxy, GRID_SPACING)
lon_grid, lat_grid = np.meshgrid(lons, lats)

# Flatten to list of points
candidate_points = [
    Point(lon, lat) 
    for lon, lat in zip(lon_grid.flatten(), lat_grid.flatten())
]

# Filter to points inside Ontario
candidates_gdf = gpd.GeoDataFrame({'geometry': candidate_points}, crs="EPSG:4326")
candidates_gdf = candidates_gdf[candidates_gdf.within(ontario.union_all())]

print(f"✓ Generated {len(candidates_gdf)} candidate points")


# ============================================================================
# 3. EXTRACT FEATURES FOR EACH CANDIDATE
# ============================================================================
print("\nExtracting features for candidates...")

def get_wind_speed(point, raster_data, transform):
    """Sample wind speed at point from raster."""
    row, col = rasterio.transform.rowcol(transform, point.x, point.y)
    try:
        if 0 <= row < raster_data.shape[0] and 0 <= col < raster_data.shape[1]:
            value = raster_data[row, col]
            return value if not np.isnan(value) else 0
    except:
        pass
    return 0


def get_min_distance_km(point, gdf_proj):
    """Calculate minimum distance from point to any feature in gdf (in km).
    Assumes gdf_proj is already in EPSG:3347."""
    if len(gdf_proj) == 0:
        return 999999
    # Project point to metric CRS for accurate distance
    point_proj = gpd.GeoSeries([point], crs="EPSG:4326").to_crs("EPSG:3347").iloc[0]
    distances = gdf_proj.distance(point_proj)
    return distances.min() / 1000  # meters to km


# Extract features
features = []
for idx, row in candidates_gdf.iterrows():
    point = row.geometry
    
    wind = get_wind_speed(point, wind_data, wind_transform)
    dist_road = get_min_distance_km(point, roads)
    dist_hydro = get_min_distance_km(point, hydro_all)
    dist_protected = get_min_distance_km(point, protected)
    dist_residential = get_min_distance_km(point, residential)
    
    features.append({
        'wind_speed': wind,
        'dist_road_km': dist_road,
        'dist_hydro_km': dist_hydro,
        'dist_protected_km': dist_protected,
        'dist_residential_km': dist_residential,
        'lon': point.x,
        'lat': point.y
    })
    
    if (idx + 1) % 1000 == 0:
        print(f"  Processed {idx + 1}/{len(candidates_gdf)} points...")

candidates_gdf = candidates_gdf.join(pd.DataFrame(features))

print(f"✓ Extracted features for {len(candidates_gdf)} candidates")


# ============================================================================
# 4. RULE-BASED SUITABILITY SCORING
# ============================================================================
print("\nCalculating rule-based suitability scores...")

def normalize(series, min_val, max_val):
    """Normalize series to 0-1 range."""
    return np.clip((series - min_val) / (max_val - min_val), 0, 1)


# Wind speed score (higher = better)
candidates_gdf['wind_score'] = normalize(
    candidates_gdf['wind_speed'], 
    THRESHOLDS['min_wind_speed'], 
    12.0  # max expected
)

# Road proximity score (closer = better, but not too far)
candidates_gdf['road_score'] = 1 - normalize(
    candidates_gdf['dist_road_km'], 
    0, 
    THRESHOLDS['max_road_distance']
)

# Hydro proximity score (closer = better)
candidates_gdf['hydro_score'] = 1 - normalize(
    candidates_gdf['dist_hydro_km'], 
    0, 
    THRESHOLDS['max_hydro_distance']
)

# Exclusion score (hard constraints)
candidates_gdf['exclusion_score'] = (
    (candidates_gdf['dist_protected_km'] >= THRESHOLDS['min_protected_distance']).astype(float) *
    (candidates_gdf['dist_residential_km'] > 0).astype(float)  # Must be outside residential buffer
)

# Combined weighted score
candidates_gdf['suitability_score'] = (
    WEIGHTS['wind_speed'] * candidates_gdf['wind_score'] +
    WEIGHTS['road_proximity'] * candidates_gdf['road_score'] +
    WEIGHTS['hydro_proximity'] * candidates_gdf['hydro_score'] +
    WEIGHTS['exclusion'] * candidates_gdf['exclusion_score']
) * 100  # Scale to 0-100

# Filter out completely unsuitable sites
candidates_gdf['suitable'] = (
    (candidates_gdf['wind_speed'] >= THRESHOLDS['min_wind_speed']) &
    (candidates_gdf['exclusion_score'] == 1)
)

print(f"✓ {candidates_gdf['suitable'].sum()} suitable sites found")
print(f"  Mean suitability score: {candidates_gdf[candidates_gdf['suitable']]['suitability_score'].mean():.1f}")


# ============================================================================
# 5. MACHINE LEARNING MODEL
# ============================================================================
print("\nTraining ML model from existing turbines...")

# Extract features for existing turbines (positive examples)
turbine_features = []
for idx, row in turbines_gdf.iterrows():
    point = row.geometry
    
    wind = get_wind_speed(point, wind_data, wind_transform)
    dist_road = get_min_distance_km(point, roads)
    dist_hydro = get_min_distance_km(point, hydro_all)
    dist_protected = get_min_distance_km(point, protected)
    dist_residential = get_min_distance_km(point, residential)
    
    turbine_features.append({
        'wind_speed': wind,
        'dist_road_km': dist_road,
        'dist_hydro_km': dist_hydro,
        'dist_protected_km': dist_protected,
        'dist_residential_km': dist_residential,
        'has_turbine': 1
    })

# Create negative examples (random non-turbine locations)
suitable_candidates = candidates_gdf[candidates_gdf['suitable']].sample(
    n=min(len(turbines_gdf) * 3, len(candidates_gdf[candidates_gdf['suitable']])),
    random_state=42
)

negative_features = []
for idx, row in suitable_candidates.iterrows():
    negative_features.append({
        'wind_speed': row['wind_speed'],
        'dist_road_km': row['dist_road_km'],
        'dist_hydro_km': row['dist_hydro_km'],
        'dist_protected_km': row['dist_protected_km'],
        'dist_residential_km': row['dist_residential_km'],
        'has_turbine': 0
    })

# Combine positive and negative examples
training_data = pd.DataFrame(turbine_features + negative_features)

# Prepare features and labels
feature_cols = ['wind_speed', 'dist_road_km', 'dist_hydro_km', 'dist_protected_km', 'dist_residential_km']
X = training_data[feature_cols]
y = training_data['has_turbine']

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train Random Forest classifier
model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
y_prob = model.predict_proba(X_test)[:, 1]

print("\n=== ML Model Performance ===")
print(classification_report(y_test, y_pred))
print(f"ROC-AUC Score: {roc_auc_score(y_test, y_prob):.3f}")

# Feature importance
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print("\n=== Feature Importance ===")
print(feature_importance.to_string(index=False))

# Predict on all suitable candidates
suitable_mask = candidates_gdf['suitable']
if suitable_mask.sum() > 0:
    X_candidates = candidates_gdf.loc[suitable_mask, feature_cols]
    ml_predictions = model.predict_proba(X_candidates)[:, 1] * 100  # Scale to 0-100
    candidates_gdf.loc[suitable_mask, 'ml_score'] = ml_predictions
else:
    candidates_gdf['ml_score'] = 0

# Combined final score (average of rule-based and ML)
candidates_gdf['final_score'] = (
    candidates_gdf['suitability_score'] * 0.5 +
    candidates_gdf['ml_score'].fillna(0) * 0.5
)


# ============================================================================
# 6. SAVE RESULTS
# ============================================================================
print("\nSaving results...")

# Save full suitability grid
output_gdf = candidates_gdf[['geometry', 'wind_speed', 'dist_road_km', 'dist_hydro_km', 
                               'dist_protected_km', 'dist_residential_km', 'suitability_score', 
                               'ml_score', 'final_score', 'suitable']]
output_gdf.to_file(OUT_SUITABILITY_GEOJSON, driver="GeoJSON")
print(f"✓ Saved suitability grid → {OUT_SUITABILITY_GEOJSON}")

# Save top 100 candidate sites
top_sites = candidates_gdf[candidates_gdf['suitable']].nlargest(100, 'final_score')
top_sites = top_sites[['geometry', 'wind_speed', 'dist_road_km', 'dist_hydro_km',
                        'suitability_score', 'ml_score', 'final_score']]
top_sites.to_file(OUT_TOP_SITES, driver="GeoJSON")
print(f"✓ Saved top 100 sites → {OUT_TOP_SITES}")

# Save model metadata
model_info = {
    'weights': WEIGHTS,
    'thresholds': THRESHOLDS,
    'feature_importance': feature_importance.to_dict('records'),
    'model_accuracy': float((y_pred == y_test).mean()),
    'roc_auc': float(roc_auc_score(y_test, y_prob)),
    'total_candidates': int(len(candidates_gdf)),
    'suitable_candidates': int(candidates_gdf['suitable'].sum()),
    'mean_final_score': float(candidates_gdf[candidates_gdf['suitable']]['final_score'].mean())
}

with open(OUT_ML_MODEL, 'w') as f:
    json.dump(model_info, f, indent=2)
print(f"✓ Saved model info → {OUT_ML_MODEL}")

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print(f"Total candidate points:    {len(candidates_gdf):,}")
print(f"Suitable locations:        {candidates_gdf['suitable'].sum():,}")
print(f"Mean suitability score:    {candidates_gdf[candidates_gdf['suitable']]['suitability_score'].mean():.1f}/100")
print(f"Mean ML score:             {candidates_gdf[candidates_gdf['suitable']]['ml_score'].mean():.1f}/100")
print(f"Mean final score:          {candidates_gdf[candidates_gdf['suitable']]['final_score'].mean():.1f}/100")
print(f"\nTop site score:            {top_sites['final_score'].max():.1f}/100")
print(f"Top site location:         {top_sites.iloc[0]['geometry'].y:.3f}°N, {top_sites.iloc[0]['geometry'].x:.3f}°W")
print(f"Top site wind speed:       {top_sites.iloc[0]['wind_speed']:.1f} m/s")
print("="*60)
