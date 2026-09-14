"""Spatially join fire polygons against cadastral parcels to find affected particelle.

NATIONALCADASTRALREFERENCE format confirmed by cross-checking against the AdE
point-lookup service: "I028_006700.972" = comune I028, foglio 67, particella 972
(foglio is zero-padded to 4 digits + "00", particella after the dot).

Per the brief: a detected fire polygon may span several particelle, and satellite
resolution won't always cleanly match parcel boundaries - this is stated plainly
in the output rather than smoothed over.
"""
import re

import geopandas as gpd

FIRES = "data/processed/effis_sanmauro_2018_2025.geojson"
PARCELS = "data/processed/cadastral_parcels_sanmauro.geojson"
OUT = "data/processed/fire_parcel_matches.geojson"


def parse_foglio_particella(ref: str):
    m = re.match(r"I028_(\d{4})\d*\.(\d+)", ref)
    if not m:
        return None, None
    foglio = int(m.group(1))
    particella = m.group(2)
    return foglio, particella


def main():
    fires = gpd.read_file(FIRES).to_crs("EPSG:4326")
    parcels = gpd.read_file(PARCELS).to_crs("EPSG:4326")

    joined = gpd.sjoin(parcels, fires, how="inner", predicate="intersects")
    print(f"{len(joined)} parcel-fire intersections found across {fires['id'].nunique()} fires")
    matched_parcels = parcels.loc[joined.index.unique()]
    matched_parcels.to_file(OUT, driver="GeoJSON")
    print(f"Saved {OUT} ({len(matched_parcels)} matched parcels, for the map layer)")

    rows = []
    for fire_idx, fire in fires.iterrows():
        matched = joined[joined["index_right"] == fire_idx]
        if len(matched) == 0:
            continue
        foglio_particella = [parse_foglio_particella(r) for r in matched["NATIONALCADASTRALREFERENCE"]]
        parcel_area_ha = matched.to_crs("EPSG:32633").geometry.area.sum() / 1e4
        fire_area_ha = gpd.GeoSeries([fire.geometry], crs="EPSG:4326").to_crs("EPSG:32633").area.iloc[0] / 1e4
        rows.append(
            {
                "fire_id": fire["id"],
                "fire_date": fire["FIREDATE"],
                "fire_area_ha_effis": fire["AREA_HA"],
                "n_parcels_touched": len(matched),
                "parcels_total_area_ha": round(parcel_area_ha, 2),
                "foglio_particella_list": "; ".join(f"{f}/{p}" for f, p in foglio_particella if f is not None),
                "note": (
                    "fire polygon spans multiple parcels - satellite-detected boundary "
                    "does not align with parcel edges, this is a coverage list not a "
                    "precise single-parcel match"
                    if len(matched) > 1
                    else "single parcel match"
                ),
            }
        )

    import pandas as pd

    result_df = pd.DataFrame(rows)
    result_df.to_csv("data/processed/fire_parcel_matches.csv", index=False)
    print(f"Saved data/processed/fire_parcel_matches.csv ({len(result_df)} fires with parcel matches)")
    print(result_df[["fire_date", "fire_area_ha_effis", "n_parcels_touched", "parcels_total_area_ha"]].to_string())


if __name__ == "__main__":
    main()
