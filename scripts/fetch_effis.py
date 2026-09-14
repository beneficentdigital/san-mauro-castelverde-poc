"""Fetch EFFIS burnt-area polygons for San Mauro Castelverde, 2018-present.

EFFIS (Copernicus/JRC) exposes no WFS at the public WMS base URL - GetCapabilities
for WFS times out and the endpoint is WMS-only. However GetMap supports
FORMAT=application/vnd.mapbox-vector-tile, which returns real vector polygons
with full Rapid Damage Assessment attributes (FIREDATE, COMMUNE, AREA_HA, land
cover breakdown, % in Natura 2000) - not just a rendered raster. That's the
route used here instead of the raster-tile-vectorisation approach in the
LuisSevillano/effis_current_situation reference script.

Layer naming on this WMS is misleading: "modis.ba.poly.<year>" sounds MODIS-only,
but the decoded attributes confirm it's the full multi-sensor Rapid Damage
Assessment product.

Source: https://maps.effis.emergency.copernicus.eu/effis (Copernicus/JRC, EU Data License)
"""
from __future__ import annotations

import json

import geopandas as gpd
import mapbox_vector_tile
import requests
from shapely.geometry import Polygon, shape
from shapely.ops import transform as shp_transform

EFFIS_WMS = "https://maps.effis.emergency.copernicus.eu/effis"
BOUNDARY = "data/processed/san_mauro_boundary.geojson"
YEARS = list(range(2018, 2026))
TILE_EXTENT = 4096
MARGIN_DEG = 0.05  # query a bit wider than the comune so edge fires aren't clipped pre-fetch


def fetch_layer_mvt(layer: str, bbox: tuple[float, float, float, float]) -> dict | None:
    """bbox = (minlat, minlon, maxlat, maxlon) — EFFIS WMS 1.3.0 + EPSG:4326 uses lat,lon axis order."""
    minlat, minlon, maxlat, maxlon = bbox
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": layer,
        "QUERY_LAYERS": layer,
        "STYLES": "",
        "CRS": "EPSG:4326",
        "BBOX": f"{minlat},{minlon},{maxlat},{maxlon}",
        "WIDTH": 1024,
        "HEIGHT": 1024,
        "FORMAT": "application/vnd.mapbox-vector-tile",
    }
    r = requests.get(EFFIS_WMS, params=params, timeout=30)
    r.raise_for_status()
    if not r.content or r.content.startswith(b"<?xml"):
        return None
    decoded = mapbox_vector_tile.decode(r.content)
    return decoded.get(layer)


def tile_to_lonlat(x, y, bbox):
    """Map MVT tile-local coords [0, TILE_EXTENT] back to the query bbox in lon/lat.
    y=0 is the top (north) row, matching standard WMS image row order."""
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
        # keep only fires attributed to this comune by name, OR intersecting the comune polygon
        # (a fire can span comuni; COMMUNE attribute reflects ignition point, not full extent)
        gdf_matched = gdf[
            (gdf["COMMUNE"] == "San Mauro Castelverde") | gdf.geometry.intersects(comune_geom)
        ]
        print(f"{year}: {len(gdf)} features in bbox, {len(gdf_matched)} matched to comune")
        if len(gdf_matched):
            all_gdfs.append(gdf_matched)

    if not all_gdfs:
        print("No EFFIS features found for San Mauro Castelverde in any year 2018-2025.")
        return

    result = gpd.pd.concat(all_gdfs, ignore_index=True)
    result = gpd.GeoDataFrame(result, crs="EPSG:4326")
    out_path = "data/processed/effis_sanmauro_2018_2025.geojson"
    result.to_file(out_path, driver="GeoJSON")
    print(f"\nSaved {len(result)} EFFIS fire polygons to {out_path}")
    print(result[["year", "FIREDATE", "COMMUNE", "AREA_HA", "PERCNA2K"]].to_string())


if __name__ == "__main__":
    main()
