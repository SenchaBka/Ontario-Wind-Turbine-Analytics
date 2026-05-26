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

All outputs are saved in the `data/` or `results/` subfolders for use by the backend and frontend.
