# All results — consolidated summary

One place for everything built this session. Deadline context: San Mauro
Castelverde materials (below) are meeting-ready for Thursday 2026-09-17.
Everything else is real, working, committed follow-on work done at the
user's request, at varying stages of polish - flagged honestly throughout.

---

## 1. San Mauro Castelverde (the actual meeting pilot)

**Meeting deliverables — complete:**
- Map: `output/san_mauro_wildfire_map.html`
- Per-fire table: `output/fire_summary_table.csv`
- One-pager for Marco (published artifact + `docs/one_pager_for_marco.md`)
- Validation note: `docs/validation_note_2023_fires.md`

**Headline numbers:**
- 14 EFFIS-detected fires, 2018-2025
- 13 official regional registry records for the comune (a richer, independent
  list - see below)
- 2 known 2023 fires (Fenice Verde's blog) both validated

**Validation against the two known 2023 fires — now doubly confirmed:**

| Fire | Fenice Verde blog | EFFIS | Prithvi | Official registry |
|---|---|---|---|---|
| Contrada Tiberio, 15 Sep 2023 | ~2ha | not detected | 36ha, 10m away | **2.26ha** (exact) |
| Foce del fiume Pollina, 21 Sep 2023 | ~12ha | 145ha complex, wrong comune | 101.6ha, 440m away | **11.84ha** as "Contrada Altopiano" (exact, correct comune) |

The official regional registry (found during the Palermo province work, see
below) gives a dramatically cleaner match than anything used in the original
validation pass - worth folding into the meeting materials if there's time.

**Other San Mauro Castelverde findings:**
- The August 2021 "mega-fire" EFFIS mapped as one 9,778ha polygon is actually
  several distinct official fires (Contrada Ciambra x2, Contrada Canalicchio,
  Casa Ciambra) days apart - a real methodological finding about how EFFIS
  aggregates nearby ignitions.
- Two new fires at Contrada Tiberio in September 2025 (recurring ignition
  location) that EFFIS never detected.
- 2 real 2024 fires (3 Jan, 7 Feb) confirmed absent from Fenice Verde's own
  published catasto - the actual "here's what automation catches" finding.
- GFW/VIIRS cross-check: doesn't tightly corroborate any San Mauro fire
  (expected - different measurement method, not a flaw).
- FireHR: blocked twice, confirmed needs Docker (see `docs/firehr_known_issue.md`).

---

## 2. Palermo province (82 comuni) - follow-on extension

**Not a Marco deliverable - internal/next-phase work**, started after the
user asked to extend beyond the single pilot comune.

- **588 unique EFFIS fires**, 2018-2025, 85,818ha total (`data/processed/effis_palermo_province_2018_2025.geojson`)
- **7,090 GFW/VIIRS points** (`data/processed/gfw_viirs_alerts_palermo_province.geojson`)
- **1,663 official registry records**, 75,527ha (`data/processed/regione_censimento_incendi_palermo_2018_2025.geojson`)
- **209,188 candidate parcel matches** (188,636 unique parcels) across all
  588 fires - 536 smaller fires handled with full precision, 52 large
  complexes (up to 9,778ha) matched separately since enumerating thousands
  of parcels per mega-fire isn't reviewable one-by-one
- Map + per-comune summary table built (`output/palermo_province_wildfire_map.html`,
  `output/palermo_province_summary_by_comune.csv`)
- **Monreale** stands out as the strongest case for this tool's value: 77
  fires, 20,700 combined candidate parcels

**EFFIS vs. official registry cross-check** (the real gap-analysis finding):

| | Count | % |
|---|---|---|
| EFFIS fires matching an official record | 139 / 588 | 24% |
| Official fires with no EFFIS match | 1,517 / 1,663 | 91% |

That 91% needs the breakdown, not the headline number alone:

| Size of missed fire | Count | Share of misses |
|---|---|---|
| ≤10ha | 991 | 65% |
| 10-30ha | 255 | 17% |
| 30-100ha | 157 | 10% |
| 100-300ha | 83 | 5% |
| >300ha | 26 | 2% |

**82% of misses are ≤30ha** - below EFFIS's own documented floor, fully
expected. **The other 18% (~266 fires) are genuinely within EFFIS's claimed
range and still missed** - the honest, interesting gap, and the real
argument for cross-referencing rather than trusting one satellite product.

**dNBR (small-fire precision layer):**
- Built from scratch this session - plain NBR/SWIR band math, not a trained
  model, validated first on the San Mauro pilot (1.35ha detected 10m from
  the known Tiberio site - excellent)
- Automated and run province-wide on 276 fires ≤30ha; after a tile-boundary
  fix, 219/276 (79%) produced a result
- QA flag applied (statistical proxy, not full visual review): 134 plausible,
  85 flagged as likely noise
- Independently tested at 8 locations EFFIS completely missed: found real
  positional signal at 5/8 (0m from the known site in every hit), but area
  estimates unreliable in automated mode (4 of 5 overshot 16-100x)
- Seasonal-noise problem (Sicilian late-summer vegetation drying confounding
  the burn signal) tried twice to fix (RdNBR, multi-image median baseline) -
  both failed honestly, documented as open

---

## 3. Carlentini (Fenice Verde's other pilot comune)

Completes the actual two-comune pitch, not just San Mauro Castelverde.

- 59 EFFIS fires, 2018-2025 (`data/processed/effis_carlentini_2018_2025.geojson`)
- 18 official registry records (`data/processed/carlentini_effis_vs_official.csv`)
- 2/18 strict cross-check match, same pattern as everywhere else (several
  near-misses with close area correspondence just outside the matching radius)
- Boundary, EFFIS, and cross-check done; cadastral parcel matching and a
  one-pager not yet built for this comune

---

## 4. Sicily-wide official fire registry

The single strongest ground-truth source found all session, and it covers
the whole region, not just Palermo province.

- **7,273 official fire records, 232,301ha, 2018-2025, across 352 of 391
  Sicilian comuni** (`data/processed/regione_censimento_incendi_sicilia_2018_2025.geojson`)
- Source: Sicilian Regional Forestry Service's own "Censimento Incendi"
  ArcGIS service (`sifweb.regione.sicilia.it`) - the same source Fenice
  Verde's own site draws its cached SIF layer from, fetched live here instead
- Found and fixed a real server quirk along the way (the 2025 layer rejects
  pagination params outright) - verified the fix against an independent
  estimate before trusting it

---

## 5. Next-phase roadmap

Full detail in `docs/next_phase_roadmap.md`. Summary:

| Item | Status |
|---|---|
| Tile-boundary bug fix (dNBR) | ✅ Done - 66%→79% success rate |
| QA flagging on dNBR | ✅ Done (statistical proxy) |
| Carlentini extension | ✅ Done |
| Sicily-wide registry | ✅ Done |
| dNBR seasonal-noise fix | ❌ Tried twice (RdNBR, median baseline), both failed honestly |
| FireHR | ❌ Tried twice, confirmed needs a full Docker rebuild |
| Ongoing/scheduled pipeline | Not started - written up as a ~1-2 day scope |
| Trained ignition-cause classifier | Not started - now more feasible given the Sicily-wide registry, but still needs a real cause-label source first |

---

## Source map

| Question | File |
|---|---|
| Is San Mauro Castelverde ready for Thursday? | Yes - see section 1, `STATUS.md` |
| What's the strongest validation evidence? | Official registry match on both known 2023 fires (section 1) |
| What would extending to the whole province look like? | Section 2 - already substantially done |
| What's genuinely unresolved? | Section 5 / `docs/next_phase_roadmap.md` |
| Full script-by-script detail | `git log` - every step this session is a separate, documented commit |
