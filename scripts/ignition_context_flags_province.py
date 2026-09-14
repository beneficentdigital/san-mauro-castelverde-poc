"""Province-wide version of ignition_context_flags.py - same method, applied to
all 588 unique Palermo province fires rather than just San Mauro Castelverde's 14.
"""
from __future__ import annotations

import numpy as np
import geopandas as gpd
import pandas as pd
from astral import LocationInfo
from astral.sun import sun

FIRES = "data/processed/effis_palermo_province_2018_2025.geojson"
OUT = "data/processed/ignition_context_flags_palermo_province.csv"

STRAIGHT_ANGLE_TOL_DEG = 8
STRAIGHT_MIN_FRAC = 0.35


def day_or_night(dt, lon, lat):
    if pd.isna(dt):
        return "unknown"
    loc = LocationInfo(latitude=lat, longitude=lon)
    try:
        s = sun(loc.observer, date=dt.date())
    except Exception:
        return "unknown"
    t = dt.tz_localize("UTC") if dt.tzinfo is None else dt
    return "day" if s["sunrise"] <= t <= s["sunset"] else "night"


def compactness(geom):
    area, perim = geom.area, geom.length
    return 4 * np.pi * area / (perim**2) if perim else np.nan


def straight_edge_fraction(geom, angle_tol=STRAIGHT_ANGLE_TOL_DEG):
    geoms = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    total_len, straight_len = 0.0, 0.0
    for g in geoms:
        coords = list(g.exterior.coords)
        n = len(coords)
        for i in range(n - 1):
            p0, p1, p2 = coords[i - 1], coords[i], coords[(i + 1) % (n - 1)]
            seg_len = ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5
            total_len += seg_len
            v1 = np.array([p1[0] - p0[0], p1[1] - p0[1]])
            v2 = np.array([p2[0] - p1[0], p2[1] - p1[1]])
            if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
                continue
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            angle_deg = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
            if angle_deg < angle_tol:
                straight_len += seg_len
    return straight_len / total_len if total_len else np.nan


def main():
    fires = gpd.read_file(FIRES).to_crs("EPSG:4326")
    fires = fires.drop_duplicates(subset="id").reset_index(drop=True)
    fires_m = fires.to_crs("EPSG:32633")

    rows = []
    for idx, fire in fires.iterrows():
        centroid = fire.geometry.centroid
        dt = pd.to_datetime(fire["FIREDATE"], errors="coerce")
        dn = day_or_night(dt, centroid.x, centroid.y)

        geom_m = fires_m.loc[idx].geometry
        comp = compactness(geom_m)
        straight_frac = straight_edge_fraction(geom_m)
        geometric_flag = bool(straight_frac >= STRAIGHT_MIN_FRAC) if straight_frac == straight_frac else None

        agri_pct = float(fire.get("AGRIAREAS", 0) or 0)

        rows.append({
            "fire_id": fire["id"],
            "comune": fire["COMMUNE"],
            "fire_date": fire["FIREDATE"],
            "area_ha": fire["AREA_HA"],
            "day_or_night_ignition": dn,
            "pct_agricultural_landcover": round(agri_pct, 1),
            "pastureland_context_flag": "near/in agricultural land" if agri_pct > 30 else "not predominantly agricultural",
            "shape_compactness": round(comp, 3) if comp == comp else None,
            "straight_edge_fraction": round(straight_frac, 3) if straight_frac == straight_frac else None,
            "geometric_shape_flag": geometric_flag,
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"Saved {OUT}")
    print(f"{len(df)} unique fires scored")
    print(f"{df['geometric_shape_flag'].sum()} flagged with unusually straight/geometric edges")
    print(f"{(df['day_or_night_ignition']=='night').sum()} started at night")
    print(f"{(df['pastureland_context_flag']=='near/in agricultural land').sum()} near/in agricultural land")
    print("\nComuni with the most geometric-flagged fires:")
    print(df[df["geometric_shape_flag"] == True]["comune"].value_counts().head(10))


if __name__ == "__main__":
    main()
