"""Fetch the Sicilian Regional Forestry Service's own official fire registry
("Censimento Incendi") for every comune in Provincia di Palermo, 2018-2025.

This is a genuinely different, stronger source than anything used so far:
- Not satellite-derived (like EFFIS/GFW) - it's the region's own official
  record, the one comuni draw on to compile their legally-mandated Catasto
  Incendi under Legge 353/2000.
- Not limited to Fenice Verde's two pilot comuni - covers the whole region,
  every year back to 2010 (found via the SIF portal's own WMS service list:
  sifweb.regione.sicilia.it/arcgis/rest/services/Censimento_Incendi/MapServer,
  one polygon layer per year).
- Confirmed accurate: queried directly, it returns the exact Contrada Tiberio
  fire (2.26ha, San Mauro Castelverde, 15 Sep 2023) that EFFIS never detected
  and that only Fenice Verde's blog post (not their own SIF cache file, which
  is 2024-only) previously told us about.

This becomes the real "acknowledged burnt areas" ground truth for the gap
analysis against EFFIS, province-wide - stronger than the San Mauro-only
comparison against Fenice Verde's site, which only worked for their two pilot
comuni.
"""
import time

import geopandas as gpd
import pandas as pd
import requests

BASE_URL = "https://sifweb.regione.sicilia.it/arcgis/rest/services/Censimento_Incendi/MapServer"
# layer id -> year, per the service's own layer list
YEAR_LAYERS = {2018: 7, 2019: 6, 2020: 5, 2021: 4, 2022: 3, 2023: 2, 2024: 1, 2025: 0}
COMUNI = "data/processed/palermo_comuni.geojson"
OUT = "data/processed/regione_censimento_incendi_palermo_2018_2025.geojson"


def fetch_year(layer_id, comuni_names, retries=3):
    # despite the qualified field name in outFields (DATI_WEB.DBO.AAAMAMCOMU.DESCRIPTION),
    # the WHERE clause needs the plain alias - confirmed working by direct test
    escaped = [c.replace("'", "''") for c in comuni_names]
    where = " OR ".join(f"UPPER(DESCRIPTION) = '{c.upper()}'" for c in escaped)
    params = {
        "where": where,
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson",
    }
    url = f"{BASE_URL}/{layer_id}/query"
    for attempt in range(retries):
        try:
            r = requests.post(url, data=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"  attempt {attempt+1} failed: {e}")
            time.sleep(2**attempt)
    return None


def main():
    comuni = gpd.read_file(COMUNI)
    comuni_names = comuni["COMUNE"].tolist()

    all_gdfs = []
    for year, layer_id in YEAR_LAYERS.items():
        data = fetch_year(layer_id, comuni_names)
        if not data or "features" not in data:
            print(f"{year}: fetch failed")
            continue
        n = len(data["features"])
        print(f"{year}: {n} official fire records")
        if n:
            import json
            with open("/tmp/_regione_year.geojson", "w") as f:
                json.dump(data, f)
            gdf = gpd.read_file("/tmp/_regione_year.geojson")
            gdf["year"] = year
            all_gdfs.append(gdf)

    if not all_gdfs:
        print("No records fetched.")
        return

    result = gpd.GeoDataFrame(pd.concat(all_gdfs, ignore_index=True), crs="EPSG:4326")
    result.to_file(OUT, driver="GeoJSON")
    print(f"\nSaved {len(result)} official regional fire records to {OUT}")
    total_ha = pd.to_numeric(result.get("DATI_WEB.DBO.DFCNSIINCD_DENORM.TOTSUP"), errors="coerce").sum()
    print(f"Total area (official record): {total_ha:.0f} ha")


if __name__ == "__main__":
    main()
