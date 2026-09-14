"""Fetch VIIRS active-fire alert points for San Mauro Castelverde from GFW.

The GFW Data API's newest dataset versions (v20250206 onward, as of this
writing) have a broken geometry filter on POST /query - confirmed by testing
against a massive, well-documented wildfire (Rhodes, Greece, July 2023) where
even a simple count-with-no-date-filter returns 0. Documented in
docs/gfw_known_issue.md. Versions up to and including v20250127 filter
correctly, but each dated version is a frozen snapshot as of its own creation
date, not a continuously-updated feed - v20250127's most recent record is
2025-01-27. That's the tradeoff made here: working spatial filtering, full
2018-present coverage except roughly the last ~8 months before whatever
"today" is when this is re-run. Worth re-checking whether GFW has fixed newer
versions before the next run.
"""
import time

import geopandas as gpd
import pandas as pd
import requests

GFW_URL = "https://data-api.globalforestwatch.org/dataset/nasa_viirs_fire_alerts/v20250127/query"
BOUNDARY = "data/processed/san_mauro_boundary.geojson"
OUT = "data/processed/gfw_viirs_alerts_sanmauro.geojson"
MAX_RETRIES = 4


def get_api_key():
    for line in open(".env"):
        if line.startswith("GFW_API_KEY"):
            return line.strip().split("=", 1)[1]
    raise RuntimeError("GFW_API_KEY not found in .env")


def query(sql, geometry, api_key):
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(
                GFW_URL,
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={"sql": sql, "geometry": geometry},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            wait = 2**attempt
            print(f"  request failed ({e}), retry {attempt+1}/{MAX_RETRIES} in {wait}s")
            time.sleep(wait)
    raise RuntimeError("GFW query failed after retries")


def main():
    api_key = get_api_key()
    boundary = gpd.read_file(BOUNDARY)
    geom = boundary.geometry.iloc[0].__geo_interface__

    sql = (
        "SELECT latitude, longitude, alert__date, alert__time_utc, confidence__cat, "
        '"frp__MW" FROM data WHERE alert__date >= \'2018-01-01\''
    )
    result = query(sql, geom, api_key)
    rows = result.get("data", [])
    print(f"Fetched {len(rows)} VIIRS fire alert points for San Mauro Castelverde since 2018 (through 2025-01-27)")

    if rows:
        df = pd.DataFrame(rows)
        gdf = gpd.GeoDataFrame(
            df, geometry=gpd.points_from_xy(df["longitude"].astype(float), df["latitude"].astype(float)), crs="EPSG:4326"
        )
        gdf.to_file(OUT, driver="GeoJSON")
        print(f"Saved {OUT}")
        print(df.sort_values("alert__date").to_string())
    else:
        print("No VIIRS alerts found in this window - plausible for a comune this size given VIIRS's")
        print("own documented limitation that many short/small fires fall between satellite overpasses.")


if __name__ == "__main__":
    main()
