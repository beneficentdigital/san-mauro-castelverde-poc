"""Assemble the per-fire summary table (deliverable 2): one row per fire since
2018, area by detection method, matched particelle, catasto status, ignition
flags.

GFW and FireHR columns are included but empty/marked n/a - GFW is blocked by a
platform-side bug (see docs/gfw_known_issue.md), FireHR needs GEE auth not yet
set up. Left in the table structure rather than omitted, so the gap is visible
rather than silently absent.
"""
import pandas as pd

FIRES = "data/processed/effis_sanmauro_2018_2025.geojson"
PARCEL_MATCHES = "data/processed/fire_parcel_matches.csv"
GAP_CSV = "data/processed/gap_analysis_vs_feniceverde.csv"
IGNITION_CSV = "data/processed/ignition_context_flags.csv"
GFW_CROSS_CHECK = "data/processed/effis_gfw_cross_check.csv"
OUT = "output/fire_summary_table.csv"

PRITHVI_RESULTS = {
    "2023-09-15": {"area_ha": None, "note": "no HLS chip fetched for this specific date - validated at Tiberio's location using the 19 Sep post-fire scene instead"},
    "2023-09-21": {"area_ha": 101.6, "note": "validated - see docs/validation_note_2023_fires.md"},
}


def main():
    import geopandas as gpd

    fires = gpd.read_file(FIRES)
    parcel_df = pd.read_csv(PARCEL_MATCHES)
    gap_df = pd.read_csv(GAP_CSV)
    ignition_df = pd.read_csv(IGNITION_CSV)
    gfw_df = pd.read_csv(GFW_CROSS_CHECK)
    gfw_df["fire_id_str"] = gfw_df["fire_id"].astype(str)

    fires["id_str"] = fires["id"].astype(str)
    parcel_df["fire_id_str"] = parcel_df["fire_id"].astype(str)
    gap_df["fire_id_str"] = gap_df["fire_id"].astype(str)
    ignition_df["fire_id_str"] = ignition_df["fire_id"].astype(str)

    df = fires[["id_str", "FIREDATE", "AREA_HA", "COMMUNE", "PERCNA2K"]].rename(
        columns={"id_str": "fire_id", "FIREDATE": "date", "AREA_HA": "area_ha_effis", "COMMUNE": "effis_commune_field", "PERCNA2K": "pct_natura2000"}
    )
    df["date"] = df["date"].astype(str)

    df = df.merge(parcel_df[["fire_id_str", "n_parcels_touched", "foglio_particella_list"]], left_on="fire_id", right_on="fire_id_str", how="left").drop(columns=["fire_id_str"])
    df = df.merge(gap_df[["fire_id_str", "in_feniceverde_sif_catasto"]], left_on="fire_id", right_on="fire_id_str", how="left").drop(columns=["fire_id_str"])
    df = df.merge(
        ignition_df[["fire_id_str", "day_or_night_ignition", "pastureland_context_flag", "geometric_shape_flag"]],
        left_on="fire_id", right_on="fire_id_str", how="left"
    ).drop(columns=["fire_id_str"])

    df = df.merge(gfw_df[["fire_id_str", "closest_gfw_point_km", "gfw_confirms_within_2km"]], left_on="fire_id", right_on="fire_id_str", how="left").drop(columns=["fire_id_str"])
    df["gfw_viirs_cross_check"] = df.apply(
        lambda r: f"nearest VIIRS hotspot {r['closest_gfw_point_km']}km away (not a tight match)" if pd.notna(r["closest_gfw_point_km"]) else "no VIIRS hotspot within 3 days",
        axis=1,
    )
    df = df.drop(columns=["closest_gfw_point_km", "gfw_confirms_within_2km"])
    df["area_ha_firehr"] = "n/a (needs GEE auth, not yet set up)"
    df["area_ha_prithvi"] = df["date"].str[:10].map(lambda d: PRITHVI_RESULTS.get(d, {}).get("area_ha", "not run for this fire"))

    df["n_parcels_touched"] = df["n_parcels_touched"].fillna(0).astype(int)
    df["in_feniceverde_sif_catasto"] = df["in_feniceverde_sif_catasto"].fillna("n/a (SIF catasto is 2024-only)")

    cols = [
        "date", "area_ha_effis", "gfw_viirs_cross_check", "area_ha_firehr", "area_ha_prithvi",
        "effis_commune_field", "n_parcels_touched", "foglio_particella_list",
        "in_feniceverde_sif_catasto", "day_or_night_ignition", "pastureland_context_flag",
        "geometric_shape_flag", "pct_natura2000",
    ]
    df = df[cols]

    # Contrada Tiberio (2023-09-15) is not in EFFIS at all - below its detection
    # floor (see validation note). It's one of the two headline known fires, so
    # it goes in explicitly rather than silently disappearing because EFFIS is
    # the table's backbone. Prithvi and Fenice Verde blog are the only sources
    # for this row.
    tiberio_row = pd.DataFrame([{
        "date": "2023-09-15 (known fire, not EFFIS-detected)",
        "area_ha_effis": "not detected (below EFFIS's mapping floor - see validation note)",
        "gfw_viirs_cross_check": "no VIIRS hotspot within 3 days",
        "area_ha_firehr": "n/a (needs GEE auth, not yet set up)",
        "area_ha_prithvi": 36.0,
        "effis_commune_field": "n/a",
        "n_parcels_touched": None,
        "foglio_particella_list": "not computed (no EFFIS/GFW polygon to join against parcels)",
        "in_feniceverde_sif_catasto": "n/a (SIF catasto is 2024-only; known instead from Fenice Verde's blog post)",
        "day_or_night_ignition": "n/a",
        "pastureland_context_flag": "n/a",
        "geometric_shape_flag": "n/a",
        "pct_natura2000": "n/a (fire is inside ZSC Boschi di S. Mauro Castelverde per Fenice Verde's blog)",
    }])
    df = pd.concat([df, tiberio_row], ignore_index=True).sort_values("date")

    df.to_csv(OUT, index=False)
    print(f"Saved {OUT}")
    print(df.to_string())


if __name__ == "__main__":
    main()
