"""Compare our satellite-derived fire detections against Fenice Verde's own
published records for San Mauro Castelverde, and surface gaps.

Two Fenice Verde sources found on osservatorioincendi.org/osservazioni/sanmauro.html:
- particelle_s_mauro.geojson: their cached copy of the base cadastral parcel layer
  (used for their citizen-editing tool) - not itself a fire record.
- sif_sanmauro.geojson: "Censimento Incendi SIF 2024" - the actual official
  regional fire census, labelled 2024-only (confirmed: no 2023 variant exists at
  this URL pattern, tested during the validation gate).

This is the actual point of the whole exercise per the brief: surface fires that
are satellite-visible but not (yet) reflected in Fenice Verde's own published
catasto.
"""
import geopandas as gpd
import pandas as pd
import requests

SIF_URL = "https://www.osservatorioincendi.org/osservazioni/sif_sanmauro.geojson"
FIRES = "data/processed/effis_sanmauro_2018_2025.geojson"
BOUNDARY = "data/processed/san_mauro_boundary.geojson"
OUT_CSV = "data/processed/gap_analysis_vs_feniceverde.csv"


def main():
    r = requests.get(SIF_URL, timeout=30)
    r.raise_for_status()
    sif_path = "data/raw/sif_sanmauro.geojson"
    with open(sif_path, "wb") as f:
        f.write(r.content)
    sif = gpd.read_file(sif_path)
    print(f"Fenice Verde SIF catasto: {len(sif)} recorded fire(s)")
    print(sif[["LOCALITA", "DTAINIZIOF", "TOTSUP"]].to_string() if len(sif) else "  (empty)")

    fires = gpd.read_file(FIRES).to_crs("EPSG:4326")
    boundary = gpd.read_file(BOUNDARY).to_crs("EPSG:4326").geometry.iloc[0]
    fires["in_boundary"] = fires.geometry.intersects(boundary)

    sif = sif.to_crs("EPSG:4326") if len(sif) else sif

    rows = []
    for _, fire in fires.iterrows():
        in_sif = False
        sif_match_note = ""
        if len(sif):
            for _, s in sif.iterrows():
                fire_date = pd.to_datetime(str(fire["FIREDATE"])[:10])
                sif_date = pd.to_datetime(str(s.get("DTAINIZIOF", ""))[:10])
                days_apart = abs((fire_date - sif_date).days)
                # same/near-same day in a comune this size is strong evidence of the same fire;
                # distance is a generous sanity bound (~3km) to rule out true coincidences,
                # not a precise match - the two records measure the event differently
                # (EFFIS centroid vs SIF's own reported locality) so sub-km precision isn't expected
                geographically_close = fire.geometry.distance(s.geometry) < 0.03
                if geographically_close and days_apart <= 3:
                    in_sif = True
                    sif_match_note = f"matches SIF record '{s.get('LOCALITA')}' ({sif_date.date()}, {days_apart}d apart)"
        rows.append(
            {
                "fire_date": fire["FIREDATE"],
                "area_ha_effis": fire["AREA_HA"],
                "commune_field": fire["COMMUNE"],
                "in_feniceverde_sif_catasto": in_sif,
                "note": sif_match_note or "not found in Fenice Verde's SIF catasto (2024-only coverage - fires before 2024 are out of that layer's scope by design, not a detection gap)",
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {OUT_CSV}")
    print(df.to_string())

    n_2024_plus = (pd.to_datetime(df["fire_date"]) >= "2024-01-01").sum()
    n_in_sif = df["in_feniceverde_sif_catasto"].sum()
    print(f"\n{n_2024_plus} EFFIS fires from 2024 onwards (within SIF's coverage window), {n_in_sif} matched in Fenice Verde's SIF catasto")


if __name__ == "__main__":
    main()
