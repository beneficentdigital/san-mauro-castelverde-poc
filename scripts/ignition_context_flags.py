"""Compute ignition-context flags per fire: transparent, published-feature-based
scoring - NOT a trained classifier. This distinction must survive into every
output (see brief section 5).

Flags computed:
- day/night ignition: from EFFIS's own FIREDATE timestamp + sunrise/sunset for
  that lat/lon/date (astral). More precise than trying to correlate with a
  separate VIIRS Day/Night Band pass, and needs no extra imagery.
- land use / pastureland context: EFFIS already computes a CORINE-Land-Cover-
  derived breakdown per fire (AGRIAREAS = % agricultural areas, among others) -
  reused directly rather than re-deriving from raw CORINE.
- burn-scar shape: compactness (4*pi*area/perimeter^2, 1.0 = circle, lower =
  more irregular) and a straight-edge fraction, as a measured version of Fenice
  Verde's own manual "fuoco geometra" heuristic.

NOT computed (documented gap, not silently skipped): distance to nearest road.
OpenStreetMap's Overpass API (overpass-api.de and the kumi.systems/private.coffee
mirror) is unreachable from this environment - confirmed via multiple mirrors,
GET and POST, with and without custom headers, while general internet and other
unrelated hosts (JRC, PyPI) work fine. Worth retrying from a different network
before the meeting if the road-proximity flag matters for the deck.
"""
import numpy as np
import geopandas as gpd
import pandas as pd
from astral import LocationInfo
from astral.sun import sun
from datetime import datetime

FIRES = "data/processed/effis_sanmauro_2018_2025.geojson"
OUT = "data/processed/ignition_context_flags.csv"

STRAIGHT_ANGLE_TOL_DEG = 8  # consecutive-edge angle within this of 180deg counts as "straight"
STRAIGHT_MIN_FRAC = 0.35  # flag as "geometric" if at least this fraction of perimeter is straight runs


def day_or_night(dt: pd.Timestamp, lon: float, lat: float) -> str:
    if pd.isna(dt):
        return "unknown"
    loc = LocationInfo(latitude=lat, longitude=lon)
    try:
        s = sun(loc.observer, date=dt.date())
    except Exception:
        return "unknown"
    t = dt.tz_localize("UTC") if dt.tzinfo is None else dt
    return "day" if s["sunrise"] <= t <= s["sunset"] else "night"


def compactness(geom) -> float:
    area = geom.area
    perim = geom.length
    if perim == 0:
        return np.nan
    return 4 * np.pi * area / (perim**2)


def straight_edge_fraction(geom, angle_tol=STRAIGHT_ANGLE_TOL_DEG) -> float:
    """Fraction of the boundary length that sits in runs of near-collinear
    consecutive vertices - a measured version of the 'fuoco geometra' heuristic."""
    if geom.geom_type == "MultiPolygon":
        geoms = list(geom.geoms)
    else:
        geoms = [geom]

    total_len = 0.0
    straight_len = 0.0
    for g in geoms:
        coords = list(g.exterior.coords)
        n = len(coords)
        for i in range(n - 1):
            p0 = coords[i - 1]
            p1 = coords[i]
            p2 = coords[(i + 1) % (n - 1)]
            seg_len = ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5
            total_len += seg_len
            v1 = np.array([p1[0] - p0[0], p1[1] - p0[1]])
            v2 = np.array([p2[0] - p1[0], p2[1] - p1[1]])
            if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
                continue
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            angle_deg = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
            if angle_deg < angle_tol:  # near-straight continuation
                straight_len += seg_len
    return straight_len / total_len if total_len else np.nan


def main():
    fires = gpd.read_file(FIRES).to_crs("EPSG:4326")
    fires_m = fires.to_crs("EPSG:32633")  # metric CRS for shape metrics

    rows = []
    for idx, fire in fires.iterrows():
        centroid = fire.geometry.centroid
        dt = pd.to_datetime(fire["FIREDATE"], errors="coerce")
        dn = day_or_night(dt, centroid.x, centroid.y)

        geom_m = fires_m.loc[idx].geometry
        comp = compactness(geom_m)
        straight_frac = straight_edge_fraction(geom_m)
        geometric_flag = bool(straight_frac >= STRAIGHT_MIN_FRAC) if not np.isnan(straight_frac) else None

        agri_pct = float(fire.get("AGRIAREAS", 0) or 0)

        rows.append(
            {
                "fire_id": fire["id"],
                "fire_date": fire["FIREDATE"],
                "day_or_night_ignition": dn,
                "pct_agricultural_landcover": round(agri_pct, 1),
                "pastureland_context_flag": "near/in agricultural land" if agri_pct > 30 else "not predominantly agricultural",
                "shape_compactness": round(comp, 3) if comp == comp else None,
                "straight_edge_fraction": round(straight_frac, 3) if straight_frac == straight_frac else None,
                "geometric_shape_flag": geometric_flag,
                "distance_to_road_m": None,  # documented gap - Overpass API unreachable, see module docstring
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"Saved {OUT}")
    print(df.to_string())
    print(f"\n{df['geometric_shape_flag'].sum()} of {len(df)} fires flagged as having unusually straight/geometric edges")
    print("NOTE: this is transparent feature-based scoring, not a trained ignition-cause classifier - label it that way in any output.")


if __name__ == "__main__":
    main()
