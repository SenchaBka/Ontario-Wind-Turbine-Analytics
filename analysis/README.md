# Analysis Folder Overview

This folder contains all scripts and notebooks for spatial data processing, feature extraction, and wind turbine site suitability modeling. Below is a concise summary of each file:

---

## residential_areas.py
- **Purpose:** Buffers built-up (residential) areas by 550m, dissolves into a single exclusion zone, simplifies geometry, and exports as a GeoPackage.
- **Use:** Provides exclusion zones for spatial filtering in the suitability model.

## wind_speed.py
- **Purpose:** Reads Canada-wide wind speed raster, clips to Ontario, downsamples, and generates a color-coded overlay for mapping wind resource suitability.
- **Use:** Produces wind speed overlays and data for visualization and analysis.

## ml_model.py
- **Purpose:** Main wind turbine suitability model. Combines rule-based spatial exclusion (lakes, protected, residential, turbine buffer, etc.) with a machine learning classifier trained on existing turbines.
- **Use:** Outputs top candidate sites for frontend display and further analysis.

## Detailed Logic: ml_model.py (Suitability Model)

1. **Data Loading & Preparation**
   - Loads all spatial layers (Ontario boundary, protected areas, residential buffers, roads, hydro stations/lines, lakes, existing turbines) and wind speed raster.
   - Projects all vector layers to a metric CRS (EPSG:3347) for accurate distance calculations.

2. **Candidate Grid Generation**
   - Creates a regular grid of candidate points (~2km spacing) covering all of Ontario.
   - Filters points to those within the Ontario boundary.

3. **Spatial Exclusion (Hard Filters)**
   - Removes candidates inside lakes, turbine buffer zones (300m), residential buffers, and protected areas using fast spatial joins.
   - Only land areas outside all exclusion zones are kept for further analysis.

4. **Feature Extraction (Vectorized)**
   - For each candidate, calculates:
     - Wind speed (from raster, using fast index lookup)
     - Distance to nearest road, hydro station/line, residential area, and turbine (using STRtree spatial index for speed)
     - Latitude/longitude (for spatial ML patterns)

5. **Rule-Based Scoring**
   - Computes a weighted suitability score for each candidate:
     - Wind speed (60%), road proximity (10%), hydro proximity (30%)
     - Scores are normalized (0–1) and combined, then scaled to 0–100.
   - Applies a quadratic penalty to sites within 1.5km of an existing turbine (to avoid wake interference).
   - Filters out sites with wind speed below a minimum threshold (6.0 m/s).

6. **Machine Learning Model**
   - Trains a Random Forest classifier using features from existing turbines (positives) and random non-turbine sites (negatives).
   - Features: wind speed, distances, lat/lon (to capture spatial clustering).
   - Evaluates model performance (accuracy, ROC-AUC, feature importance).
   - Predicts ML suitability score (0–100) for all remaining candidates.

7. **Final Scoring & Output**
   - Combines rule-based and ML scores (average) for a final score.
   - Ranks all suitable sites and outputs the top N (e.g., 1000) as GeoJSON for frontend display.
   - Saves the full suitability grid and model metadata for reproducibility.

This approach ensures only technically, environmentally, and economically viable wind turbine sites are selected, using both expert rules and data-driven ML insights.

## plot_turbines.ipynb
- **Purpose:** Loads turbine database, filters for Ontario, creates GeoJSON of turbine locations, and generates a 300m exclusion buffer around each turbine.
- **Use:** Supplies turbine locations and exclusion buffers for penalty/exclusion logic in the model.

## plot_wind_dir.ipynb
- **Purpose:** Visualizes wind direction and speed at climate stations using interactive map with arrow icons, and overlays wind speed raster for Ontario.
- **Use:** Produces wind direction/speed visualizations for exploratory analysis.

## roads.py
- **Purpose:** Extracts major roads (freeway, highway, arterial) from geodatabase, removes arterials inside built-up areas, and exports filtered road network.
- **Use:** Provides road network data for cost and access calculations in the suitability model.

---

All outputs are saved in the `data/` or `api/` subfolders for use by the backend and frontend.
