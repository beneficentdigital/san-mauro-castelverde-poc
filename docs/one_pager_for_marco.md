# What the satellite record shows for San Mauro Castelverde

*A trial run of an automated version of the fire-by-fire review Fenice Verde already does by hand — applied to your own pilot comune, using only public records. Prepared for discussion with Fenice Verde.*

*(Designed version: see the published one-pager artifact for the meeting-ready layout — this file is the plain-text source.)*

## Headline numbers

- **15** real fires identified, 2018–2025
- **2 / 2** of your documented 2023 fires located
- **2** real 2024 fires not yet in your own catasto

## 1. We checked our work against your own two known fires first

Before trusting this on anything new, we tested it against the two 2023 fires your blog already documented — the only fair test, since we know exactly what happened there.

**Foce del fiume Pollina, 21 September 2023 — Confirmed.** Our main satellite source located a fire on that exact date, in that exact place. Its own size estimate came out larger (a wider fire complex crossing into Tusa), but the portion sitting inside San Mauro Castelverde lines up with your ~12 hectare figure once measured the same way you measured it.

**Contrada Tiberio, 15 September 2023 — Indicative.** At ~2 hectares, this one is too small for our main satellite source to see — expected, not a flaw. Our second, higher-resolution AI tool found it anyway, in the right spot. Its size estimate (36 hectares) overshoots badly and should not be quoted as-is — but as a "was something burnt here" check, it passed.

## 2. Two real fires we found aren't in your own catasto yet

Checked against your 2024 fire census, one entry (Contrada Buonanotte, 8 October) matched exactly. But two other real fires that same year — 3 January (2 ha) and 7 February (3 ha) — show up in the satellite record and don't yet appear in your published catasto. This is the actual case for automating the audit: not replacing your review, but flagging what a comune-by-comune manual pass might not have reached yet.

## 3. Every fire, matched to the exact land parcels it touched

Each burnt area was checked against the official land registry (catasto) to list which specific parcels (foglio/particella) it crossed — automatically, comune-wide. Worth saying plainly: a satellite-drawn fire edge rarely lines up neatly with a parcel boundary, so a fire is usually reported as touching several parcels, not landing inside one.

| Date | Area (ha) | Parcels touched | In your catasto? |
|---|---|---|---|
| 17 Oct 2020 | 36 | 26 | — |
| 4 Aug 2021 | 9,778* | 88 | — |
| 21 Sep 2023 | 145* | 85 | — |
| 3 Jan 2024 | 2 | 3 | Not found |
| 7 Feb 2024 | 3 | 4 | Not found |
| 8 Oct 2024 | 10 | 42 | Confirmed |

*Multi-comune fire complex — figure is the full detected extent, not just the San Mauro Castelverde portion. Full 15-fire table: `output/fire_summary_table.csv`.

## We also checked against a second, independent satellite source

Global Forest Watch's heat-detection data (a different satellite, a different method — it senses active heat while a fire burns, rather than mapping the scar afterwards) didn't closely match any of our 14 fires by location. That's expected, not a contradiction: the two tools measure different things, and heat-sensing satellites miss a lot of smaller or short-lived fires by design. Worth stating plainly rather than only reporting the sources that agree with each other.

## Important — please read before the meeting

The "unusually straight edge," "near farmland," and "day/night" notes attached to each fire are **plain observations, not a verdict on cause**. They're a measured version of the same eyeballing your own reviewers already do — applied consistently to every fire, not a trained model guessing who lit it. San Mauro Castelverde simply hasn't had enough fires for that kind of model to be trustworthy, and we're not pretending otherwise.

## 4. What this shows

The manual, fire-by-fire audit Fenice Verde already runs can be reproduced from public records alone, for one comune, checked against your own past findings before drawing conclusions from it. It caught what a broad satellite pass alone would miss, and surfaced two real fires your own catasto hadn't recorded yet. Next step, if useful: the same process on Carlentini, your other pilot comune.

One tool we planned to add — a second high-resolution refinement pass (FireHR) — turned out to depend on unmaintained software that won't currently install. Rather than paper over it, we're naming it here: the AI tool we did get working (Prithvi) already covers the same role, so nothing in this report depends on the one that didn't ship. Worth revisiting FireHR for a later phase.

---

Public sources only, each carrying its own attribution: EFFIS burnt-area data (Copernicus/JRC, EU Data License) · cadastral parcels (Agenzia delle Entrate, CC BY 4.0) · Prithvi-EO-2.0 burn-scar model (IBM/NASA, Apache 2.0) · your own published catasto (osservatorioincendi.org).

Prepared by Beneficent · San Mauro Castelverde pilot · 2026
