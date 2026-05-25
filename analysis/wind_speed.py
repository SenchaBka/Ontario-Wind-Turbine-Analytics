"""
wind_speed.py
Reads CAN_wind-speed_100m.tif (GeoTIFF, EPSG:4326, Canada-wide),
clips to Ontario, downsamples, and renders an interactive Folium
map with a colour-coded image overlay saved to wind_speed_map.html.
"""

import io
import os
import json
import base64
import numpy as np
from PIL import Image
import rasterio
from rasterio.windows import from_bounds
from rasterio.transform import array_bounds, from_bounds as transform_from_bounds
from rasterio.features import geometry_mask
from rasterio.crs import CRS
from rasterio.warp import reproject, calculate_default_transform, Resampling as WarpResampling
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import folium

# ---------------------------------------------------------------------------
# 1.  File paths
# ---------------------------------------------------------------------------
TIF_PATH        = "data/CAN_wind-speed_100m.tif"
ONTARIO_CACHE   = "data/ontario_boundary.gpkg"   # cached after first run
OUT_HTML        = "wind_speed_map.html"
OUT_PNG         = "wind_speed_overlay.png"
OUT_JSON        = "wind_speed_overlay.json"

# ---------------------------------------------------------------------------
# 2.  Ontario bounding box (EPSG:4326)
# ---------------------------------------------------------------------------
ON_WEST, ON_EAST   = -95.16, -74.34
ON_SOUTH, ON_NORTH = 41.67,   56.87

# ---------------------------------------------------------------------------
# 2b. Ontario boundary polygon (Natural Earth 1:10m, cached locally)
# ---------------------------------------------------------------------------
def get_ontario_geometry():
    if os.path.exists(ONTARIO_CACHE):
        gdf = gpd.read_file(ONTARIO_CACHE)
    else:
        print("Downloading province boundaries (one-time, ~10 MB)…")
        url = ("https://naturalearth.s3.amazonaws.com/10m_cultural/"
               "ne_10m_admin_1_states_provinces.zip")
        provinces = gpd.read_file(url)
        ontario   = provinces[provinces["name"] == "Ontario"].to_crs("EPSG:4326")
        ontario[["geometry"]].to_file(ONTARIO_CACHE, driver="GPKG")
        gdf = ontario[["geometry"]]
    return gdf.geometry.iloc[0]

ontario_geom = get_ontario_geometry()
print("Ontario boundary loaded.")

# ---------------------------------------------------------------------------
# 3.  Read the raster clipped to Ontario, downsampled to ≤ 2000 px per side
# ---------------------------------------------------------------------------
MAX_PX = 2000

with rasterio.open(TIF_PATH) as src:
    window = from_bounds(ON_WEST, ON_SOUTH, ON_EAST, ON_NORTH, src.transform)

    # How many native pixels in the window?
    native_h = int(window.height)
    native_w = int(window.width)

    # Compute the actual geographic bounds after pixel-grid snapping
    win_transform = rasterio.windows.transform(window, src.transform)
    actual_west, actual_south, actual_east, actual_north = array_bounds(
        native_h, native_w, win_transform
    )

    scale = max(native_h / MAX_PX, native_w / MAX_PX)
    out_h  = max(1, int(native_h / scale))
    out_w  = max(1, int(native_w / scale))

    data = src.read(
        1,
        window=window,
        out_shape=(out_h, out_w),
        resampling=rasterio.enums.Resampling.average,
    ).astype(np.float32)

valid_min = float(np.nanmin(data))
valid_max = float(np.nanmax(data))
valid_mean = float(np.nanmean(data))

print(f"Ontario window  : {native_w} × {native_h} native pixels")
print(f"Downsampled to  : {out_w} × {out_h} pixels  (scale ≈ {scale:.1f}×)")
print(f"Wind speed range: {valid_min:.2f} – {valid_max:.2f} m/s")
print(f"Mean wind speed : {valid_mean:.2f} m/s")

# ---------------------------------------------------------------------------
# 3b. Mask to Ontario's actual political boundary
#     Without this, the rectangular window includes Quebec, Manitoba, and US
#     states that share the same bounding box.
# ---------------------------------------------------------------------------
src_transform_ds = transform_from_bounds(
    actual_west, actual_south, actual_east, actual_north, out_w, out_h
)

outside_ontario = geometry_mask(
    [ontario_geom],
    out_shape=(out_h, out_w),
    transform=src_transform_ds,
    invert=False,   # True = outside the polygon → set to NaN
)
data[outside_ontario] = np.nan

# Recompute stats after masking (only Ontario land pixels)
valid_min  = float(np.nanmin(data))
valid_max  = float(np.nanmax(data))
valid_mean = float(np.nanmean(data))
print(f"After masking   : range {valid_min:.2f}–{valid_max:.2f} m/s, "
      f"mean {valid_mean:.2f} m/s")

# ---------------------------------------------------------------------------
# 4.  Reproject downsampled data to EPSG:3857 (Web Mercator)
# ---------------------------------------------------------------------------
src_crs = CRS.from_epsg(4326)
dst_crs = CRS.from_epsg(3857)

# src_transform_ds already computed in step 3b
# Calculate the output Mercator transform / size
dst_transform, dst_width, dst_height = calculate_default_transform(
    src_crs, dst_crs, out_w, out_h,
    left=actual_west, bottom=actual_south,
    right=actual_east, top=actual_north,
)

data_merc = np.full((dst_height, dst_width), np.nan, dtype=np.float32)
reproject(
    source=data,
    destination=data_merc,
    src_transform=src_transform_ds,
    src_crs=src_crs,
    dst_transform=dst_transform,
    dst_crs=dst_crs,
    resampling=WarpResampling.bilinear,
    src_nodata=np.nan,
    dst_nodata=np.nan,
)
print(f"Reprojected to  : {dst_width} × {dst_height} px (EPSG:3857)")

# ---------------------------------------------------------------------------
# 5.  Build a colour-mapped RGBA PNG (transparent where NaN)
# ---------------------------------------------------------------------------
norm  = mcolors.Normalize(vmin=valid_min, vmax=valid_max)
cmap  = plt.get_cmap("RdYlGn")          # red = low, green = high
rgba  = cmap(norm(np.nan_to_num(data_merc, nan=valid_min)))  # (H, W, 4)

# Make NaN pixels fully transparent
nan_mask = np.isnan(data_merc)
rgba[nan_mask, 3] = 0.0

# Convert to uint8
rgba_u8 = (rgba * 255).astype(np.uint8)

# ------------------------------------------------------------------
# Save PNG to disk (high-quality, reusable by the frontend)
# ------------------------------------------------------------------
pil_img = Image.fromarray(rgba_u8, mode="RGBA")
pil_img.save(OUT_PNG, format="PNG", optimize=True, compress_level=6)
print(f"PNG saved   → {OUT_PNG}  ({os.path.getsize(OUT_PNG) / 1024:.0f} KB)")

# Save bounds + colour-scale metadata so the frontend knows where to place
# the image and how to render the legend without recomputing anything.
metadata = {
    "bounds": [[actual_south, actual_west], [actual_north, actual_east]],
    "vmin":   round(valid_min,  3),
    "vmax":   round(valid_max,  3),
    "vmean":  round(valid_mean, 3),
    "image":  OUT_PNG,
    "width":  dst_width,
    "height": dst_height,
    "cmap":   "RdYlGn",
}
with open(OUT_JSON, "w") as _f:
    json.dump(metadata, _f, indent=2)
print(f"JSON saved  → {OUT_JSON}")

# Encode as base64 for the self-contained standalone HTML
buf = io.BytesIO()
pil_img.save(buf, format="PNG")
buf.seek(0)
img_b64 = base64.b64encode(buf.read()).decode("utf-8")
img_src  = f"data:image/png;base64,{img_b64}"

# ---------------------------------------------------------------------------
# 6.  Also produce a legend PNG
# ---------------------------------------------------------------------------
fig_leg, ax_leg = plt.subplots(figsize=(5, 0.5))
fig_leg.subplots_adjust(bottom=0.5)
cb = matplotlib.colorbar.ColorbarBase(
    ax_leg,
    cmap=cmap,
    norm=norm,
    orientation="horizontal",
)
cb.set_label("Wind Speed at 100 m (m/s)", fontsize=9)
buf_leg = io.BytesIO()
fig_leg.savefig(buf_leg, format="png", bbox_inches="tight", dpi=120)
plt.close(fig_leg)
buf_leg.seek(0)
leg_b64 = base64.b64encode(buf_leg.read()).decode("utf-8")

# ---------------------------------------------------------------------------
# 7.  Build Folium map
# ---------------------------------------------------------------------------
centre_lat = (ON_SOUTH + ON_NORTH) / 2
centre_lon = (ON_WEST  + ON_EAST)  / 2

m = folium.Map(
    location=[centre_lat, centre_lon],
    zoom_start=5,
    tiles="CartoDB positron",
)

# Wind-speed raster overlay
folium.raster_layers.ImageOverlay(
    image=img_src,
    bounds=[[actual_south, actual_west], [actual_north, actual_east]],
    opacity=0.7,
    interactive=True,
    cross_origin=False,
    name="Wind Speed 100 m",
).add_to(m)

# Layer control so users can toggle the overlay
folium.LayerControl(collapsed=False).add_to(m)

# Legend as a floating HTML element
legend_html = f"""
<div style="
    position: fixed;
    bottom: 30px; left: 50%;
    transform: translateX(-50%);
    z-index: 9999;
    background: rgba(255,255,255,0.9);
    padding: 8px 14px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    font-family: sans-serif;
    font-size: 12px;
    text-align: center;
">
  <b>Wind Speed at 100 m (m/s)</b><br>
  <img src="data:image/png;base64,{leg_b64}" style="width:320px;margin-top:4px;">
  <br>
  <span style="color:#888;font-size:10px;">
    Ontario · Range {valid_min:.1f}–{valid_max:.1f} m/s · Mean {valid_mean:.1f} m/s
  </span>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# Stats popup in the title bar
title_html = """
<div style="
    position: fixed;
    top: 10px; left: 50%;
    transform: translateX(-50%);
    z-index: 9999;
    background: rgba(26,26,46,0.88);
    color: white;
    padding: 8px 20px;
    border-radius: 8px;
    font-family: sans-serif;
    font-size: 14px;
    font-weight: 600;
    pointer-events: none;
">
  Ontario Wind Speed at 100 m — Annual Mean
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

m.save(OUT_HTML)
print(f"\nMap saved → {OUT_HTML}")
