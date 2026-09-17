"""dNBR (differenced Normalized Burn Ratio) burn detection - a classical,
non-ML remote sensing technique, not a trained model. NBR = (NIR - SWIR2) /
(NIR + SWIR2); dNBR = NBR_prefire - NBR_postfire. Higher dNBR = more severe
burn. Thresholds below are the standard USGS/Key & Benson (2006) FIREMON
scale, widely used globally - not fitted to any particular continent's
training data the way Prithvi is, which is exactly why this is worth trying
for the small fires EFFIS and Prithvi both struggle with precisely.

Built to answer a direct question: does this catch San Mauro Castelverde's
two known 2023 fires more precisely than Prithvi did? Same two locations,
same validation standard, so the comparison is apples-to-apples.
"""
import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform as warp_transform
from rasterio.windows import Window
from shapely.geometry import shape as shapely_shape
import geopandas as gpd

CHIP_SIZE = 512  # matches the Prithvi chips, 30m HLS resolution
# dNBR severity thresholds, Key & Benson (2006) - not fitted to any one region
DNBR_BURN_THRESHOLD = 0.10  # low-severity-or-greater cutoff; conservative, catches small/patchy burns


HLS_NODATA = -9999
HLS_SCALE_FACTOR = 0.0001  # HLS S30 surface reflectance is stored as int16 DN;
# BAIS2 (unlike NBR/dNBR) is NOT scale-invariant - it mixes a 3-band product
# against a 1-band term, so raw DNs must be converted to true 0-1 reflectance
# or the index comes out numerically wrong, not just rescaled.

# BAIS2 (Filipponi 2018, "Burned Area Index for Sentinel-2") - a single-date
# post-fire index, not a pre/post difference like dNBR. Verified formula:
# BAIS2 = (1 - sqrt((B06*B07*B8A)/B04)) * ((B12-B8A)/sqrt(B12+B8A) + 1)
# Threshold 0.865 is Filipponi's own calibration for a Sicily wildfire case
# (July 2017) - the closest published value to our exact use case, so used
# as-is rather than the more generic >0.90 seen elsewhere in the literature.
BAIS2_BURN_THRESHOLD = 0.865


def fetch_band(item_id, band, center_lon, center_lat, chip_size=CHIP_SIZE):
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    item = list(catalog.search(collections=["hls2-s30"], ids=[item_id]).items())[0]
    href = item.assets[band].href
    with rasterio.open(href) as src:
        lon, lat = warp_transform("EPSG:4326", src.crs, [center_lon], [center_lat])
        col, row = ~src.transform * (lon[0], lat[0])
        col, row = int(col), int(row)
        half = chip_size // 2
        if not (half <= col <= src.width - half and half <= row <= src.height - half):
            raise ValueError(f"{item_id}: window falls outside tile bounds, pick a neighbouring tile")
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
    cloud_or_shadow = ((fmask >> 1) & 1).astype(bool) | ((fmask >> 3) & 1).astype(bool)  # bit1=cloud, bit3=shadow
    arr[cloud_or_shadow] = np.nan

    return arr, meta


def compute_nbr(nir, swir2):
    denom = nir + swir2
    with np.errstate(invalid="ignore", divide="ignore"):
        nbr = (nir - swir2) / denom
    nbr[np.abs(nbr) > 1.5] = np.nan  # NBR is mathematically bounded to [-1,1]; anything beyond is bad data, not signal
    return nbr


def compute_bais2(b06, b07, b8a, b04, b12):
    """BAIS2 (Filipponi 2018). Inputs must already be scaled to true 0-1
    reflectance (see HLS_SCALE_FACTOR) - unlike NBR this formula is not
    scale-invariant. Designed to run on a single post-fire scene: high
    values flag char/ash directly, no pre-fire baseline needed, which
    sidesteps dNBR/RdNBR's seasonal-vegetation-drying false positives
    (there's no pre-fire image to be thrown off by)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        term1 = 1 - np.sqrt((b06 * b07 * b8a) / b04)
        term2 = (b12 - b8a) / np.sqrt(b12 + b8a) + 1
        bais2 = term1 * term2
    bais2[~np.isfinite(bais2)] = np.nan
    return bais2


MIN_PREFIRE_NBR = 100  # x1000 scale; below this the RdNBR formula is numerically
# unstable (denominator -> 0) over bare rock/very sparse ground - plausible over
# Sicilian karst terrain - so those pixels are excluded rather than risking a
# spurious spike being read as a burn


def compute_rdnbr(dnbr, nbr_pre):
    """Relative dNBR (Miller & Thode 2007): normalizes dNBR by pre-fire vegetation
    density, correcting the bias where sparse vegetation (scrub/maquia) shows a
    smaller absolute dNBR than dense woodland for the same real burn severity -
    exactly the effect behind the Pollina under-detection (mixed cork-oak/
    sclerophyll scrub vs Tiberio's denser, more uniform woodland)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        rdnbr = dnbr / np.sqrt(np.abs(nbr_pre) / 1000)
    rdnbr[~np.isfinite(rdnbr)] = np.nan
    rdnbr[np.abs(nbr_pre) < MIN_PREFIRE_NBR] = np.nan
    return rdnbr


def clean_burn_mask(mask, min_pixels=2):
    """Minimum-mapping-unit cleanup: drop speckle below min_pixels (~0.18ha at
    30m/px). Tried adding a morphological closing step to merge nearby
    fragments too (standard practice) - rejected, it merged the real fire
    patch with nearby unrelated noise into one bloated blob (Tiberio's clean
    1.35ha result became a false 105ha after closing). Speckle removal alone
    is safe; fragment-merging isn't, at least not with a fixed structuring
    element - would need a smarter approach to attempt that again."""
    from scipy import ndimage
    labeled, n = ndimage.label(mask)
    sizes = ndimage.sum(mask, labeled, range(1, n + 1))
    keep = np.isin(labeled, np.where(sizes >= min_pixels)[0] + 1)
    return keep.astype("uint8")


RDNBR_BURN_THRESHOLD = 100  # Miller & Thode (2007) convention, NBR scaled x1000


def run_dnbr(pre_item, post_item, center_lon, center_lat, label, out_prefix, use_rdnbr=True):
    pre_nir, meta = fetch_band(pre_item, "B08", center_lon, center_lat)
    pre_swir, _ = fetch_band(pre_item, "B12", center_lon, center_lat)
    post_nir, _ = fetch_band(post_item, "B08", center_lon, center_lat)
    post_swir, _ = fetch_band(post_item, "B12", center_lon, center_lat)

    nbr_pre = compute_nbr(pre_nir, pre_swir)
    nbr_post = compute_nbr(post_nir, post_swir)
    dnbr = nbr_pre - nbr_post

    if use_rdnbr:
        rdnbr = compute_rdnbr(dnbr * 1000, nbr_pre * 1000)
        raw_mask = (rdnbr > RDNBR_BURN_THRESHOLD).astype("uint8")
        raw_mask[np.isnan(rdnbr)] = 0
    else:
        raw_mask = (dnbr > DNBR_BURN_THRESHOLD).astype("uint8")

    burn_mask = clean_burn_mask(raw_mask)

    polys = []
    for geom, val in shapes(burn_mask, mask=burn_mask > 0, transform=meta["transform"]):
        geom_wgs84 = rasterio.warp.transform_geom(meta["crs"], "EPSG:4326", geom)
        polys.append(shapely_shape(geom_wgs84))

    if not polys:
        print(f"{label}: no burn detected above dNBR threshold {DNBR_BURN_THRESHOLD}")
        return None

    gdf = gpd.GeoDataFrame(geometry=polys, crs="EPSG:4326")
    gdf_m = gdf.to_crs("EPSG:32633")
    whole_chip_area_ha = gdf_m.area.sum() / 1e4

    from shapely.geometry import Point
    query_pt_m = gpd.GeoSeries([Point(center_lon, center_lat)], crs="EPSG:4326").to_crs("EPSG:32633").iloc[0]
    gdf_m["dist_to_query_m"] = gdf_m.geometry.distance(query_pt_m)
    gdf_m["area_ha"] = gdf_m.geometry.area / 1e4

    # the patch actually at our known fire location, not the sum of every flagged
    # pixel across the whole 15km chip (most of which is unrelated seasonal change,
    # not this specific fire) - report that patch's own area, not a chip-wide total
    nearest = gdf_m.loc[gdf_m["dist_to_query_m"].idxmin()]

    gdf.to_file(f"output/dnbr_{out_prefix}.geojson", driver="GeoJSON")
    print(f"{label}: nearest patch = {nearest['area_ha']:.2f} ha, {nearest['dist_to_query_m']:.0f}m from query point "
          f"(whole-chip total across {len(gdf_m)} separate patches: {whole_chip_area_ha:.0f} ha - mostly unrelated background change)")
    return {
        "label": label,
        "nearest_patch_area_ha": round(nearest["area_ha"], 2),
        "nearest_patch_dist_m": round(nearest["dist_to_query_m"]),
        "n_patches_in_chip": len(gdf_m),
        "whole_chip_area_ha": round(whole_chip_area_ha, 1),
    }


def run_bais2(post_item, center_lon, center_lat, label, out_prefix):
    b04, meta = fetch_band(post_item, "B04", center_lon, center_lat)
    b06, _ = fetch_band(post_item, "B06", center_lon, center_lat)
    b07, _ = fetch_band(post_item, "B07", center_lon, center_lat)
    b8a, _ = fetch_band(post_item, "B8A", center_lon, center_lat)
    b12, _ = fetch_band(post_item, "B12", center_lon, center_lat)

    b04, b06, b07, b8a, b12 = (b * HLS_SCALE_FACTOR for b in (b04, b06, b07, b8a, b12))
    bais2 = compute_bais2(b06, b07, b8a, b04, b12)

    raw_mask = (bais2 > BAIS2_BURN_THRESHOLD).astype("uint8")
    raw_mask[np.isnan(bais2)] = 0
    burn_mask = clean_burn_mask(raw_mask)

    polys = []
    for geom, val in shapes(burn_mask, mask=burn_mask > 0, transform=meta["transform"]):
        geom_wgs84 = rasterio.warp.transform_geom(meta["crs"], "EPSG:4326", geom)
        polys.append(shapely_shape(geom_wgs84))

    if not polys:
        print(f"{label}: no burn detected above BAIS2 threshold {BAIS2_BURN_THRESHOLD}")
        return None

    gdf = gpd.GeoDataFrame(geometry=polys, crs="EPSG:4326")
    gdf_m = gdf.to_crs("EPSG:32633")
    whole_chip_area_ha = gdf_m.area.sum() / 1e4

    from shapely.geometry import Point
    query_pt_m = gpd.GeoSeries([Point(center_lon, center_lat)], crs="EPSG:4326").to_crs("EPSG:32633").iloc[0]
    gdf_m["dist_to_query_m"] = gdf_m.geometry.distance(query_pt_m)
    gdf_m["area_ha"] = gdf_m.geometry.area / 1e4

    nearest = gdf_m.loc[gdf_m["dist_to_query_m"].idxmin()]

    gdf.to_file(f"output/bais2_{out_prefix}.geojson", driver="GeoJSON")
    print(f"{label} [BAIS2]: nearest patch = {nearest['area_ha']:.2f} ha, {nearest['dist_to_query_m']:.0f}m from query point "
          f"(whole-chip total across {len(gdf_m)} separate patches: {whole_chip_area_ha:.0f} ha - mostly unrelated background change)")
    return {
        "label": label,
        "nearest_patch_area_ha": round(nearest["area_ha"], 2),
        "nearest_patch_dist_m": round(nearest["dist_to_query_m"]),
        "n_patches_in_chip": len(gdf_m),
        "whole_chip_area_ha": round(whole_chip_area_ha, 1),
    }


if __name__ == "__main__":
    import os
    os.makedirs("output", exist_ok=True)

    results = []
    # RdNBR was tried and rejected (see module notes below run() calls) - at
    # Tiberio's exact known fire pixel RdNBR = 14.5, far below any workable
    # threshold, while noise elsewhere in the chip hit RdNBR>800 - it performs
    # worse than plain dNBR on this dataset/scale, not better. Reverted to
    # plain dNBR as the working method; the mixed-vegetation (Pollina) precision
    # problem stays open rather than being force-fixed.
    results.append(run_dnbr(
        "HLS.S30.T33SVC.2023237T095031.v2.0", "HLS.S30.T33SVC.2023262T094659.v2.0",
        14.1508, 37.9530, "Contrada Tiberio (known: ~2ha)", "tiberio", use_rdnbr=False
    ))
    results.append(run_dnbr(
        "HLS.S30.T33SVB.2023222T094549.v2.0", "HLS.S30.T33SVB.2023277T095031.v2.0",
        14.2079, 37.8692, "Foce del fiume Pollina (known: ~12ha comune-clipped)", "pollina", use_rdnbr=False
    ))

    print("\n--- Summary (dNBR) ---")
    for r in results:
        if r:
            print(r)

    # BAIS2: single-date post-fire index, no pre-fire baseline needed - test
    # whether it's more robust to the seasonal-vegetation-drying false
    # positives that made dNBR ~40% unreliable on automated area estimates.
    bais2_results = []
    bais2_results.append(run_bais2(
        "HLS.S30.T33SVC.2023262T094659.v2.0",
        14.1508, 37.9530, "Contrada Tiberio (known: ~2ha)", "tiberio"
    ))
    bais2_results.append(run_bais2(
        "HLS.S30.T33SVB.2023277T095031.v2.0",
        14.2079, 37.8692, "Foce del fiume Pollina (known: ~12ha comune-clipped)", "pollina"
    ))

    print("\n--- Summary (BAIS2) ---")
    for r in bais2_results:
        if r:
            print(r)
