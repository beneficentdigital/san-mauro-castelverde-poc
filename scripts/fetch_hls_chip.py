"""Build a 512x512, 6-band HLS GeoTIFF chip (Blue, Green, Red, NIR-narrow, SWIR1, SWIR2)
for Prithvi burn-scar inference, centred on a given lon/lat.

Source: HLS v2.0 (NASA) via Microsoft Planetary Computer STAC API - free, no auth needed
for search/read. Band order matches the Prithvi-EO-2.0-300M-BurnScars model card.
"""
import sys

import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.warp import transform as warp_transform
from rasterio.windows import Window
from rasterio.enums import Resampling

BANDS = ["B02", "B03", "B04", "B8A", "B11", "B12"]  # Blue, Green, Red, NIR-narrow, SWIR1, SWIR2
CHIP_SIZE = 512


def fetch_chip(item_id: str, center_lon: float, center_lat: float, out_path: str):
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    item = list(catalog.search(collections=["hls2-s30"], ids=[item_id]).items())[0]

    band_arrays = []
    out_meta = None
    for band in BANDS:
        href = item.assets[band].href
        with rasterio.open(href) as src:
            lon, lat = warp_transform("EPSG:4326", src.crs, [center_lon], [center_lat])
            col, row = ~src.transform * (lon[0], lat[0])
            col, row = int(col), int(row)
            half = CHIP_SIZE // 2
            if not (half <= col <= src.width - half and half <= row <= src.height - half):
                raise ValueError(
                    f"Requested {CHIP_SIZE}x{CHIP_SIZE} window at col={col},row={row} "
                    f"falls outside tile bounds ({src.width}x{src.height}) - point is too "
                    f"close to this tile's edge, pick a neighbouring tile instead."
                )
            window = Window(col - half, row - half, CHIP_SIZE, CHIP_SIZE)
            arr = src.read(1, window=window, boundless=True, fill_value=0, out_shape=(CHIP_SIZE, CHIP_SIZE))
            band_arrays.append(arr.astype("float32"))
            if out_meta is None:
                out_meta = src.meta.copy()
                out_meta.update(
                    count=len(BANDS),
                    dtype="float32",
                    height=CHIP_SIZE,
                    width=CHIP_SIZE,
                    transform=rasterio.windows.transform(window, src.transform),
                )

    stack = np.stack(band_arrays, axis=0)
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(stack)

    # quick cloud check via Fmask (bit 1 = cloud) over the same window
    fmask_href = item.assets["Fmask"].href
    with rasterio.open(fmask_href) as src:
        lon, lat = warp_transform("EPSG:4326", src.crs, [center_lon], [center_lat])
        col, row = ~src.transform * (lon[0], lat[0])
        col, row = int(col), int(row)
        half = CHIP_SIZE // 2
        window = Window(col - half, row - half, CHIP_SIZE, CHIP_SIZE)
        fmask = src.read(1, window=window, boundless=True, fill_value=0, out_shape=(CHIP_SIZE, CHIP_SIZE))
    cloud_bit = (fmask >> 1) & 1
    cloud_pct = 100 * cloud_bit.sum() / cloud_bit.size
    print(f"{out_path}: saved, band means {stack.reshape(len(BANDS), -1).mean(axis=1)}, cloud cover in chip: {cloud_pct:.1f}%")
    return out_path


if __name__ == "__main__":
    item_id, lon, lat, out_path = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    fetch_chip(item_id, lon, lat, out_path)
