"""Province-wide summary table: per-comune rollup (82 rows, readable) rather
than per-fire (588 rows, a data export not a table a person reads). The
detailed per-fire data stays in data/processed/palermo_province_fire_parcel_matches.csv.
"""
import geopandas as gpd
import pandas as pd

COMUNI = "data/processed/palermo_comuni.geojson"
FIRES = "data/processed/effis_palermo_province_2018_2025.geojson"
MATCHES = "data/processed/palermo_province_fire_parcel_matches.csv"
LARGE_FIRES = "data/processed/palermo_province_large_fires_not_parcel_matched.csv"
IGNITION = "data/processed/ignition_context_flags_palermo_province.csv"
OUT = "output/palermo_province_summary_by_comune.csv"


def main():
    comuni = gpd.read_file(COMUNI)
    fires = gpd.read_file(FIRES).to_crs("EPSG:4326")
    fires = fires.drop_duplicates(subset="id")
    fires["AREA_HA"] = fires["AREA_HA"].astype(float)

    matches = pd.read_csv(MATCHES)
    ignition = pd.read_csv(IGNITION)
    try:
        large = pd.read_csv(LARGE_FIRES)
    except FileNotFoundError:
        large = pd.DataFrame(columns=["COMUNE"])

    rows = []
    for _, comune in comuni.iterrows():
        name = comune["COMUNE"]
        c_fires = fires[fires["COMMUNE"] == name]
        c_matches = matches[matches["comune"] == name]
        c_large = large[large["COMMUNE"] == name] if len(large) else pd.DataFrame()
        c_ignition = ignition[ignition["comune"] == name]

        rows.append({
            "comune": name,
            "n_fires_2018_2025": len(c_fires),
            "total_area_ha": round(c_fires["AREA_HA"].sum(), 1),
            "n_large_complexes_not_parcel_matched": len(c_large),
            "n_candidate_parcels_suggested": int(c_matches["n_parcels_matched"].sum()) if len(c_matches) else 0,
            "n_geometric_shape_flagged": int((c_ignition["geometric_shape_flag"] == True).sum()) if len(c_ignition) else 0,
            "n_night_ignitions": int((c_ignition["day_or_night_ignition"] == "night").sum()) if len(c_ignition) else 0,
        })

    df = pd.DataFrame(rows).sort_values("total_area_ha", ascending=False)
    df.to_csv(OUT, index=False)
    print(f"Saved {OUT}")
    print(df.head(20).to_string())
    print(f"\n{(df['n_fires_2018_2025']>0).sum()} of {len(df)} comuni have at least one recorded fire, 2018-2025")


if __name__ == "__main__":
    main()
