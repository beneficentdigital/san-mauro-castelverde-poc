"""Cadastral parcel matching for the 52 large fires (>300ha) skipped by
scripts/fetch_parcels_near_fires.py. Same proven tiling approach, just for
the fires that need many more tiles each given their size. Kept separate
rather than removing the size cutoff from the main script, since these
fires genuinely need a different mindset: the output is a complete parcel
list for legal/audit completeness (Legge 353/2000 restrictions apply
per-parcel regardless of fire size), not a short list for manual one-by-one
review the way the smaller fires' lists are.
"""
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

from fetch_parcels_near_fires import fetch_parcels_for_bounds, BUFFER_DEG

FIRES = "data/processed/effis_palermo_province_2018_2025.geojson"
LARGE_FIRES_LIST = "data/processed/palermo_province_large_fires_not_parcel_matched.csv"
OUT_PARCELS = "data/processed/palermo_province_large_fire_matched_parcels.geojson"
OUT_MATCHES = "data/processed/palermo_province_large_fire_parcel_matches.csv"


def main():
    fires = gpd.read_file(FIRES).to_crs("EPSG:4326").drop_duplicates(subset="id")
    large_ids = pd.read_csv(LARGE_FIRES_LIST)["id"].astype(str).tolist()
    fires["id"] = fires["id"].astype(str)
    large_fires = fires[fires["id"].isin(large_ids)].reset_index(drop=True)
    print(f"Matching parcels for {len(large_fires)} large fires (this will take a while)")

    all_parcels = []
    match_rows = []
    seen_parcel_ids = set()

    for i, fire in large_fires.iterrows():
        t0 = time.time()
        buffered = fire.geometry.buffer(BUFFER_DEG)
        minlon, minlat, maxlon, maxlat = buffered.bounds
        parcels = fetch_parcels_for_bounds(minlon, minlat, maxlon, maxlat)

        if len(parcels):
            parcels = parcels.to_crs("EPSG:4326")
            matched = parcels[parcels.geometry.intersects(fire.geometry)]
            matched = matched.drop_duplicates(subset="gml_id")
            new_parcels = matched[~matched["gml_id"].isin(seen_parcel_ids)]
            if len(new_parcels):
                all_parcels.append(new_parcels)
                seen_parcel_ids.update(new_parcels["gml_id"])
        else:
            matched = gpd.GeoDataFrame()

        print(f"  [{i+1}/{len(large_fires)}] {fire['COMMUNE']} ({fire['AREA_HA']}ha): "
              f"{len(matched)} parcels matched in {time.time()-t0:.1f}s", flush=True)

        match_rows.append({
            "fire_id": fire["id"],
            "fire_date": fire["FIREDATE"],
            "comune": fire["COMMUNE"],
            "area_ha_effis": fire["AREA_HA"],
            "n_parcels_matched": len(matched),
            "parcel_refs": "; ".join(matched["NATIONALCADASTRALREFERENCE"]) if len(matched) else "",
        })

        pd.DataFrame(match_rows).to_csv(OUT_MATCHES, index=False)
        if all_parcels:
            gpd.GeoDataFrame(pd.concat(all_parcels, ignore_index=True), crs="EPSG:4326").to_file(OUT_PARCELS, driver="GeoJSON")

    print(f"\nDone. {sum(len(p) for p in all_parcels)} unique parcels across {len(large_fires)} large fires")


if __name__ == "__main__":
    main()
