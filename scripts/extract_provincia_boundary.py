"""Extract the Provincia di Palermo boundary (all 82 comuni, dissolved) and keep
per-comune boundaries too, for the province-wide extension of the pilot.

Source: same ISTAT national shapefile used for San Mauro Castelverde.
"""
import geopandas as gpd

COD_PROV_PALERMO = 82
SRC = "data/raw/istat/Com01012026/Com01012026_WGS84.shp"
OUT_COMUNI = "data/processed/palermo_comuni.geojson"
OUT_DISSOLVED = "data/processed/palermo_provincia_boundary.geojson"


def main():
    gdf = gpd.read_file(SRC)
    palermo = gdf[gdf["COD_PROV"] == COD_PROV_PALERMO].to_crs("EPSG:4326")
    palermo.to_file(OUT_COMUNI, driver="GeoJSON")

    dissolved = palermo.dissolve()
    dissolved.to_file(OUT_DISSOLVED, driver="GeoJSON")

    area_km2 = palermo.to_crs("EPSG:32633").area.sum() / 1e6
    print(f"Saved {len(palermo)} comuni to {OUT_COMUNI}")
    print(f"Saved dissolved province boundary to {OUT_DISSOLVED}")
    print(f"Total area: {area_km2:.1f} km2")
    print(f"Bounds: {palermo.total_bounds}")


if __name__ == "__main__":
    main()
