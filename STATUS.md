# San Mauro Castelverde Wildfire POC — Status

## Confirmed so far

- **ISTAT comune code:** 082065 (San Mauro Castelverde, Città Metropolitana di Palermo). Cross-checked via ottomilacensus.istat.it and comuni-italiani.it.
- **EFFIS WMS** (`maps.effis.emergency.copernicus.eu/effis`) is live. `GetCapabilities` shows only **MODIS-based** yearly burnt-area layers (`modis.ba.poly.2018`…`2025`) plus near-real-time hotspot/point layers — there is no Sentinel-2 "damage assessment" layer exposed on this particular WMS endpoint.
- **Cadastral WFS** (`wfs.cartografia.agenziaentrate.gov.it`) is live, standard INSPIRE schema: `CP:CadastralParcel`, `CP:CadastralZoning`. Need to confirm the INSPIRE parcel ID format actually carries foglio/particella (Italy typically encodes it in the `nationalCadastralReference` / `inspireId` field — will confirm against the point-lookup AJAX endpoint).
- **GFW Data API** requires a free account + self-service API key (expires after 1 year, `x-api-key` header). No bulk/anonymous access.

## Important correction to the brief's EFFIS assumptions

Two different EFFIS "minimum mapped size" numbers exist, and it matters which one we build on:

- The **pan-European automatic burnt-area product** (what the WMS layers above serve): ~30ha minimum pre-2018 (MODIS), and Sentinel-2 since 2018 pushes that down — EFFIS's own technical page says Sentinel-2 "allows detection of fires below the 30ha threshold" but doesn't commit to an exact floor lower than that.
- The **JRC bulk-download "Damage Assessment" dataset** (DOI 10.2905/JRC.TB3JJQG, the one the brief names as the fallback) is explicitly described as covering "forest fires with a final size of at least **50 ha**." It also has no direct shapefile/GeoJSON download link on its catalogue page — only a generic RDF/CSV export and a link back to the EFFIS Viewer.

**Consequence:** both of Fenice Verde's own documented 2023 validation fires (Contrada Tiberio, ~2ha; ZSC Foce del fiume Pollina, ~12ha) are very likely **below EFFIS's practical detection floor**, on either product. EFFIS will probably return nothing for both validation fires. That's not a pipeline bug — it's the actual, honest finding, and it substantially strengthens the pitch: it's precisely the gap that GFW/FireHR/Prithvi and comparison against Fenice Verde's own manual catasto are there to fill. But it means the validation note (deliverable 4) needs to say "EFFIS: no detection (below its mapping floor, as expected)" rather than quietly hiding a failed check — and the one-pager should lead with GFW+FireHR+Prithvi as the layers that actually catch small fires, with EFFIS framed as the large-fire cross-check it actually is, not the primary detector the brief's memory model assumed.

## Environment

- Python 3.9.6, pip 21.2.4, network access to PyPI confirmed. No geopandas/rasterio/folium/earthengine/gdal installed yet — will need a venv + install pass.
- Project scaffold created at `/Users/user/san-mauro-wildfire-poc/`.

## Open items that need you, not more research

1. **Meeting date** — brief says "Thursday, [confirm date]." Today is Mon 2026-09-14, so I'm assuming **Thu 2026-09-17** unless you say otherwise.
2. **GFW API key** — self-serve account creation (ties to an email + accepting WRI's terms). Want me to register one, or will you/Hannah do that and hand me the key?
3. **Google Earth Engine auth** — brief says Hannah already has GEE access from the river-recovery-watch project. This machine has no `earthengine` credentials configured yet. Needed only for FireHR (later in the build order), not blocking today.
4. Confirm you want this built under a **new standalone repo** at `~/san-mauro-wildfire-poc` (not nested in `ncc/` or another existing project) — that's what I've set up.
