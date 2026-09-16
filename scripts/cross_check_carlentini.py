"""EFFIS vs official regional registry cross-check for Carlentini - same
method as cross_check_regional_registry.py (Palermo province), applied to
Fenice Verde's other pilot comune to complete the two-comune picture.
"""
import geopandas as gpd
import pandas as pd

OFFICIAL = "data/processed/regione_censimento_incendi_sicilia_2018_2025.geojson"
EFFIS = "data/processed/effis_carlentini_2018_2025.geojson"
OUT = "data/processed/carlentini_effis_vs_official.csv"

COMUNE_COL = "DATI_WEB.DBO.AAAMAMCOMU.DESCRIPTION"
DATE_COL = "DATI_WEB.DBO.DFCNSIINCD_DENORM.DTAINIZIOFUOCO"
AREA_COL = "DATI_WEB.DBO.DFCNSIINCD_DENORM.TOTSUP"
LOC_COL = "DATI_WEB.DBO.DFCNSIINCD_DENORM.LOCALITA"
MATCH_KM = 1.5
MATCH_DAYS = 5


def main():
    official = gpd.read_file(OFFICIAL).to_crs("EPSG:32633")
    official[DATE_COL] = pd.to_datetime(official[DATE_COL], unit="ms")
    c_off = official[official[COMUNE_COL] == "CARLENTINI"].copy()

    effis = gpd.read_file(EFFIS).to_crs("EPSG:32633")
    effis["FIREDATE"] = pd.to_datetime(effis["FIREDATE"])

    rows = []
    for _, o in c_off.iterrows():
        if pd.isna(o[DATE_COL]):
            rows.append({"localita": o[LOC_COL], "area_ha": o[AREA_COL], "date": None, "nearest_effis_km": None, "matched": False})
            continue
        cands = effis[(effis["FIREDATE"] - o[DATE_COL]).abs().dt.days <= MATCH_DAYS]
        if len(cands):
            dists = cands.geometry.distance(o.geometry) / 1000
            best = dists.idxmin()
            matched = dists[best] <= MATCH_KM
            rows.append({
                "localita": o[LOC_COL], "area_ha": o[AREA_COL], "date": o[DATE_COL],
                "nearest_effis_km": round(dists[best], 2), "nearest_effis_area_ha": cands.loc[best, "AREA_HA"],
                "matched": matched,
            })
        else:
            rows.append({"localita": o[LOC_COL], "area_ha": o[AREA_COL], "date": o[DATE_COL], "nearest_effis_km": None, "matched": False})

    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(df.to_string())
    print(f"\n{df['matched'].sum()} of {len(df)} official Carlentini fires matched within {MATCH_KM}km/{MATCH_DAYS} days")


if __name__ == "__main__":
    main()
