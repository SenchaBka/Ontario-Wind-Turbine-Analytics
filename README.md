# 🌬️ Ontario Wind Turbine Siting Analysis

A GIS-based suitability analysis for identifying optimal wind turbine placement across Ontario, considering wind resources, grid infrastructure, exclusion zones, terrain, and energy demand.

---

## 📦 Datasets

### Wind Resource
| Dataset | Description | Source |
|---|---|---|
| Global Wind Atlas (GIS) | Wind speed rasters for Ontario — primary wind suitability layer | [globalwindatlas.info](https://globalwindatlas.info/en/download/gis-files) |
| Climate Normals (Environment Canada) | Historical climate averages including wind speed by weather station | [climate.weather.gc.ca](https://climate.weather.gc.ca/climate_normals/index_e.html) |

---

### Built-Up / Residential Areas
| Dataset | Description | Source |
|---|---|---|
| Ontario Built-Up Area | Province-wide layer of man-made/residential land cover — covers southern Ontario | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/built-up-area/explore?location=43.997557%2C-79.332619%2C10) |
| Canada Building Footprints | Building footprints including northern Ontario where Built-Up Area layer has gaps | [open.canada.ca](https://ouvert.canada.ca/data/dataset/79fdad93-9025-49ad-ba16-c26d718cc070/resource/38049b30-86ce-4097-ab28-8ac0b5acd4fe) |

> ⚠️ **AFI:** Find equivalent built-up area dataset for **northern Ontario** to fill coverage gaps in the provincial layer.

---

### Grid Infrastructure
| Dataset | Description | Source |
|---|---|---|
| Utility Site (Hydro Stations) | 395 electrical substations/transformer stations across Ontario — primary grid connection points | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/mnrf::utility-site/explore?location=43.520091%2C-78.756479%2C7) |
| Utility Line (Hydro Lines) | Transmission lines across Ontario — filter to: Hydro Line (1,792) and Unknown Transmission Line (1,659) | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/mnrf::utility-line/explore?location=49.634309%2C-82.752813%2C5) |

---

### Transportation (Accessibility & Setbacks)
| Dataset | Description | Source |
|---|---|---|
| Ontario Road Network (ORN) | Public road rights-of-way — used for both setback exclusion (100m buffer) and accessibility scoring | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/mnrf::ontario-road-network-orn-road-net-element/explore?location=43.637580%2C-79.374191%2C14) |
| Ontario Railway Network (ORWN) | Railway rights-of-way — used for setback exclusion only (blade length + 10m buffer) | [Ontario GeoHub](https://geohub.lio.gov.on.ca/maps/mnrf::ontario-railway-network-orwn/about) |

---

### Exclusion Zones
| Dataset | Description | Source |
|---|---|---|
| Greenbelt Designation | Covers four designations: Niagara Escarpment Plan, Oak Ridges Moraine, Protected Countryside, Urban River Valley — full exclusion | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/greenbelt-designation/explore?location=43.720698%2C-79.410251%2C8) |
| Conservation Reserve Regulated | Provincially regulated conservation reserves — full exclusion under Provincial Parks and Conservation Reserves Act, 2006 | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/a10198b53f894026b92df6828054584d_2/explore?location=49.189941%2C-84.732700%2C4) |
| Provincial Park Regulated | Regulated provincial parks — full exclusion under Provincial Parks and Conservation Reserves Act, 2006 | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/provincial-park-regulated/explore?location=44.368344%2C-78.219877%2C8) |
| Ontario Hydro Network (Water Bodies) | Lakes, rivers, wetlands — full exclusion (offshore wind moratorium + ecological protection) | [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/mnrf::ontario-hydro-network-ohn-waterbody/explore?location=44.356364%2C-79.324936%2C9) |

---

### 🔲 AFIs — Datasets Still Needed

| Layer | Purpose | Suggested Source |
|---|---|---|
| **Built-Up Area — Northern Ontario** | Fill coverage gap in northern Ontario residential areas | Statistics Canada / Ontario PLC 2000 |
| **Local Energy Demand** | Identify high-demand zones to prioritize turbine placement near load centres | IESO Zonal Demand Data + Statistics Canada Census (population density) |
| **Terrain / Slope** | Exclude slopes > 20° and score terrain suitability | Ontario PDEM — [Ontario GeoHub](https://geohub.lio.gov.on.ca/maps/mnrf::provincial-digital-elevation-model-pdem) |
| **Humidity** | Assess atmospheric conditions affecting turbine performance and icing risk | Environment Canada Climate Normals |
| **Land Use Type** | Identify agricultural/rural vs. urban/protected land for siting suitability | SOLRIS (south) + Provincial Land Cover 2000 (north) |
| **Airports & Aerodromes** | Exclusion/avoidance zones — turbines interfere with navigational aids | Ontario GeoHub — search `Airport Aerodrome` |

---

## 🗂️ Analysis Layers Summary

### Suitability Scoring Layers
| Layer | Weight | Notes |
|---|---|---|
| Wind Speed | High | Primary driver of energy output |
| Distance to Hydro Station | High | Grid connection cost proxy |
| Distance to Hydro Line | Medium | Secondary grid proximity |
| Road Accessibility | Medium | Construction and maintenance access |
| Slope | Medium | Foundation and construction cost |
| Energy Demand (AFI) | Low–Medium | Secondary siting factor in Ontario's grid |

### Hard Exclusion Layers (No-Build Zones)
| Layer | Buffer |
|---|---|
| Provincial Parks | Full polygon |
| Conservation Reserves | Full polygon |
| Greenbelt (all designations) | Full polygon |
| Water Bodies | Full polygon |
| Roads | ~100m (blade length + 10m) |
| Railways | ~100m (blade length + 10m) |
| Residential Buildings | 550m (Ontario noise setback regulation) |
| Existing Wind Turbines | 400m (spacing / wake exclusion) |
| Airports & Aerodromes (AFI) | Avoidance zone |

---

## 💡 Key Formulas

### Annual Energy Output
```
AEP (MWh) = Capacity (MW) × 8,760 hrs × Capacity Factor
```

### Physics-Based Power Output
```
P (kW) = 0.5 × 1.225 × π × (rotor_radius)² × wind_speed³ × Cp
```
Where Cp ≈ 0.35–0.45 (turbine efficiency)

### Approximate Total Cost (CAD)
```
Turbine Cost    = MW × $1,800,000
Foundation      = $250,000 × slope_multiplier
Road Access     = road_distance_km × $62,000
Grid Connection = grid_distance_km × $200,000
Transport       = ~$65,000
Subtotal        = sum of above
Soft Costs      = Subtotal × 0.15
─────────────────────────────────────
Total Cost      = Subtotal + Soft Costs
```

---

## 📌 Notes
- Ontario has a **moratorium on offshore wind** (all freshwater lakes) in place since 2011 — analysis is land-based only.
- Ontario's grid is managed by **IESO** — turbine output feeds the provincial grid, not local areas directly. Grid proximity is therefore more important than demand proximity.
- Wind turbine spacing: **400m minimum** (hard exclusion), **1,500m** soft wake interference zone.
