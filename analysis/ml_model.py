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
import shapely
from shapely.strtree import STRtree
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
LAKES = "analysis/results/lakes.geojson"

# Turbine buffer (300m exclusion zone)
TURBINE_BUFFER = "analysis/results/turbine_buffer.geojson"

# Existing turbines for training
TURBINES_EXCEL = "analysis/data/Wind_Turbine_Database_en.xlsx"

# Output paths
OUT_SUITABILITY_GPKG = "analysis/results/suitability_grid.gpkg"
OUT_ML_MODEL = "analysis/results/turbine_model.json"
OUT_TOP_SITES = "analysis/results/top_candidate_sites.geojson"

# Grid resolution for candidate points
GRID_SPACING = 0.01  # ~1km spacing - MIGHT NEED ADJUSTMENT BASED ON PERFORMANCE

# Suitability weights (rule-based scoring)
# Note: hard exclusions (protected areas, residential, lakes) are pre-filtered via spatial join
# before this scoring runs, so no exclusion term is needed here.
WEIGHTS = {
    'wind_speed': 0.60,      # Most important: need wind
    'road_proximity': 0.10,  # Access for construction
    'hydro_proximity': 0.30, # Connection to grid
}

# Distance thresholds
THRESHOLDS = {
    'min_wind_speed': 5.0,        # m/s minimum
    'max_road_distance': 50.0,    # km - too far = harder to build
    'max_hydro_distance': 50.0,   # km - too far = expensive connection
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

lakes = gpd.read_file(LAKES).to_crs("EPSG:4326")
print(f"✓ Loaded {len(lakes)} lake polygons")

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

# Load turbine buffer (as exclusion zone)
turbine_buffer = gpd.read_file(TURBINE_BUFFER).to_crs("EPSG:4326")
print(f"✓ Loaded turbine buffer exclusion zone")


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

# Remove candidates that fall inside lake polygons (can't build on water)
print("  Removing candidates inside lakes...")
in_lakes = gpd.sjoin(candidates_gdf, lakes[["geometry"]], how="inner", predicate="within")
candidates_gdf = candidates_gdf[~candidates_gdf.index.isin(in_lakes.index)]
print(f"  ✓ {len(candidates_gdf)} candidates remain after lake exclusion")

# Remove candidates that fall inside turbine buffer (can't build too close to existing turbines)
print("  Removing candidates inside turbine buffer...")
in_turbine_buffer = gpd.sjoin(candidates_gdf, turbine_buffer[["geometry"]], how="inner", predicate="within")
candidates_gdf = candidates_gdf[~candidates_gdf.index.isin(in_turbine_buffer.index)]
print(f"  ✓ {len(candidates_gdf)} candidates remain after turbine buffer exclusion")

# Pre-filter hard exclusions before the expensive per-point distance loop
print("  Pre-filtering hard exclusion zones...")
before = len(candidates_gdf)

# Remove points directly inside residential buffer
residential_4326 = residential.to_crs("EPSG:4326")
in_res = gpd.sjoin(candidates_gdf, residential_4326[["geometry"]], how="inner", predicate="within")
candidates_gdf = candidates_gdf[~candidates_gdf.index.isin(in_res.index)]

# Remove points directly inside protected areas
protected_4326 = protected.to_crs("EPSG:4326")
in_prot = gpd.sjoin(candidates_gdf, protected_4326[["geometry"]], how="inner", predicate="within")
candidates_gdf = candidates_gdf[~candidates_gdf.index.isin(in_prot.index)]

print(f"  ✓ {len(candidates_gdf)} candidates remain (removed {before - len(candidates_gdf)} excluded points)")


# ============================================================================
# 3. EXTRACT FEATURES FOR EACH CANDIDATE (VECTORIZED)
# ============================================================================
print("\nExtracting features for candidates (vectorized)...")


def bulk_nearest_km(query_geoms_3347, target_gdf_proj):
    """Vectorized nearest-neighbour distances (km) for all query geometries.
    Uses STRtree for O(n log m) performance. Both inputs must be in EPSG:3347."""
    if len(target_gdf_proj) == 0:
        return np.full(len(query_geoms_3347), 999999.0)
    tree = STRtree(target_gdf_proj.geometry.values)
    nearest_idx = tree.nearest(query_geoms_3347)  # vectorized: one call for all points
    nearest_geoms = target_gdf_proj.geometry.values[nearest_idx]
    return shapely.distance(query_geoms_3347, nearest_geoms) / 1000


# Reset index after pre-filtering so array assignment aligns correctly
candidates_gdf = candidates_gdf.reset_index(drop=True)

# Project all candidates to metric CRS once (reused for every distance layer)
candidates_3347 = candidates_gdf.to_crs("EPSG:3347")
geoms_3347 = candidates_3347.geometry.values
    
# Compute distance to nearest existing turbine (for penalty)
turbines_3347 = turbines_gdf.to_crs("EPSG:3347")
candidates_gdf['dist_turbine_km'] = bulk_nearest_km(geoms_3347, turbines_3347)

# Vectorized wind speed: numpy raster index lookup instead of per-point sampling
lons_arr = candidates_gdf.geometry.x.values
lats_arr = candidates_gdf.geometry.y.values
rows, cols = rasterio.transform.rowcol(wind_transform, lons_arr, lats_arr)
rows = np.clip(np.asarray(rows), 0, wind_data.shape[0] - 1)
cols = np.clip(np.asarray(cols), 0, wind_data.shape[1] - 1)
wind_vals = wind_data[rows, cols].astype(float)
candidates_gdf['wind_speed'] = np.where(wind_vals < 0, 0.0, wind_vals)

# Vectorized distances via STRtree bulk nearest-neighbour
print("  Computing road distances...")
candidates_gdf['dist_road_km'] = bulk_nearest_km(geoms_3347, roads)
print("  Computing hydro distances...")
candidates_gdf['dist_hydro_km'] = bulk_nearest_km(geoms_3347, hydro_all)
print("  Computing residential distances...")
candidates_gdf['dist_residential_km'] = bulk_nearest_km(geoms_3347, residential)

candidates_gdf['lon'] = lons_arr
candidates_gdf['lat'] = lats_arr

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

# Combined weighted score
# All remaining candidates are already outside hard exclusion zones (pre-filtered above)
candidates_gdf['suitability_score'] = (
    WEIGHTS['wind_speed'] * candidates_gdf['wind_score'] +
    WEIGHTS['road_proximity'] * candidates_gdf['road_score'] +
    WEIGHTS['hydro_proximity'] * candidates_gdf['hydro_score']
) * 100  # Scale to 0-100
    
# Penalize sites within 10km of a turbine (quadratic dropoff: 0x at 0m, 0.25x at 5km, 1x at 10km+)
penalty = np.clip((candidates_gdf['dist_turbine_km'] / 10.0) ** 2, 0, 1)
candidates_gdf['suitability_score'] *= penalty

# Filter out candidates with insufficient wind
candidates_gdf['suitable'] = candidates_gdf['wind_speed'] >= THRESHOLDS['min_wind_speed']

print(f"✓ {candidates_gdf['suitable'].sum()} suitable sites found")
print(f"  Mean suitability score: {candidates_gdf[candidates_gdf['suitable']]['suitability_score'].mean():.1f}")


# ============================================================================
# 5. MACHINE LEARNING MODEL
# ============================================================================
print("\nTraining ML model from existing turbines...")

# Extract features for existing turbines (positive examples)
# Vectorized turbine feature extraction
turbines_3347 = turbines_gdf.to_crs("EPSG:3347")
t_geoms = turbines_3347.geometry.values
t_lons = turbines_gdf.geometry.x.values
t_lats = turbines_gdf.geometry.y.values
t_rows, t_cols = rasterio.transform.rowcol(wind_transform, t_lons, t_lats)
t_rows = np.clip(np.asarray(t_rows), 0, wind_data.shape[0] - 1)
t_cols = np.clip(np.asarray(t_cols), 0, wind_data.shape[1] - 1)
t_wind = wind_data[t_rows, t_cols].astype(float)
t_wind = np.where(t_wind < 0, 0.0, t_wind)

turbine_features = pd.DataFrame({
    'wind_speed':         t_wind,
    'dist_road_km':       bulk_nearest_km(t_geoms, roads),
    'dist_hydro_km':      bulk_nearest_km(t_geoms, hydro_all),
    'dist_residential_km':bulk_nearest_km(t_geoms, residential),
    'lon':                t_lons,
    'lat':                t_lats,
    'has_turbine':        1,
})

# Create negative examples — sample from ALL candidates (not just suitable)
# This gives the model genuinely non-turbine locations, not just undeveloped good sites
neg_sample = candidates_gdf.sample(
    n=min(len(turbines_gdf) * 3, len(candidates_gdf)),
    random_state=42
)
neg_features = neg_sample[['wind_speed', 'dist_road_km', 'dist_hydro_km',
                            'dist_residential_km', 'lon', 'lat']].copy()
neg_features['has_turbine'] = 0

# Combine positive and negative examples
training_data = pd.concat([turbine_features, neg_features], ignore_index=True)

# Prepare features — include lat/lon so the model learns spatial clustering patterns
# (existing turbines concentrate in specific Ontario regions due to policy/grid access)
feature_cols = ['wind_speed', 'dist_road_km', 'dist_hydro_km', 'dist_residential_km', 'lon', 'lat']
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
                               'dist_residential_km', 'suitability_score', 
                               'ml_score', 'final_score', 'suitable']]
output_gdf.to_file(OUT_SUITABILITY_GPKG, driver="GPKG", layer="suitability")
print(f"✓ Saved suitability grid → {OUT_SUITABILITY_GPKG}")

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
