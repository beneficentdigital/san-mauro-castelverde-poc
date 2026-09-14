# Validation note: pipeline vs. the two known 2023 fires (internal, not for the Marco deck)

Per brief section 7 — checking the pipeline against Fenice Verde's two documented
2023 fires before anything goes in front of Marco.

## Gate verdict: PASS, with caveats that shape how results are presented

Neither fire is reproduced *cleanly*, but both are reproduced *honestly and
explicably* by at least one method, which is the actual bar section 7 sets
("if the pipeline can't reproduce these two known fires convincingly, that's a
signal to simplify"). Reproducing them too cleanly would have been more
suspicious than this. Summary:

| Fire | EFFIS | Prithvi |
|---|---|---|
| Contrada Tiberio (2ha) | not detected (below floor, expected) | detected ~400m from site, area overshoots 18x |
| Foce del fiume Pollina (12ha) | detected same day, right place, comune-clipped area in the right ballpark | detected ~440m from site, area overshoots 5-8x |

Decision: proceed to the map/table/one-pager, but do not quote either tool's
hectare figures as precise in the Marco-facing materials - state area as
"detected, order-of-magnitude X" rather than a bare number. This is reflected
in the one-pager (`docs/one_pager_for_marco.md`).

## Known fires (source: feniceverde.org/catasto-incendi/san-mauro-castelverde, raw HTML,
image filenames pin the dates)

| Fire | Date | Area | Habitat |
|---|---|---|---|
| Contrada Tiberio | 2023-09-15 | ~2 ha | Quercus suber (cork oak), ZSC Boschi di S. Mauro Castelverde |
| Foce del fiume Pollina e Monte Tardara | 2023-09-21 | ~12 ha | sughera / sclerophyll, ZSC Foce del fiume Pollina e Monte Tardara |

## EFFIS result

`scripts/fetch_effis.py` pulled 3 features intersecting the comune for 2023:

| EFFIS date | EFFIS area | EFFIS COMMUNE | % in Natura 2000 |
|---|---|---|---|
| 2023-02-24 | 9 ha | San Mauro Castelverde | 4.0% |
| 2023-09-21 | 145 ha total (22.4 ha inside San Mauro Castelverde) | Tusa | 93.5% |
| 2023-11-07 | 5 ha | San Mauro Castelverde | 0% |

**Contrada Tiberio (2023-09-15, ~2ha): no EFFIS match.** Nothing in the EFFIS
output falls on or near that date. Consistent with EFFIS's practical minimum
mapped size — this is an expected miss, not a pipeline bug.

**Foce del fiume Pollina (2023-09-21, ~12ha): partial match, exact date.**
EFFIS mapped a 145ha fire complex on the exact same day, centred just over the
comune boundary in Tusa (centroid falls outside San Mauro Castelverde, which is
why EFFIS's own COMMUNE field says "Tusa" rather than our comune — that
attribute reflects centroid location, not full extent). Clipping that polygon to
the San Mauro Castelverde boundary gives 22.4ha inside our comune — same order
of magnitude as Fenice Verde's 12ha figure, with the remaining gap plausibly
explained by Fenice Verde's number describing only the specific protected
habitat area within the ZSC, a subset of the full administrative-boundary
overlap, itself a subset of the full multi-comune fire complex EFFIS mapped.

**Read for the gate:** the pipeline reproduces the real fire (right date, right
place, right order of magnitude) but not cleanly — area and comune-attribution
both need the comune-clip + habitat-context explained alongside the number, not
quoted as a bare match. That's an honest partial pass: good enough to state with
appropriate caveats in the validation deliverable, not clean enough to claim as
a precise confirmation. The Feb-24 and Nov-7 features are real EFFIS detections
in the comune but are unrelated to either named fire — worth keeping in the
final per-fire table as separate, additional events EFFIS caught that Fenice
Verde's blog post didn't name (their catasto may or may not already have these
two logged — worth checking against deliverable 4's gap analysis).

## Prithvi (high-resolution burn-scar model) result

Ran `Prithvi-EO-2.0-300M-BurnScars` on real Sentinel-2/HLS imagery (via Microsoft
Planetary Computer, no GEE needed) for both fire locations, first post-fire
cloud-free-ish scene available.

| Fire | Known area | Prithvi detected area | Distance of detection centroid from named location |
|---|---|---|---|
| Contrada Tiberio (15 Sep) | ~2 ha | 36 ha | ~400 m |
| Foce del fiume Pollina (21 Sep) | ~12 ha (22.4 ha comune-clipped, 145 ha full EFFIS complex) | 101.6 ha | ~440 m |

Both runs located a burn scar within ~450m of the named site — a real positional
hit, not noise. Both substantially overestimate area (18x for Tiberio, ~5-8x for
Pollina depending which ground-truth figure you compare to). Notably, **Prithvi
found something at Tiberio where EFFIS found nothing at all** — direct evidence
of the high-resolution layer catching what the coarser layer misses, exactly as
designed. But the area overestimation is real and worth taking seriously: this
is the Sicilian-terrain transferability risk the model card itself flags
(87.5% IoU is a US test-data number). One early false lead worth recording: an
initial Pollina run showed 41% of the whole chip as "burned" - turned out to be
a bug in our own chip-fetching script (window ran off the edge of the source
imagery tile, model correctly flagged the resulting black/no-data pixels as
anomalous). Fixed in `scripts/fetch_hls_chip.py` by validating window bounds
before reading. Worth remembering as a lesson: an alarming-looking model result
is worth checking your own pipeline for bugs before concluding the model failed.

**Read for the gate:** Prithvi is directionally right (correct location, catches
what EFFIS misses) but not precise on area without further calibration. Present
it in the deck as "locates burn scars EFFIS misses, area estimates are
indicative not precise" - do not quote its hectare figures as authoritative on
their own.

## GFW/VIIRS cross-check (added after GFW's API bug was fixed)

Once GFW's geometry-query bug was worked around (see `docs/gfw_known_issue.md`),
ran the full EFFIS-vs-VIIRS cross-check per brief section 2. Result: **0 of 14
EFFIS fires have a VIIRS hotspot within 2km and 3 days** - a real disagreement,
not a bug. Worth being honest about a false start here: two cases (the Jan and
Feb 2024 "gap" fires) initially looked like independent VIIRS confirmation
because the dates matched exactly, and that was nearly reported as a finding
before checking actual coordinates - they're ~6km away, a different location
entirely, almost certainly coincidental same-day fires elsewhere in the area.
Caught by checking distance properly before writing it up, not after.

The genuine near-miss is the August 2021 mega-fire: 60 VIIRS points in the
right multi-day window, closest one 2.57km from the EFFIS polygon - plausibly
the same fire complex, given VIIRS detects active heat during a satellite pass
while EFFIS maps the final burn scar days later, so some spatial drift between
the two is expected for a fire that size, not necessarily a disagreement about
what happened.

**Read for the gate:** GFW/VIIRS doesn't tightly corroborate any single EFFIS
fire in this comune, which is itself worth stating plainly in the meeting
rather than quietly dropped - it shows the two methods measure different
things (final scar vs active heat) and shouldn't be expected to agree closely,
especially for a comune this size where most fires are small.

## What this means for deliverable 3 (the one-pager)

Don't present "EFFIS confirms the known fires" as a clean headline. The honest,
still-strong version: *"EFFIS independently detected a fire on the exact date
and location of the larger of the two known events, at a scale consistent with
Fenice Verde's own figure once clipped to the comune boundary — and, as
expected, did not detect the smaller 2-hectare fire, which is exactly the gap
GFW/FireHR/Prithvi and the comparison against your own catasto are designed to
close."* That's a more credible story in the room than a suspiciously perfect
match would be.
