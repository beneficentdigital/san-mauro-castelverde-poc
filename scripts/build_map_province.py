"""Province-wide map: fire polygons across all 82 Palermo comuni, with matched
parcel counts in popups. Doesn't render all 75,769 individual matched parcels
directly (unlike the single-comune map) - at this scale that would make the
page too heavy for a browser to load smoothly. Parcel-level detail stays in
data/processed/palermo_province_fire_parcel_matches.csv (per-fire) and
palermo_province_matched_parcels.geojson (full parcel shapes) for anyone who
wants to drill into a specific fire in GIS software.
"""
import folium
import geopandas as gpd
import pandas as pd

PROVINCE_BOUNDARY = "data/processed/palermo_provincia_boundary.geojson"
COMUNI = "data/processed/palermo_comuni.geojson"
FIRES = "data/processed/effis_palermo_province_2018_2025.geojson"
MATCHES = "data/processed/palermo_province_fire_parcel_matches.csv"
LARGE_FIRES = "data/processed/palermo_province_large_fires_not_parcel_matched.csv"
OUT = "output/palermo_province_wildfire_map.html"


def area_to_color(area_ha):
    if area_ha > 500:
        return "#7a0c0c"
    if area_ha > 100:
        return "#c2410c"
    if area_ha > 20:
        return "#e08a2c"
    return "#e8b93f"


def main():
    province = gpd.read_file(PROVINCE_BOUNDARY).to_crs("EPSG:4326")
    comuni = gpd.read_file(COMUNI).to_crs("EPSG:4326")
    fires = gpd.read_file(FIRES).to_crs("EPSG:4326")
    fires = fires.drop_duplicates(subset="id")
    fires["AREA_HA"] = fires["AREA_HA"].astype(float)

    matches = pd.read_csv(MATCHES)
    matches["fire_id"] = matches["fire_id"].astype(str)
    fires["id"] = fires["id"].astype(str)
    fires = fires.merge(matches[["fire_id", "n_parcels_matched"]], left_on="id", right_on="fire_id", how="left")

    large_fires_ids = set()
    try:
        large_df = pd.read_csv(LARGE_FIRES)
        large_fires_ids = set(large_df["id"].astype(str))
    except FileNotFoundError:
        pass

    centre = province.geometry.iloc[0].centroid
    m = folium.Map(location=[centre.y, centre.x], zoom_start=9, tiles="OpenStreetMap")

    folium.GeoJson(
        province.__geo_interface__,
        name="Provincia di Palermo boundary",
        style_function=lambda x: {"color": "black", "weight": 2, "fill": False},
    ).add_to(m)

    comuni_layer = folium.FeatureGroup(name="Comune boundaries", show=False)
    folium.GeoJson(
        comuni.__geo_interface__,
        style_function=lambda x: {"color": "#888", "weight": 0.7, "fill": False},
        tooltip=folium.GeoJsonTooltip(fields=["COMUNE"]),
    ).add_to(comuni_layer)
    comuni_layer.add_to(m)

    fire_layer = folium.FeatureGroup(name=f"EFFIS fires 2018-2025 ({len(fires)} total)")
    for _, f in fires.iterrows():
        is_large = f["id"] in large_fires_ids
        n_parcels = f.get("n_parcels_matched")
        parcels_note = (
            "large regional complex - not parcel-matched (see large-fires CSV)"
            if is_large
            else (f"{int(n_parcels)} candidate parcels matched" if pd.notna(n_parcels) else "no parcels matched")
        )
        popup = folium.Popup(
            f"<b>{f['COMMUNE']}</b><br>"
            f"Date: {f['FIREDATE']}<br>"
            f"Area: {f['AREA_HA']} ha<br>"
            f"{parcels_note}",
            max_width=280,
        )
        color = "#4a0404" if is_large else area_to_color(f["AREA_HA"])
        folium.GeoJson(
            f.geometry.__geo_interface__,
            style_function=lambda x, c=color: {"color": c, "weight": 1, "fillColor": c, "fillOpacity": 0.55},
            popup=popup,
        ).add_to(fire_layer)
    fire_layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    legend_html = """
    <div style="position: fixed; bottom: 20px; left: 20px; z-index: 1000; background: white;
                padding: 10px; border: 1px solid #999; border-radius: 4px; font-size: 12px; max-width: 300px;">
    <b>Fire size key</b><br>
    <span style="color:#e8b93f">&#9632;</span> &le;20 ha
    <span style="color:#e08a2c">&#9632;</span> 20-100 ha
    <span style="color:#c2410c">&#9632;</span> 100-500 ha
    <span style="color:#7a0c0c">&#9632;</span> &gt;500 ha
    <span style="color:#4a0404">&#9632;</span> large complex, not parcel-matched
    <br><br>Click a fire for details and candidate parcel count. Full parcel-level
    lists: <code>data/processed/palermo_province_fire_parcel_matches.csv</code>
    <br><br><b>Sources:</b> EFFIS (Copernicus/JRC, EU Data License) &middot;
    Cadastral parcels (Agenzia delle Entrate, CC BY 4.0) &middot; ISTAT comune boundaries
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save(OUT)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
