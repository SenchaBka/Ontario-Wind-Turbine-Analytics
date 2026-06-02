# 🌬️ Ontario Wind Turbine Siting Analysis

A GIS-based suitability analysis for identifying optimal wind turbine placement across Ontario, considering wind resources, grid infrastructure, exclusion zones, terrain, and energy demand.

---

## 📦 Datasets

### Wind Resource

| Dataset                              | Description                                                         | Source                                                                              |
| ------------------------------------ | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Global Wind Atlas (GIS)              | Wind speed rasters for Ontario — primary wind suitability layer     | [globalwindatlas.info](https://globalwindatlas.info/en/download/gis-files)          |
| Climate Normals (Environment Canada) | Historical climate averages including wind speed by weather station | [climate.weather.gc.ca](https://climate.weather.gc.ca/climate_normals/index_e.html) |

---

### Built-Up / Residential Areas

| Dataset                    | Description                                                                       | Source                                                                                                                                     |
| -------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Ontario Built-Up Area      | Province-wide layer of man-made/residential land cover                            | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/built-up-area/explore?location=43.997557%2C-79.332619%2C10)                         |

---

### Grid Infrastructure

| Dataset                       | Description                                                                                             | Source                                                                                                                 |
| ----------------------------- | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Utility Site (Hydro Stations) | 395 electrical substations/transformer stations across Ontario — primary grid connection points         | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/mnrf::utility-site/explore?location=43.520091%2C-78.756479%2C7) |
| Utility Line (Hydro Lines)    | Transmission lines across Ontario — filter to: Hydro Line (1,792) and Unknown Transmission Line (1,659) | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/mnrf::utility-line/explore?location=49.634309%2C-82.752813%2C5) |
| Existing Wind Turbines        | Locations of existing wind turbines across Ontario — used as positive training examples for the ML suitability model | [open.canada.ca](https://ouvert.canada.ca/data/dataset/79fdad93-9025-49ad-ba16-c26d718cc070/resource/38049b30-86ce-4097-ab28-8ac0b5acd4fe) |

---

### Transportation (Accessibility & Setbacks)

| Dataset                        | Description                                                                                         | Source                                                                                                                                               |
| ------------------------------ | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ontario Road Network (ORN)     | Public road rights-of-way — used for both setback exclusion (100m buffer) and accessibility scoring | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/mnrf::ontario-road-network-orn-road-net-element/explore?location=43.637580%2C-79.374191%2C14) |
| Ontario Railway Network (ORWN) | Railway rights-of-way — used for setback exclusion only (blade length + 10m buffer)                 | [Ontario GeoHub](https://geohub.lio.gov.on.ca/maps/mnrf::ontario-railway-network-orwn/about)                                                         |

---

### Exclusion Zones

| Dataset                              | Description                                                                                                                       | Source                                                                                                                                        |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Greenbelt Designation                | Covers four designations: Niagara Escarpment Plan, Oak Ridges Moraine, Protected Countryside, Urban River Valley — full exclusion | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/greenbelt-designation/explore?location=43.720698%2C-79.410251%2C8)                     |
| Conservation Reserve Regulated       | Provincially regulated conservation reserves — full exclusion under Provincial Parks and Conservation Reserves Act, 2006          | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/a10198b53f894026b92df6828054584d_2/explore?location=49.189941%2C-84.732700%2C4)        |
| Provincial Park Regulated            | Regulated provincial parks — full exclusion under Provincial Parks and Conservation Reserves Act, 2006                            | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/provincial-park-regulated/explore?location=44.368344%2C-78.219877%2C8)                 |
| Ontario Hydro Network (Water Bodies) | Lakes, rivers, wetlands — full exclusion (offshore wind moratorium + ecological protection)                                       | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/mnrf::ontario-hydro-network-ohn-waterbody/explore?location=44.356364%2C-79.324936%2C9) |

---

## 🔲 AFIs — Datasets Still Needed

| Layer                                | Purpose                                                                     |
| ------------------------------------ | --------------------------------------------------------------------------- |
| **Built-Up Area — Northern Ontario** | Fill coverage gap in northern Ontario residential areas                     |
| **Local Energy Demand**              | IESO Zonal Demand Data or Population Density — identify high-demand zones   |
| **Humidity**                         | Assess atmospheric conditions affecting turbine performance and icing risk  |
| **Land Use Type**                    | Identify agricultural/rural vs. urban/protected land for siting suitability |

---

## 🗂️ Analysis Layers Summary

### Suitability Scoring Layers

| Layer                     | Weight     | Notes                                     |
| ------------------------- | ---------- | ----------------------------------------- |
| Wind Speed                | High       | Primary driver of energy output           |
| Distance to Hydro Station | High       | Grid connection cost proxy                |
| Distance to Hydro Line    | Medium     | Secondary grid proximity                  |
| Road Accessibility        | Medium     | Construction and maintenance access       |
| Energy Demand (AFI)       | Low–Medium | Secondary siting factor in Ontario's grid |

---

## 🤖 How the ML Suitability Model Works

The wind turbine suitability model combines spatial exclusion logic with a machine learning (ML) classifier to identify optimal sites:

1. **Spatial Exclusion (Pre-filtering):**
   - Removes all candidate points that fall within exclusion zones (lakes, protected areas, residential buffers, turbine buffers, etc.) using fast spatial joins.
   - Only land areas outside these zones are considered for further analysis.

2. **Feature Extraction:**
   - For each candidate site, calculates features such as wind speed, distance to nearest hydro station, distance to nearest hydro line, and road accessibility.
   - Uses vectorized spatial operations and STRtree for efficient nearest-neighbor calculations.

3. **Rule-Based Scoring:**
   - Assigns a suitability score to each site based on weighted factors (e.g., wind speed, grid proximity, road access).
   - Hard thresholds (e.g., minimum wind speed) are applied to further filter out poor sites.

4. **ML Classification:**
   - Trains a Random Forest classifier using known turbine locations (positive examples) and random non-turbine sites (negatives).
   - Predicts the likelihood of suitability for each candidate site based on extracted features.

5. **Penalty Logic:**
   - Applies penalties to sites that are too close to existing turbines (within 1.5 km), reducing their final score to avoid wake interference.

6. **Output:**
   - Ranks all remaining candidate sites by final score (combining rule-based and ML predictions).
   - Outputs the top N sites as GeoJSON for frontend visualization, including all relevant properties and cost estimates.

This hybrid approach ensures that only technically, environmentally, and economically viable sites are selected for wind turbine development.

---

## 📌 Notes

- Ontario has a **moratorium on offshore wind** (all freshwater lakes) in place since 2011 — analysis is land-based only.
- Ontario's grid is managed by **IESO** — turbine output feeds the provincial grid, not local areas directly. Grid proximity is therefore more important than demand proximity.
- Wind turbine spacing: **300m minimum** (hard exclusion), **1,500m** soft wake interference zone.

---

## How to Run the Project

1. **Start the Backend API**
   - Open a terminal in the `backend` directory:
     ```sh
     cd backend
     python app.py
     ```

2. **Open the Frontend**
   - Open `frontend/index.html` in your web browser.

3. **Install Required Libraries for Analysis**
   - In the project root directory, install all Python dependencies:
     ```sh
     pip install -r requirements.txt
     ```
   - This will ensure all necessary libraries are available to run the analysis scripts.
