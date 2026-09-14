"""Build the interactive map deliverable: EFFIS fire polygons, matched cadastral
parcels, Fenice Verde's own catasto record, and the two validated Prithvi
high-resolution detections, with clear source attribution per layer.

Attribution (required in any output):
- EFFIS burnt-area data: Copernicus/JRC, EU Data License
- Cadastral parcels: Agenzia delle Entrate, CC BY 4.0
- Fenice Verde SIF catasto: osservatorioincendi.org
- Prithvi-EO-2.0-300M-BurnScars: IBM/NASA, Apache 2.0
"""
import json

import folium
import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.warp import transform_geom

BOUNDARY = "data/processed/san_mauro_boundary.geojson"
FIRES = "data/processed/effis_sanmauro_2018_2025.geojson"
PARCELS_MATCHED = "data/processed/fire_parcel_matches.geojson"
GAP_CSV = "data/processed/gap_analysis_vs_feniceverde.csv"
IGNITION_CSV = "data/processed/ignition_context_flags.csv"
SIF = "data/raw/sif_sanmauro.geojson"
PRITHVI_TIBERIO = "output/prithvi_tiberio/pred_HLS.S30.T33SVC.2023262T094659_tiberio_merged.tiff"
PRITHVI_POLLINA = "output/prithvi_pollina/pred_HLS.S30.T33SVB.2023267T095031_pollina_merged.tiff"
OUT = "output/san_mauro_wildfire_map.html"


def prithvi_mask_to_geojson(tiff_path):
    """Polygonize a Prithvi prediction raster (burned=255) into WGS84 polygons."""
    from rasterio.features import shapes
    from shapely.geometry import shape as shapely_shape

    with rasterio.open(tiff_path) as src:
        arr = src.read(1)
        transform = src.transform
        crs = src.crs
        polys = []
        for geom, val in shapes(arr, mask=arr > 0, transform=transform):
            geom_wgs84 = transform_geom(crs, "EPSG:4326", geom)
            polys.append(shapely_shape(geom_wgs84))
    if not polys:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return gpd.GeoDataFrame(geometry=polys, crs="EPSG:4326")


def main():
    boundary = gpd.read_file(BOUNDARY).to_crs("EPSG:4326")
    fires = gpd.read_file(FIRES).to_crs("EPSG:4326")
    parcels = gpd.read_file(PARCELS_MATCHED).to_crs("EPSG:4326")
    gap_df = pd.read_csv(GAP_CSV)
    ignition_df = pd.read_csv(IGNITION_CSV)

    fires["FIREDATE"] = fires["FIREDATE"].astype(str)
    fires["id"] = fires["id"].astype(str)
    gap_df["fire_id"] = gap_df["fire_id"].astype(str)
    fires = fires.merge(gap_df[["fire_id", "in_feniceverde_sif_catasto"]], left_on="id", right_on="fire_id", how="left")
    fires["id"] = fires["id"].astype(str)
    ignition_df["fire_id"] = ignition_df["fire_id"].astype(str)
    fires = fires.merge(ignition_df[["fire_id", "day_or_night_ignition", "geometric_shape_flag", "pastureland_context_flag"]], left_on="id", right_on="fire_id", how="left")

    centre = boundary.geometry.iloc[0].centroid
    m = folium.Map(location=[centre.y, centre.x], zoom_start=12, tiles="OpenStreetMap")

    folium.GeoJson(
        boundary.__geo_interface__,
        name="San Mauro Castelverde boundary (ISTAT)",
        style_function=lambda x: {"color": "black", "weight": 2, "fill": False},
    ).add_to(m)

    fire_layer = folium.FeatureGroup(name="EFFIS fires 2018-2025 (Copernicus/JRC)")
    for _, f in fires.iterrows():
        in_catasto = f.get("in_feniceverde_sif_catasto")
        color = "green" if in_catasto is True else ("red" if in_catasto is False else "orange")
        popup = folium.Popup(
            f"<b>Date:</b> {f['FIREDATE']}<br>"
            f"<b>EFFIS area:</b> {f['AREA_HA']} ha<br>"
            f"<b>EFFIS commune field:</b> {f['COMMUNE']}<br>"
            f"<b>In Fenice Verde catasto:</b> {in_catasto}<br>"
            f"<b>Day/night:</b> {f.get('day_or_night_ignition','n/a')}<br>"
            f"<b>Geometric shape flag:</b> {f.get('geometric_shape_flag','n/a')}<br>"
            f"<b>Pastureland context:</b> {f.get('pastureland_context_flag','n/a')}",
            max_width=300,
        )
        folium.GeoJson(
            f.geometry.__geo_interface__,
            style_function=lambda x, c=color: {"color": c, "weight": 1, "fillColor": c, "fillOpacity": 0.5},
            popup=popup,
        ).add_to(fire_layer)
    fire_layer.add_to(m)

    parcel_layer = folium.FeatureGroup(name="Matched cadastral particelle (Agenzia delle Entrate, CC BY 4.0)", show=False)
    folium.GeoJson(
        parcels.__geo_interface__,
        style_function=lambda x: {"color": "purple", "weight": 0.5, "fillOpacity": 0.1},
        tooltip=folium.GeoJsonTooltip(fields=["NATIONALCADASTRALREFERENCE"]),
    ).add_to(parcel_layer)
    parcel_layer.add_to(m)

    try:
        sif = gpd.read_file(SIF).to_crs("EPSG:4326")
        sif_layer = folium.FeatureGroup(name="Fenice Verde SIF catasto 2024 (osservatorioincendi.org)")
        for _, s in sif.iterrows():
            folium.GeoJson(
                s.geometry.__geo_interface__,
                style_function=lambda x: {"color": "blue", "weight": 2, "fillOpacity": 0.2},
                popup=f"{s.get('LOCALITA')} - {s.get('DTAINIZIOF')} - {s.get('TOTSUP')} ha (Fenice Verde SIF record)",
            ).add_to(sif_layer)
        sif_layer.add_to(m)
    except Exception as e:
        print(f"SIF layer skipped: {e}")

    prithvi_layer = folium.FeatureGroup(name="Prithvi high-res detection (validated fires only - IBM/NASA, Apache 2.0)")
    for label, path in [("Contrada Tiberio", PRITHVI_TIBERIO), ("Foce del fiume Pollina", PRITHVI_POLLINA)]:
        try:
            gdf = prithvi_mask_to_geojson(path)
            if len(gdf):
                folium.GeoJson(
                    gdf.__geo_interface__,
                    style_function=lambda x: {"color": "darkred", "weight": 1, "fillColor": "darkred", "fillOpacity": 0.6},
                    popup=f"Prithvi detection near {label} (area estimates indicative, not precise - see validation note)",
                ).add_to(prithvi_layer)
        except Exception as e:
            print(f"Prithvi layer for {label} skipped: {e}")
    prithvi_layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    legend_html = """
    <div style="position: fixed; bottom: 20px; left: 20px; z-index: 1000; background: white;
                padding: 10px; border: 1px solid #999; border-radius: 4px; font-size: 12px; max-width: 280px;">
    <b>Fire colour key</b><br>
    <span style="color:green">&#9632;</span> in Fenice Verde's catasto<br>
    <span style="color:red">&#9632;</span> NOT in Fenice Verde's catasto<br>
    <span style="color:orange">&#9632;</span> catasto coverage n/a for this year (SIF is 2024-only)<br>
    <br><b>Sources:</b> EFFIS (Copernicus/JRC, EU Data License) &middot;
    Cadastral parcels (Agenzia delle Entrate, CC BY 4.0) &middot;
    Catasto (osservatorioincendi.org, Fenice Verde) &middot;
    Prithvi-EO-2.0-300M-BurnScars (IBM/NASA, Apache 2.0)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save(OUT)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
