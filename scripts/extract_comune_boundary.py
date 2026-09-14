"""Extract the San Mauro Castelverde comune boundary from the national ISTAT shapefile.

Source: ISTAT "Confini delle unità amministrative a fini statistici", 1 Jan 2026 edition
https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/2026/Limiti01012026.zip
License: free reuse, attribution to ISTAT.
"""
import geopandas as gpd

ISTAT_COMUNE_CODE = "82065"  # San Mauro Castelverde, Città Metropolitana di Palermo
SRC = "data/raw/istat/Com01012026/Com01012026_WGS84.shp"
OUT = "data/processed/san_mauro_boundary.geojson"


def main():
    gdf = gpd.read_file(SRC)
    gdf["PRO_COM"] = gdf["PRO_COM"].astype(str)
    comune = gdf[gdf["PRO_COM"] == ISTAT_COMUNE_CODE]
    assert len(comune) == 1, f"expected 1 match for PRO_COM={ISTAT_COMUNE_CODE}, got {len(comune)}"
    comune = comune.to_crs("EPSG:4326")
    comune.to_file(OUT, driver="GeoJSON")
    bounds = comune.total_bounds
    area_km2 = comune.to_crs("EPSG:32633").area.iloc[0] / 1e6
    print(f"Saved {OUT}")
    print(f"COMUNE: {comune.iloc[0]['COMUNE']}, PRO_COM: {comune.iloc[0]['PRO_COM']}")
    print(f"Bounds (lon/lat): {bounds}")
    print(f"Area: {area_km2:.1f} km2")


if __name__ == "__main__":
    main()
