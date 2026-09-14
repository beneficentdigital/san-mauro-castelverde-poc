# GFW Data API — geometry query issue (2026-09-14, resolved same day)

**Resolved:** the bug is version-specific, not a total platform failure as first
assumed. `v20250127` and earlier dataset versions filter by geometry correctly;
`v20250206` and later are broken. Traded off against data recency - each dated
version is a frozen snapshot as of its own creation date, not a live feed, so
`v20250127` gives full 2018-present coverage except roughly the most recent
8 months. Real VIIRS data fetched successfully via `scripts/fetch_gfw_fire_alerts.py`
using that version. Worth re-checking for a newer working version periodically.

## Original note, kept for the record

`POST /dataset/nasa_viirs_fire_alerts/{version}/query` with a `geometry` field
in the body consistently returns zero rows, even against:
- The exact real fire polygon for the 21 Sep 2023 San Mauro Castelverde/Tusa fire
- A large bbox over Rhodes, Greece during the well-documented July 2023 wildfires,
  with no date filter at all (should return thousands of historical points)

Confirmed not a network/auth issue: global queries (no geometry) return real data
immediately; a `geostore_id` was created successfully via `/geostore`. The
geometry-filter path itself appears non-functional for this dataset/version as
of today.

Parked as should-ship, not must-ship, per the agreed priority tiers. Options to
revisit later: retry once GFW ships a fix, try a different dataset version, or
pull VIIRS directly from NASA FIRMS (same underlying data, simpler API, needs
a separate free MAP_KEY emailed on signup: https://firms.modaps.eosdis.nasa.gov/api/map_key/).
