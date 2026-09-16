"""Region-wide version of fetch_regional_catasto_incendi.py - all of Sicily
(391 comuni, 9 province), not just Palermo. Uses a geometry (bbox) filter
instead of a comune-name WHERE clause, since 391 OR-ed name conditions would
be unwieldy - and adds pagination (resultOffset), since a single year alone
(2023) already exceeds the service's 1000-record page cap.
"""
import time

import geopandas as gpd
import pandas as pd
import requests

BASE_URL = "https://sifweb.regione.sicilia.it/arcgis/rest/services/Censimento_Incendi/MapServer"
YEAR_LAYERS = {2018: 7, 2019: 6, 2020: 5, 2021: 4, 2022: 3, 2023: 2, 2024: 1, 2025: 0}
SICILY_BBOX = "11.92,35.49,15.66,38.82"
OUT = "data/processed/regione_censimento_incendi_sicilia_2018_2025.geojson"
PAGE_SIZE = 1000


def fetch_year(layer_id, retries=3):
    url = f"{BASE_URL}/{layer_id}/query"
    all_features = []
    offset = 0
    paginate = True
    while True:
        params = {
            "geometry": SICILY_BBOX, "geometryType": "esriGeometryEnvelope", "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true",
            "outSR": 4326, "f": "geojson",
        }
        if paginate:
            params["resultOffset"] = offset
            params["resultRecordCount"] = PAGE_SIZE

        for attempt in range(retries):
            try:
                r = requests.post(url, data=params, timeout=60)
                r.raise_for_status()
                data = r.json()
                break
            except requests.RequestException as e:
                print(f"  attempt {attempt+1} failed: {e}")
                time.sleep(2**attempt)
        else:
            break

        if "error" in data:
            if paginate and "pagination" in data["error"].get("message", "").lower():
                # some layers reject pagination params outright (server quirk,
                # not a record-count issue) - retry once without them
                print("  layer rejects pagination, retrying as a single unpaginated request")
                paginate = False
                continue
            print(f"  server error: {data['error']}")
            break

        feats = data.get("features", [])
        all_features.extend(feats)
        if not paginate or len(feats) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return all_features


def main():
    all_gdfs = []
    for year, layer_id in YEAR_LAYERS.items():
        feats = fetch_year(layer_id)
        print(f"{year}: {len(feats)} official fire records (all Sicily)")
        if feats:
            import json
            with open("/tmp/_sicilia_year.geojson", "w") as f:
                json.dump({"type": "FeatureCollection", "features": feats}, f)
            gdf = gpd.read_file("/tmp/_sicilia_year.geojson")
            gdf["year"] = year
            all_gdfs.append(gdf)

    result = gpd.GeoDataFrame(pd.concat(all_gdfs, ignore_index=True), crs="EPSG:4326")
    result.to_file(OUT, driver="GeoJSON")
    print(f"\nSaved {len(result)} official fire records for all of Sicily to {OUT}")
    total_ha = pd.to_numeric(result.get("DATI_WEB.DBO.DFCNSIINCD_DENORM.TOTSUP"), errors="coerce").sum()
    print(f"Total area: {total_ha:.0f} ha")
    print(f"Comuni represented: {result['DATI_WEB.DBO.AAAMAMCOMU.DESCRIPTION'].nunique()}")


if __name__ == "__main__":
    main()
