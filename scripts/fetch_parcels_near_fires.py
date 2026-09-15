"""Fetch cadastral parcels only near detected fires, province-wide.

Blanket-fetching every parcel in Palermo province (44x San Mauro Castelverde's
area) the way scripts/fetch_cadastral_parcels.py did for one comune would mean
tens of thousands of tiled WFS requests - hours, for parcels that mostly never
touch a fire. Fires cover ~17% of the province's area at most, so instead:
buffer each detected fire slightly and fetch only parcels in that buffer.

Reuses the same tiling logic proven for San Mauro (the WFS silently returns
zero features for bbox queries wider than ~0.015 degrees, confirmed by
testing) - large fires get their buffer split into a small grid of safe-sized
tiles; most fires are small enough to fit in a single tile.
"""
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

WFS_URL = "https://wfs.cartografia.agenziaentrate.gov.it/inspire/wfs/owfs01.php"
FIRES = "data/processed/effis_palermo_province_2018_2025.geojson"
OUT_PARCELS = "data/processed/palermo_province_matched_parcels.geojson"
OUT_MATCHES = "data/processed/palermo_province_fire_parcel_matches.csv"

BUFFER_DEG = 0.0015  # ~150m, enough to catch edge parcels without over-matching neighbours
TILE_SIZE = 0.012  # same safe tile size proven for San Mauro
COUNT = 500
MAX_RETRIES = 3


def fetch_tile(minlat, minlon, maxlat, maxlon, start_index=0):
    params = {
        "language": "ita", "SERVICE": "WFS", "VERSION": "2.0.0",
        "TYPENAMES": "CP:CadastralParcel", "SRSNAME": "urn:ogc:def:crs:EPSG::6706",
        "BBOX": f"{minlat},{minlon},{maxlat},{maxlon}",
        "REQUEST": "GetFeature", "COUNT": COUNT, "STARTINDEX": start_index,
    }
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(WFS_URL, params=params, timeout=30)
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            time.sleep(2**attempt)
    return None


def fetch_parcels_for_bounds(minlon, minlat, maxlon, maxlat):
    """Tile the bounds into safe-sized chunks and fetch all parcels within."""
    lat_edges = np.arange(minlat, maxlat + TILE_SIZE, TILE_SIZE)
    lon_edges = np.arange(minlon, maxlon + TILE_SIZE, TILE_SIZE)
    if len(lat_edges) < 2:
        lat_edges = np.array([minlat, minlat + TILE_SIZE])
    if len(lon_edges) < 2:
        lon_edges = np.array([minlon, minlon + TILE_SIZE])

    tile_gdfs = []
    for i in range(len(lat_edges) - 1):
        for j in range(len(lon_edges) - 1):
            start_index = 0
            while True:
                content = fetch_tile(lat_edges[i], lon_edges[j], lat_edges[i + 1], lon_edges[j + 1], start_index)
                if not content:
                    break
                with open("/tmp/_parcel_tile.gml", "wb") as f:
                    f.write(content)
                try:
                    gdf = gpd.read_file("/tmp/_parcel_tile.gml")
                except Exception:
                    break
                if len(gdf) == 0:
                    break
                tile_gdfs.append(gdf)
                if len(gdf) < COUNT:
                    break
                start_index += COUNT
    if not tile_gdfs:
        return gpd.GeoDataFrame()
    return gpd.GeoDataFrame(pd.concat(tile_gdfs, ignore_index=True), crs="EPSG:6706")


LARGE_FIRE_HA = 300  # above this, parcel-level matching isn't actionable (nobody
# reviews thousands of individual parcels for one regional mega-complex) - flag
# these separately instead of spending disproportionate WFS requests on them


def main():
    fires = gpd.read_file(FIRES).to_crs("EPSG:4326")
    fires_unique = fires.drop_duplicates(subset="id").reset_index(drop=True)
    fires_unique["AREA_HA"] = fires_unique["AREA_HA"].astype(float)

    large_fires = fires_unique[fires_unique["AREA_HA"] > LARGE_FIRE_HA]
    fires_unique = fires_unique[fires_unique["AREA_HA"] <= LARGE_FIRE_HA].reset_index(drop=True)
    print(f"Matching parcels for {len(fires_unique)} fires <= {LARGE_FIRE_HA}ha")
    print(f"({len(large_fires)} larger fires flagged separately, not parcel-matched - see output)")

    large_fires[["id", "FIREDATE", "COMMUNE", "AREA_HA"]].to_csv(
        "data/processed/palermo_province_large_fires_not_parcel_matched.csv", index=False
    )

    all_parcels = []
    match_rows = []
    seen_parcel_ids = set()

    for i, fire in fires_unique.iterrows():
        t0 = time.time()
        buffered = fire.geometry.buffer(BUFFER_DEG)
        minlon, minlat, maxlon, maxlat = buffered.bounds
        parcels = fetch_parcels_for_bounds(minlon, minlat, maxlon, maxlat)
        print(f"  [{i+1}/{len(fires_unique)}] fire {fire['id']} ({fire['AREA_HA']}ha, {fire['COMMUNE']}): "
              f"{len(parcels)} raw parcels in {time.time()-t0:.1f}s", flush=True)

        if len(parcels):
            parcels = parcels.to_crs("EPSG:4326")
            matched = parcels[parcels.geometry.intersects(fire.geometry)]
            matched = matched.drop_duplicates(subset="gml_id")
            new_parcels = matched[~matched["gml_id"].isin(seen_parcel_ids)]
            if len(new_parcels):
                all_parcels.append(new_parcels)
                seen_parcel_ids.update(new_parcels["gml_id"])
        else:
            matched = gpd.GeoDataFrame()

        match_rows.append({
            "fire_id": fire["id"],
            "fire_date": fire["FIREDATE"],
            "comune": fire["COMMUNE"],
            "area_ha_effis": fire["AREA_HA"],
            "n_parcels_matched": len(matched),
            "parcel_refs": "; ".join(matched["NATIONALCADASTRALREFERENCE"]) if len(matched) else "",
        })

        if (i + 1) % 25 == 0 or i == len(fires_unique) - 1:
            total_parcels = sum(len(p) for p in all_parcels)
            print(f"  {i+1}/{len(fires_unique)} fires processed, {total_parcels} unique parcels matched so far")

    match_df = pd.DataFrame(match_rows)
    match_df.to_csv(OUT_MATCHES, index=False)
    print(f"\nSaved {OUT_MATCHES}")

    if all_parcels:
        result = gpd.GeoDataFrame(pd.concat(all_parcels, ignore_index=True), crs="EPSG:4326")
        result.to_file(OUT_PARCELS, driver="GeoJSON")
        print(f"Saved {len(result)} matched parcels to {OUT_PARCELS}")
    else:
        print("No parcels matched.")

    print(f"\n{(match_df['n_parcels_matched']>0).sum()} of {len(match_df)} fires matched at least one parcel")


if __name__ == "__main__":
    main()
