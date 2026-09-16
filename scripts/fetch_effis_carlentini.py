"""Fetch EFFIS burnt-area polygons for Carlentini, 2018-present. Same
validated approach as fetch_effis.py (San Mauro Castelverde) - see that
file's docstring for the MVT-format discovery notes.
"""
from __future__ import annotations

import geopandas as gpd
import mapbox_vector_tile
import requests
from shapely.geometry import shape
from shapely.ops import transform as shp_transform

EFFIS_WMS = "https://maps.effis.emergency.copernicus.eu/effis"
BOUNDARY = "data/processed/carlentini_boundary.geojson"
YEARS = list(range(2018, 2026))
TILE_EXTENT = 4096
MARGIN_DEG = 0.05
COMUNE_NAME = "Carlentini"
OUT_PATH = "data/processed/effis_carlentini_2018_2025.geojson"


def fetch_layer_mvt(layer: str, bbox: tuple[float, float, float, float]) -> dict | None:
    minlat, minlon, maxlat, maxlon = bbox
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": layer, "QUERY_LAYERS": layer, "STYLES": "", "CRS": "EPSG:4326",
        "BBOX": f"{minlat},{minlon},{maxlat},{maxlon}",
        "WIDTH": 1024, "HEIGHT": 1024, "FORMAT": "application/vnd.mapbox-vector-tile",
    }
    r = requests.get(EFFIS_WMS, params=params, timeout=30)
    r.raise_for_status()
    if not r.content or r.content.startswith(b"<?xml"):
        return None
    decoded = mapbox_vector_tile.decode(r.content)
    return decoded.get(layer)


def tile_to_lonlat(x, y, bbox):
    minlat, minlon, maxlat, maxlon = bbox
    lon = minlon + (x / TILE_EXTENT) * (maxlon - minlon)
    lat = maxlat - (y / TILE_EXTENT) * (maxlat - minlat)
    return lon, lat


def features_to_gdf(layer_data: dict, bbox: tuple, year: int) -> gpd.GeoDataFrame:
    rows = []
    for feat in layer_data["features"]:
        geom_tile = shape(feat["geometry"])
        geom_lonlat = shp_transform(lambda x, y, z=None: tile_to_lonlat(x, y, bbox), geom_tile)
        props = dict(feat["properties"])
        props["year"] = year
        props["source"] = "EFFIS"
        rows.append({**props, "geometry": geom_lonlat})
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def main():
    boundary = gpd.read_file(BOUNDARY).to_crs("EPSG:4326")
    minlon, minlat, maxlon, maxlat = boundary.total_bounds
    bbox = (minlat - MARGIN_DEG, minlon - MARGIN_DEG, maxlat + MARGIN_DEG, maxlon + MARGIN_DEG)
    comune_geom = boundary.geometry.iloc[0]

    all_gdfs = []
    for year in YEARS:
        layer = f"modis.ba.poly.{year}"
        try:
            layer_data = fetch_layer_mvt(layer, bbox)
        except requests.RequestException as e:
            print(f"{year}: request failed ({e}), skipping")
            continue
        if not layer_data or not layer_data.get("features"):
            print(f"{year}: no features in query bbox")
            continue
        gdf = features_to_gdf(layer_data, bbox, year)
        gdf_matched = gdf[(gdf["COMMUNE"] == COMUNE_NAME) | gdf.geometry.intersects(comune_geom)]
        print(f"{year}: {len(gdf)} features in bbox, {len(gdf_matched)} matched to comune")
        if len(gdf_matched):
            all_gdfs.append(gdf_matched)

    if not all_gdfs:
        print(f"No EFFIS features found for {COMUNE_NAME} in any year 2018-2025.")
        return

    result = gpd.GeoDataFrame(gpd.pd.concat(all_gdfs, ignore_index=True), crs="EPSG:4326")
    result.to_file(OUT_PATH, driver="GeoJSON")
    print(f"\nSaved {len(result)} EFFIS fire polygons to {OUT_PATH}")
    print(result[["year", "FIREDATE", "COMMUNE", "AREA_HA"]].to_string())


if __name__ == "__main__":
    main()
