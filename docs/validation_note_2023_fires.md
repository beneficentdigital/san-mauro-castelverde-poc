# Validation note: EFFIS vs. the two known 2023 fires (internal, not for the Marco deck)

Per brief section 7 — checking the pipeline against Fenice Verde's two documented
2023 fires before anything goes in front of Marco.

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

## What this means for deliverable 3 (the one-pager)

Don't present "EFFIS confirms the known fires" as a clean headline. The honest,
still-strong version: *"EFFIS independently detected a fire on the exact date
and location of the larger of the two known events, at a scale consistent with
Fenice Verde's own figure once clipped to the comune boundary — and, as
expected, did not detect the smaller 2-hectare fire, which is exactly the gap
GFW/FireHR/Prithvi and the comparison against your own catasto are designed to
close."* That's a more credible story in the room than a suspiciously perfect
match would be.
