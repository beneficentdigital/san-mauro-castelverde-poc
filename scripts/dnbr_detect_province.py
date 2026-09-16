"""Province-wide dNBR burn detection: automated version of dnbr_detect.py's
validated pilot method, generalized to pick before/after imagery automatically
per fire rather than hand-curated dates (impractical for 588 fires).

Per fire: search for the least-cloudy scene in a window before the fire date
and another after it, compute dNBR, clean speckle, and report the patch
nearest the fire's own centroid (not a whole-chip total - see dnbr_detect.py
for why that matters, confirmed on the San Mauro Castelverde pilot).

RdNBR was tried on the pilot and rejected (underperformed plain dNBR at the
one location with solid ground truth) - this uses plain dNBR only.
"""
from __future__ import annotations

import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform as warp_transform
from rasterio.windows import Window
from shapely.geometry import Point, shape as shapely_shape

FIRES = "data/processed/effis_palermo_province_2018_2025.geojson"
OUT = "data/processed/dnbr_province_results.csv"
OUT_POLYS = "data/processed/dnbr_province_detections.geojson"

CHIP_SIZE = 512
HLS_NODATA = -9999
DNBR_BURN_THRESHOLD = 0.10
SEARCH_WINDOW_DAYS = 60
NEARBY_RADIUS_M = 1000  # candidate patches considered "at" the fire, not just the single nearest pixel-patch

_catalog = None


def get_catalog():
    global _catalog
    if _catalog is None:
        _catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1", modifier=planetary_computer.sign_inplace
        )
    return _catalog


def find_scenes(lon, lat, date_start, date_end):
    """Return ALL candidate scenes sorted by cloud cover, not just the single
    best - a point near an MGRS tile edge is covered by more than one tile,
    and the lowest-cloud scene isn't always the one whose raster window
    actually contains our chip. Trying the next-best candidate when the top
    one fails is the fix for the ~30% 'window outside tile bounds' failures
    seen in the first province-wide run."""
    search = get_catalog().search(
        collections=["hls2-s30"], bbox=[lon - 0.02, lat - 0.02, lon + 0.02, lat + 0.02],
        datetime=f"{date_start}/{date_end}",
    )
    items = list(search.items())
    items.sort(key=lambda i: i.properties.get("eo:cloud_cover", 100))
    return items


def fetch_scene_bands(candidates, center_lon, center_lat):
    """Try each candidate scene in order until one's raster window actually
    covers our chip. Returns (nir, swir, meta, item) from whichever succeeds."""
    last_error = None
    for item in candidates:
        try:
            nir, meta = fetch_band(item, "B08", center_lon, center_lat)
            swir, _ = fetch_band(item, "B12", center_lon, center_lat)
            return nir, swir, meta, item
        except ValueError as e:
            last_error = e
            continue
    raise ValueError(f"no candidate scene covers this location ({len(candidates)} tried): {last_error}")


def fetch_band(item, band, center_lon, center_lat, chip_size=CHIP_SIZE):
    href = item.assets[band].href
    with rasterio.open(href) as src:
        lon, lat = warp_transform("EPSG:4326", src.crs, [center_lon], [center_lat])
        col, row = ~src.transform * (lon[0], lat[0])
        col, row = int(col), int(row)
        half = chip_size // 2
        if not (half <= col <= src.width - half and half <= row <= src.height - half):
            raise ValueError("window outside tile bounds")
        window = Window(col - half, row - half, chip_size, chip_size)
        arr = src.read(1, window=window).astype("float32")
        arr[arr == HLS_NODATA] = np.nan
        meta = src.meta.copy()
        meta.update(height=chip_size, width=chip_size, count=1, dtype="float32",
                     transform=rasterio.windows.transform(window, src.transform))
    fmask_href = item.assets["Fmask"].href
    with rasterio.open(fmask_href) as src:
        lon, lat = warp_transform("EPSG:4326", src.crs, [center_lon], [center_lat])
        col, row = ~src.transform * (lon[0], lat[0])
        col, row = int(col), int(row)
        half = chip_size // 2
        window = Window(col - half, row - half, chip_size, chip_size)
        fmask = src.read(1, window=window)
    cloud_or_shadow = ((fmask >> 1) & 1).astype(bool) | ((fmask >> 3) & 1).astype(bool)
    arr[cloud_or_shadow] = np.nan
    return arr, meta


def compute_nbr(nir, swir2):
    denom = nir + swir2
    with np.errstate(invalid="ignore", divide="ignore"):
        nbr = (nir - swir2) / denom
    nbr[np.abs(nbr) > 1.5] = np.nan
    return nbr


def clean_burn_mask(mask, min_pixels=2):
    from scipy import ndimage
    labeled, n = ndimage.label(mask)
    sizes = ndimage.sum(mask, labeled, range(1, n + 1))
    keep = np.isin(labeled, np.where(sizes >= min_pixels)[0] + 1)
    return keep.astype("uint8")


def process_fire(fire_id, comune, fire_date, area_ha_effis, center_lon, center_lat):
    pre_date_start = (fire_date - pd.Timedelta(days=SEARCH_WINDOW_DAYS)).strftime("%Y-%m-%d")
    pre_date_end = fire_date.strftime("%Y-%m-%d")
    post_date_start = fire_date.strftime("%Y-%m-%d")
    post_date_end = (fire_date + pd.Timedelta(days=SEARCH_WINDOW_DAYS)).strftime("%Y-%m-%d")

    pre_candidates = find_scenes(center_lon, center_lat, pre_date_start, pre_date_end)
    post_candidates = find_scenes(center_lon, center_lat, post_date_start, post_date_end)
    if not pre_candidates or not post_candidates:
        return {"fire_id": fire_id, "status": "no_imagery_found"}

    try:
        pre_nir, pre_swir, meta, pre_item = fetch_scene_bands(pre_candidates, center_lon, center_lat)
        post_nir, post_swir, _, post_item = fetch_scene_bands(post_candidates, center_lon, center_lat)
    except ValueError:
        return {"fire_id": fire_id, "status": "no_covering_tile"}

    nbr_pre = compute_nbr(pre_nir, pre_swir)
    nbr_post = compute_nbr(post_nir, post_swir)
    dnbr = nbr_pre - nbr_post
    raw_mask = (dnbr > DNBR_BURN_THRESHOLD).astype("uint8")
    burn_mask = clean_burn_mask(raw_mask)

    polys = []
    for geom, val in shapes(burn_mask, mask=burn_mask > 0, transform=meta["transform"]):
        polys.append(shapely_shape(rasterio.warp.transform_geom(meta["crs"], "EPSG:4326", geom)))

    if not polys:
        return {"fire_id": fire_id, "status": "no_burn_detected"}

    gdf_m = gpd.GeoDataFrame(geometry=polys, crs="EPSG:4326").to_crs("EPSG:32633")
    query_pt_m = gpd.GeoSeries([Point(center_lon, center_lat)], crs="EPSG:4326").to_crs("EPSG:32633").iloc[0]
    gdf_m["dist_m"] = gdf_m.geometry.distance(query_pt_m)
    nearby = gdf_m[gdf_m["dist_m"] <= NEARBY_RADIUS_M]

    return {
        "fire_id": fire_id, "comune": comune, "fire_date": str(fire_date), "area_ha_effis": area_ha_effis,
        "status": "ok",
        "dnbr_area_ha_within_1km": round(nearby.geometry.area.sum() / 1e4, 2) if len(nearby) else 0.0,
        "dnbr_nearest_patch_ha": round(gdf_m.loc[gdf_m["dist_m"].idxmin(), "geometry"].area / 1e4, 2),
        "dnbr_nearest_dist_m": round(gdf_m["dist_m"].min()),
        "pre_scene": pre_item.id, "post_scene": post_item.id,
        "pre_cloud_pct": pre_item.properties.get("eo:cloud_cover"),
        "post_cloud_pct": post_item.properties.get("eo:cloud_cover"),
    }, gpd.GeoDataFrame(geometry=nearby.to_crs("EPSG:4326").geometry, crs="EPSG:4326").assign(fire_id=fire_id) if len(nearby) else None


def _run_one(fire):
    t0 = time.time()
    centroid = fire.geometry.centroid
    try:
        out = process_fire(fire["id"], fire["COMMUNE"], fire["FIREDATE"], fire["AREA_HA"], centroid.x, centroid.y)
        if isinstance(out, tuple):
            row, polys = out
        else:
            row, polys = out, None
    except Exception as e:
        row, polys = {"fire_id": fire["id"], "status": f"error: {e}"}, None
        traceback.print_exc(file=sys.stderr)
    row["elapsed_s"] = round(time.time() - t0, 1)
    return row, polys


def main(max_area_ha=50, limit=None, workers=8):
    fires = gpd.read_file(FIRES).to_crs("EPSG:4326").drop_duplicates(subset="id").reset_index(drop=True)
    fires["FIREDATE"] = pd.to_datetime(fires["FIREDATE"])
    fires["AREA_HA"] = fires["AREA_HA"].astype(float)
    if max_area_ha:
        fires = fires[fires["AREA_HA"] <= max_area_ha].reset_index(drop=True)
    if limit:
        fires = fires.head(limit)
    print(f"Running dNBR on {len(fires)} fires (<={max_area_ha}ha) with {workers} parallel workers")

    results = []
    all_polys = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_run_one, fire): fire for _, fire in fires.iterrows()}
        for fut in as_completed(futures):
            fire = futures[fut]
            row, polys = fut.result()
            if polys is not None and len(polys):
                all_polys.append(polys)
            results.append(row)
            done += 1
            print(f"  [{done}/{len(fires)}] fire {fire['id']} ({fire['COMMUNE']}, {fire['AREA_HA']}ha): "
                  f"{row.get('status')} in {row.get('elapsed_s')}s", flush=True)

            if done % 10 == 0 or done == len(fires):
                pd.DataFrame(results).to_csv(OUT, index=False)
                if all_polys:
                    gpd.GeoDataFrame(pd.concat(all_polys, ignore_index=True), crs="EPSG:4326").to_file(OUT_POLYS, driver="GeoJSON")

    df = pd.DataFrame(results)
    ok = df[df["status"] == "ok"]
    print(f"\n{len(ok)}/{len(df)} fires processed successfully")
    print(df["status"].value_counts())


if __name__ == "__main__":
    max_area = float(sys.argv[1]) if len(sys.argv) > 1 else 50
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    main(max_area_ha=max_area, limit=limit)
