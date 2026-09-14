"""Fetch VIIRS active-fire alert points for the whole Provincia di Palermo.
Same working dataset version as the San Mauro Castelverde pull
(scripts/fetch_gfw_fire_alerts.py) - v20250127, the newest version with a
working geometry filter (see docs/gfw_known_issue.md). Single query against
the whole province polygon - this is point data via SQL, not tile-rendered,
so it doesn't have the precision-loss problem EFFIS's MVT tiles do at this
scale.
"""
import time

import geopandas as gpd
import pandas as pd
import requests

GFW_URL = "https://data-api.globalforestwatch.org/dataset/nasa_viirs_fire_alerts/v20250127/query"
BOUNDARY = "data/processed/palermo_provincia_boundary.geojson"
OUT = "data/processed/gfw_viirs_alerts_palermo_province.geojson"
MAX_RETRIES = 4


def get_api_key():
    for line in open(".env"):
        if line.startswith("GFW_API_KEY"):
            return line.strip().split("=", 1)[1]
    raise RuntimeError("GFW_API_KEY not found in .env")


def main():
    api_key = get_api_key()
    boundary = gpd.read_file(BOUNDARY)
    geom = boundary.geometry.iloc[0].__geo_interface__

    sql = (
        "SELECT latitude, longitude, alert__date, alert__time_utc, confidence__cat, "
        '"frp__MW" FROM data WHERE alert__date >= \'2018-01-01\''
    )

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(
                GFW_URL,
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={"sql": sql, "geometry": geom},
                timeout=60,
            )
            r.raise_for_status()
            result = r.json()
            break
        except requests.RequestException as e:
            wait = 2**attempt
            print(f"  request failed ({e}), retry {attempt+1}/{MAX_RETRIES} in {wait}s")
            time.sleep(wait)
    else:
        raise RuntimeError("GFW query failed after retries")

    rows = result.get("data", [])
    print(f"Fetched {len(rows)} VIIRS fire alert points for Provincia di Palermo since 2018 (through 2025-01-27)")

    if rows:
        df = pd.DataFrame(rows)
        gdf = gpd.GeoDataFrame(
            df, geometry=gpd.points_from_xy(df["longitude"].astype(float), df["latitude"].astype(float)), crs="EPSG:4326"
        )
        gdf.to_file(OUT, driver="GeoJSON")
        print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
