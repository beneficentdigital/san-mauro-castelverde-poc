"""Cross-check EFFIS satellite detections against the official regional fire
registry, province-wide. This is the real version of the gap analysis the
project started with (originally only possible for San Mauro Castelverde via
Fenice Verde's site, which only covers their two pilot comuni) - now against
an authoritative source covering the whole province.

Two directions, both reported (matches the brief's own principle for the
EFFIS/GFW cross-check: don't just pick the flattering direction):
1. Of EFFIS's satellite detections, how many match an official record?
2. Of the official records, how many has EFFIS never detected? This is the
   more interesting number for the pitch - it's the actual measure of what a
   satellite-only approach would miss if it were the only method used.
"""
import geopandas as gpd
import pandas as pd

EFFIS = "data/processed/effis_palermo_province_2018_2025.geojson"
OFFICIAL = "data/processed/regione_censimento_incendi_palermo_2018_2025.geojson"
OUT_SUMMARY = "data/processed/effis_vs_official_registry_cross_check.csv"
OUT_MISSED = "data/processed/official_fires_not_in_effis.csv"

MATCH_KM = 1.5
MATCH_DAYS = 5

DATE_COL = "DATI_WEB.DBO.DFCNSIINCD_DENORM.DTAINIZIOFUOCO"
AREA_COL = "DATI_WEB.DBO.DFCNSIINCD_DENORM.TOTSUP"
LOCALITA_COL = "DATI_WEB.DBO.DFCNSIINCD_DENORM.LOCALITA"
COMUNE_COL = "DATI_WEB.DBO.AAAMAMCOMU.DESCRIPTION"


def main():
    effis = gpd.read_file(EFFIS).to_crs("EPSG:32633")
    effis = effis.drop_duplicates(subset="id")
    effis_wgs = gpd.read_file(EFFIS).to_crs("EPSG:4326").drop_duplicates(subset="id")

    official = gpd.read_file(OFFICIAL).to_crs("EPSG:32633")
    official_wgs = gpd.read_file(OFFICIAL).to_crs("EPSG:4326")
    official[DATE_COL] = pd.to_datetime(official[DATE_COL], unit="ms")

    effis_dates = pd.to_datetime(effis_wgs["FIREDATE"])

    # direction 1: EFFIS -> official
    effis_matched = 0
    for idx in effis.index:
        fdate = effis_dates.loc[idx]
        candidates = official[(official[DATE_COL] - fdate).abs().dt.days <= MATCH_DAYS]
        if len(candidates):
            dists = candidates.geometry.distance(effis.loc[idx].geometry) / 1000
            if (dists <= MATCH_KM).any():
                effis_matched += 1

    # direction 2: official -> EFFIS (the more interesting number)
    official_matched_flags = []
    for idx in official.index:
        odate = official.loc[idx, DATE_COL]
        candidates = effis[(effis_dates - odate).abs().dt.days <= MATCH_DAYS]
        matched = False
        if len(candidates):
            dists = candidates.geometry.distance(official.loc[idx].geometry) / 1000
            matched = bool((dists <= MATCH_KM).any())
        official_matched_flags.append(matched)

    official_wgs["matched_by_effis"] = official_matched_flags
    official_wgs[DATE_COL] = pd.to_datetime(official_wgs[DATE_COL], unit="ms")

    summary = pd.DataFrame([{
        "n_effis_fires": len(effis),
        "n_effis_matched_to_official_record": effis_matched,
        "pct_effis_confirmed": round(100 * effis_matched / len(effis), 1),
        "n_official_fires": len(official),
        "n_official_matched_by_effis": sum(official_matched_flags),
        "n_official_NOT_detected_by_effis": len(official) - sum(official_matched_flags),
        "pct_official_missed_by_effis": round(100 * (len(official) - sum(official_matched_flags)) / len(official), 1),
    }])
    summary.to_csv(OUT_SUMMARY, index=False)
    print(summary.T.to_string())

    missed = official_wgs[~official_wgs["matched_by_effis"]][[COMUNE_COL, LOCALITA_COL, DATE_COL, AREA_COL]]
    missed = missed.rename(columns={COMUNE_COL: "comune", LOCALITA_COL: "localita", DATE_COL: "date", AREA_COL: "area_ha"})
    missed = missed.sort_values("area_ha", ascending=False)
    missed.to_csv(OUT_MISSED, index=False)
    print(f"\nSaved {OUT_MISSED} ({len(missed)} official fires with no EFFIS match)")
    print("\nLargest official fires EFFIS never detected:")
    print(missed.head(15).to_string())


if __name__ == "__main__":
    main()
