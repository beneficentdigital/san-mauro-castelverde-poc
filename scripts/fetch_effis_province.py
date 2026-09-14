"""Fetch EFFIS burnt-area polygons for every comune in Provincia di Palermo,
2018-present. Same MVT approach validated for San Mauro Castelverde
(scripts/fetch_effis.py), looped per comune rather than one big province-wide
request - a single giant request loses geometric precision (MVT's tile-local
coordinate space is a fixed 4096 units regardless of the bbox size, so
precision degrades proportionally to area), which matters for matching fire
edges to cadastral parcels later.
"""
from __future__ import annotations

import time

import geopandas as gpd
import mapbox_vector_tile
import requests
from shapely.geometry import shape
from shapely.ops import transform as shp_transform

EFFIS_WMS = "https://maps.effis.emergency.copernicus.eu/effis"
COMUNI = "data/processed/palermo_comuni.geojson"
YEARS = list(range(2018, 2026))
TILE_EXTENT = 4096
MARGIN_DEG = 0.03
OUT = "data/processed/effis_palermo_province_2018_2025.geojson"


def fetch_layer_mvt(layer, bbox, retries=3):
    minlat, minlon, maxlat, maxlon = bbox
    params = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": layer, "STYLES": "", "CRS": "EPSG:4326",
        "BBOX": f"{minlat},{minlon},{maxlat},{maxlon}",
        "WIDTH": 1024, "HEIGHT": 1024,
        "FORMAT": "application/vnd.mapbox-vector-tile",
    }
    for attempt in range(retries):
        try:
            r = requests.get(EFFIS_WMS, params=params, timeout=30)
            r.raise_for_status()
            if not r.content or r.content.startswith(b"<?xml"):
                return None
            decoded = mapbox_vector_tile.decode(r.content)
            return decoded.get(layer)
        except requests.RequestException:
            time.sleep(2**attempt)
    return None


def tile_to_lonlat(x, y, bbox):
    minlat, minlon, maxlat, maxlon = bbox
    lon = minlon + (x / TILE_EXTENT) * (maxlon - minlon)
    lat = maxlat - (y / TILE_EXTENT) * (maxlat - minlat)
    return lon, lat


def main():
    comuni = gpd.read_file(COMUNI)
    all_gdfs = []

    for i, comune in comuni.iterrows():
        minlon, minlat, maxlon, maxlat = comune.geometry.bounds
        bbox = (minlat - MARGIN_DEG, minlon - MARGIN_DEG, maxlat + MARGIN_DEG, maxlon + MARGIN_DEG)
        comune_name = comune["COMUNE"]
        comune_matches = []

        for year in YEARS:
            layer = f"modis.ba.poly.{year}"
            layer_data = fetch_layer_mvt(layer, bbox)
            if not layer_data or not layer_data.get("features"):
                continue
            rows = []
            for feat in layer_data["features"]:
                geom_tile = shape(feat["geometry"])
                geom_lonlat = shp_transform(lambda x, y, z=None: tile_to_lonlat(x, y, bbox), geom_tile)
                props = dict(feat["properties"])
                props["year"] = year
                props["source"] = "EFFIS"
                props["pro_com"] = comune["PRO_COM"]
                rows.append({**props, "geometry": geom_lonlat})
            if rows:
                gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
                matched = gdf[
                    (gdf["COMMUNE"] == comune_name) | gdf.geometry.intersects(comune.geometry)
                ]
                if len(matched):
                    comune_matches.append(matched)

        if comune_matches:
            all_gdfs.append(gpd.pd.concat(comune_matches, ignore_index=True))

        if (i + 1) % 10 == 0 or i == len(comuni) - 1:
            total = sum(len(g) for g in all_gdfs)
            print(f"  {i+1}/{len(comuni)} comuni processed, {total} fire records so far")

    if not all_gdfs:
        print("No EFFIS fires found across the province.")
        return

    result = gpd.pd.concat(all_gdfs, ignore_index=True)
    result = gpd.GeoDataFrame(result, crs="EPSG:4326")
    result = result.drop_duplicates(subset=["id", "pro_com"])
    result.to_file(OUT, driver="GeoJSON")
    print(f"\nSaved {len(result)} fire records to {OUT}")
    print(f"Across {result['pro_com'].nunique()} comuni")


if __name__ == "__main__":
    main()
