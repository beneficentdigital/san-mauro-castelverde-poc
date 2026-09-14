"""Fetch cadastral parcels (particelle catastali) for San Mauro Castelverde from the
official Agenzia delle Entrate WFS.

Source: https://wfs.cartografia.agenziaentrate.gov.it/inspire/wfs/owfs01.php
License: CC BY 4.0, attribution to Agenzia delle Entrate required in any output.
CRS: native EPSG:6706 (ETRF2000) - reprojected to EPSG:4326 here for consistency
with the other layers (near-identical at this precision, but handled explicitly).

The service silently returns zero features (HTTP 200, empty FeatureCollection,
no error) for bbox queries wider than ~0.015 degrees - no error is raised, so this
is easy to miss. Confirmed by testing: 0.015 deg boxes return data, 0.02 deg boxes
return nothing. So the comune is queried in a grid of small tiles with per-tile
pagination (startIndex) for tiles above the COUNT cap, and retry/backoff per the
brief's own note about this service's concurrent-request limits.
"""
import time

import geopandas as gpd
import pandas as pd
import requests

WFS_URL = "https://wfs.cartografia.agenziaentrate.gov.it/inspire/wfs/owfs01.php"
BOUNDARY = "data/processed/san_mauro_boundary.geojson"
OUT = "data/processed/cadastral_parcels_sanmauro.geojson"
TILE_SIZE = 0.012  # degrees; safely under the ~0.015-0.02 deg failure threshold
COUNT = 500
MAX_RETRIES = 4


def fetch_tile(minlat, minlon, maxlat, maxlon, start_index=0):
    params = {
        "language": "ita",
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "TYPENAMES": "CP:CadastralParcel",
        "SRSNAME": "urn:ogc:def:crs:EPSG::6706",
        "BBOX": f"{minlat},{minlon},{maxlat},{maxlon}",
        "REQUEST": "GetFeature",
        "COUNT": COUNT,
        "STARTINDEX": start_index,
    }
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(WFS_URL, params=params, timeout=30)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            wait = 2**attempt
            print(f"  tile fetch failed ({e}), retry {attempt+1}/{MAX_RETRIES} in {wait}s")
            time.sleep(wait)
    print(f"  tile at ({minlat},{minlon}) failed after {MAX_RETRIES} retries, skipping")
    return None


def fetch_all_tiles(bounds, tile_size=TILE_SIZE):
    minlon, minlat, maxlon, maxlat = bounds
    import numpy as np

    lat_edges = np.arange(minlat, maxlat + tile_size, tile_size)
    lon_edges = np.arange(minlon, maxlon + tile_size, tile_size)

    all_gdfs = []
    n_tiles = (len(lat_edges) - 1) * (len(lon_edges) - 1)
    tile_i = 0
    for i in range(len(lat_edges) - 1):
        for j in range(len(lon_edges) - 1):
            tile_i += 1
            tlat0, tlat1 = lat_edges[i], lat_edges[i + 1]
            tlon0, tlon1 = lon_edges[j], lon_edges[j + 1]
            start_index = 0
            tile_features = []
            while True:
                content = fetch_tile(tlat0, tlon0, tlat1, tlon1, start_index)
                if content is None:
                    break
                tmp_path = "/tmp/_cad_tile.gml"
                with open(tmp_path, "wb") as f:
                    f.write(content)
                try:
                    gdf = gpd.read_file(tmp_path)
                except Exception:
                    break
                if len(gdf) == 0:
                    break
                tile_features.append(gdf)
                if len(gdf) < COUNT:
                    break
                start_index += COUNT
            if tile_features:
                all_gdfs.append(pd.concat(tile_features, ignore_index=True))
            if tile_i % 20 == 0 or tile_i == n_tiles:
                total = sum(len(g) for g in all_gdfs)
                print(f"  tile {tile_i}/{n_tiles}, {total} parcels so far")
            time.sleep(0.2)  # be polite given the brief's concurrent-request note

    if not all_gdfs:
        return gpd.GeoDataFrame()
    result = pd.concat(all_gdfs, ignore_index=True)
    result = result.drop_duplicates(subset="gml_id")
    return gpd.GeoDataFrame(result, geometry="geometry", crs="EPSG:6706")


def main():
    boundary = gpd.read_file(BOUNDARY)
    bounds = boundary.total_bounds  # minlon, minlat, maxlon, maxlat
    print(f"Fetching parcels for bounds {bounds} in {TILE_SIZE} deg tiles...")

    parcels = fetch_all_tiles(bounds)
    print(f"Fetched {len(parcels)} raw parcel features")

    parcels = parcels.to_crs("EPSG:4326")
    comune_geom = boundary.to_crs("EPSG:4326").geometry.iloc[0]
    parcels_in_comune = parcels[parcels.geometry.intersects(comune_geom)]
    print(f"{len(parcels_in_comune)} parcels intersect the comune boundary")

    parcels_in_comune.to_file(OUT, driver="GeoJSON")
    print(f"Saved {OUT}")
    print("Attribution required: Agenzia delle Entrate, CC BY 4.0")


if __name__ == "__main__":
    main()
