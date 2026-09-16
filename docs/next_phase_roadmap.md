# Next-phase roadmap

Status snapshot as of 2026-09-16, the day before the Fenice Verde meeting.
Everything here is genuinely next-phase - none of it blocks presenting the
San Mauro Castelverde materials, which are complete (see `STATUS.md`).

## 1. An ongoing pipeline, not a one-off batch

Everything built so far answers "what happened 2018-2025." The actual
product Fenice Verde would want is something that keeps answering that
question as new fires happen - a scheduled job (weekly or monthly) that:

- Re-queries EFFIS, the official regional registry, and GFW for new records
  since the last run
- Re-runs the cadastral parcel match and ignition-context flags on anything
  new
- Flags new gaps against Fenice Verde's own catasto the moment they appear,
  rather than in a retrospective batch

Effort: a day or two - the individual pieces all exist and work; this is
scheduling + incremental-fetch logic + a lightweight notification/summary
step, not new detection methods.

## 2. A trained ignition-cause classifier

Explicitly out of scope from the original brief - San Mauro Castelverde
alone never had enough labelled fires to train anything trustworthy. That
constraint has changed: the official regional registry now gives **7,273
labelled fire records across all of Sicily**, with real attributes (date,
location, area, forested/non-forested split) - genuinely enough scale to
consider training on, where before there wasn't.

Still a real project, not a next-week one: would need actual cause labels
(the registry gives *where and when*, not *why* - cause data, if it exists
at all, would have to come from a different source, likely the comuni's own
Albo Pretorio publications, which are unstructured PDFs, one per comune, no
shared format). Realistic scope: a feasibility study first (how many fires
in the registry have any cause information at all, from any source) before
committing to building a classifier.

## 3. Loose ends worth closing before the next comune

- **FireHR** - confirmed twice now (two separate fix attempts, four distinct
  dependency incompatibilities found) that this needs a Docker container
  with every package pinned to a period-correct 2020-era lockfile, not a
  single-package fix. See `docs/firehr_known_issue.md`.
- **dNBR's seasonal-noise problem** - two real techniques tried (RdNBR,
  multi-image median baseline), neither fixed it. Needs either a
  fundamentally different approach (per-landcover-type calibration using
  CORINE, an ensemble vote with EFFIS/official-registry corroboration
  required before trusting a dNBR area figure) or accepting it as a
  location-confirmation tool only, not an area-measurement one.
- **Remaining dNBR tile-boundary failures** - down from 30% to 16% after the
  fallback fix; the rest are likely single-tile-coverage edge cases.
- **Road-distance ignition flag** - never shipped; OpenStreetMap's Overpass
  API was unreachable from this environment all session. Worth a retry from
  a different network before assuming it's structurally blocked.
- **Visual QA on dNBR** - the 134/85 plausible/flagged split is a statistical
  proxy, not actual human eyes on imagery. Worth doing properly before any
  dNBR number is presented as fact rather than "worth checking."

## What's already solid and doesn't need revisiting

EFFIS, the official regional registry (now region-wide), cadastral parcel
matching, Prithvi, ignition-context shape/day-night flags, and the San Mauro
Castelverde validation gate are all working, tested, and committed. The
region-wide registry in particular turned out to be the strongest ground
truth source found all session - worth leading with in any pitch about
what's next.
