# Handover note — 2026-09-17

Written for picking this up in a fresh conversation with no memory of the
build session. Repo: `beneficentdigital/san-mauro-castelverde-poc` (this
directory). Read `docs/all_results_summary.md` first for full results,
`docs/next_phase_roadmap.md` for the fuller roadmap — this note is the
short version plus what to do right now.

## Where things stand

**The original brief (San Mauro Castelverde, for Fenice Verde) is done and
was meeting-ready as of 2026-09-17.** Map, per-fire table, one-pager
(published artifact), validation note — all complete, all in `output/` and
`docs/`. The meeting itself happens today; nothing below is needed for it.

**Everything else is follow-on work the user asked for after the brief was
already complete**: a province-wide extension to all 82 Palermo comuni, a
second pilot comune (Carlentini), and a Sicily-wide official fire registry
(7,273 labelled burn-scar polygons — the strongest data asset found all
session). Full numbers in `docs/all_results_summary.md`.

## The live thread: improving small-fire detection confidence

The core finding this session: satellites genuinely can see small fires
(proven several independent ways — dNBR found a known 2ha fire within 10m of
its true location), but **automated, unattended area/boundary estimation is
unreliable** (~40% of automated dNBR results are badly wrong, usually wild
overshoots from Sicilian seasonal vegetation-drying noise). Two real fixes
were tried and both failed honestly: RdNBR (literature-standard fix for
mixed vegetation) and a multi-image median pre-fire baseline. Don't retry
either without a new idea — both were tested properly, not abandoned early.

### Agreed next-phase to-do list, in order

1. **Try BAIS2** — a real, published Sentinel-2 burn index (verified via
   research agent, not assumed): `BAIS2 = (1 − √((B06×B07×B8A)/B04)) ×
   ((B12−B8A)/√(B12+B8A) + 1)`. Pure band math, no training, cheap to test.
   Swap it in alongside/instead of dNBR in `scripts/dnbr_detect.py`'s
   approach and re-run the San Mauro pilot validation (Tiberio ~2ha,
   Pollina ~12ha — both fires' real coordinates and known areas are in
   `docs/validation_note_2023_fires.md`) to see if it's more robust to the
   seasonal-noise problem than plain NBR.

2. **Prepare Sicily registry data for training.** The 7,273 official fire
   polygons (`data/processed/regione_censimento_incendi_sicilia_2018_2025.geojson`)
   were verified to be genuine, detailed burn-scar shapes (30-35 vertices
   for a 2ha fire, not administrative rectangles) — real training-quality
   labels, not just point records. Convert these + matching Sentinel-2/HLS
   imagery into the input format IBM/NASA's published fine-tuning recipe
   expects.

3. **Fine-tune Prithvi-EO-2.0 on that data.** Not a hopeful idea — IBM/NASA
   publish the *exact config* used to create the burn-scars checkpoint
   we're already using: `burn_scars_config.yaml` on the model's HF repo
   (huggingface.co/ibm-nasa-geospatial/Prithvi-EO-2.0-300M-BurnScars), via
   `terratorch` (already installed in `.venv311`, actively maintained,
   Apache-2.0). Adapt that same recipe to Sicily data instead of writing a
   fine-tuning pipeline from scratch. This is a real multi-day task, not a
   quick one — budget accordingly.

4. **Optionally blend in EFFIS's pan-European archive** for extra training
   volume/diversity — but only *after* the Sicily-only fine-tune works, not
   before. It's skewed toward larger fires (same floor problem documented
   all session) so it won't fix the small-fire gap alone, and would just
   add noise to an unproven pipeline if introduced too early.

5. **Validate the fine-tuned model exactly like everything else this
   session was validated**: Tiberio and Pollina first (the two known 2023
   fires), before trusting it at province scale. This discipline caught
   every false lead this session (GFW's Gangi/San Mauro coincidence, the
   RdNBR failure, the 91%-miss number needing a size breakdown) — don't
   skip it for the new model.

6. **ChaBuD**: deprioritized as a data source (real but frozen since 2023,
   only 356 image pairs, California-specific vegetation, ambiguous
   license). Its baseline model code (a TinyCD architecture) might be worth
   a five-minute look for implementation ideas, nothing more.

## Known gotchas — don't re-discover these

- **EFFIS**: only real vector data comes from `FORMAT=application/vnd.mapbox-vector-tile`
  on the WMS GetMap endpoint. WFS times out (not supported despite existing
  in capabilities). GeoTIFF format errors on this particular layer type.
  `scripts/fetch_effis.py` has the working pattern.
- **Cadastral WFS** (Agenzia delle Entrate): silently returns zero results
  (no error) for bbox queries wider than ~0.015°. Must tile queries into
  small chunks. `scripts/fetch_cadastral_parcels.py` has the working
  tiled-retry pattern.
- **GFW Data API**: geometry-filtered queries are broken on dataset
  versions `v20250206` and later (confirmed against a massive real
  wildfire, not assumed). `v20250127` works but is a frozen snapshot as of
  that date, not a live feed. See `docs/gfw_known_issue.md`.
- **Sicily regional fire registry** (`sifweb.regione.sicilia.it/arcgis/rest/services/Censimento_Incendi`):
  date field is raw epoch-milliseconds, needs `unit="ms"` in
  `pd.to_datetime()` or it silently produces nonsense dates. The newest
  year's layer (whichever is `layer id 0` at the time) may reject
  pagination params outright with an error — retry unpaginated if so.
- **FireHR**: confirmed twice, via two different fix attempts, that it
  needs a full Docker rebuild with a period-correct (~2020) pinned
  dependency lockfile — not a single-package fix. Four distinct
  incompatibilities found across both attempts. Full detail in
  `docs/firehr_known_issue.md`. Don't attempt a third "lighter" fix without
  a genuinely new idea.
- **HLS imagery bands**: `-9999` nodata fill value must be explicitly
  masked (`arr[arr == -9999] = np.nan`) before any NBR/index math, or it
  silently corrupts results with impossible values.
- **dNBR chip-fetch tile edges**: a fire near an MGRS tile boundary can
  fail with "window outside tile bounds" on the lowest-cloud scene while a
  neighbouring tile/scene would work fine. `scripts/dnbr_detect_province.py`
  has the working fallback pattern (try multiple candidate scenes, not just
  the single best one).

## Credentials / environment

- `.env` (gitignored, stays local): `GFW_API_KEY` and `GEE_PROJECT` are
  both set and working. Don't re-request these.
- Three separate venvs, don't mix them up: `.venv` (Python 3.9, original,
  mostly superseded), `.venv311` (Python 3.11, everything modern — EFFIS,
  GFW, cadastral, dNBR, Prithvi/terratorch), `.venv_firehr` (Python 3.11,
  isolated specifically for the failed FireHR attempts, don't reuse for
  anything else).
- GitHub push works fine but has warned about large files (some GeoJSONs
  are tens of MB) — not yet a real problem, but worth watching if the repo
  keeps growing; Git LFS is the eventual answer if it becomes one.
