"""Same extraction as extract_comune_boundary.py, for Carlentini (Fenice
Verde's other pilot comune, Provincia di Siracusa) - completing the actual
two-comune pitch rather than San Mauro Castelverde alone.
"""
import geopandas as gpd

ISTAT_COMUNE_CODE = "89006"
SRC = "data/raw/istat/Com01012026/Com01012026_WGS84.shp"
OUT = "data/processed/carlentini_boundary.geojson"


def main():
    gdf = gpd.read_file(SRC)
    gdf["PRO_COM"] = gdf["PRO_COM"].astype(str)
    comune = gdf[gdf["PRO_COM"] == ISTAT_COMUNE_CODE]
    assert len(comune) == 1
    comune = comune.to_crs("EPSG:4326")
    comune.to_file(OUT, driver="GeoJSON")
    bounds = comune.total_bounds
    area_km2 = comune.to_crs("EPSG:32633").area.iloc[0] / 1e6
    print(f"Saved {OUT}")
    print(f"COMUNE: {comune.iloc[0]['COMUNE']}, PRO_COM: {comune.iloc[0]['PRO_COM']}")
    print(f"Bounds: {bounds}, Area: {area_km2:.1f} km2")


if __name__ == "__main__":
    main()
