# BAIS2 test result (2026-09-17) — tried, doesn't fix the small-fire problem

Per the agreed next-phase to-do list, item 1: test BAIS2 (Filipponi 2018,
"Burned Area Index for Sentinel-2") against the same two known 2023 fires
used for every other method this session (Contrada Tiberio ~2ha, Foce del
fiume Pollina ~12ha comune-clipped). Verdict: **doesn't outperform dNBR,
don't pursue further without a new idea.**

## Formula and threshold used

```
BAIS2 = (1 - sqrt((B06*B07*B8A)/B04)) * ((B12-B8A)/sqrt(B12+B8A) + 1)
```

Implemented in `scripts/dnbr_detect.py` (`compute_bais2`, `run_bais2`).
Unlike NBR/dNBR this formula is **not scale-invariant** — it mixes a 3-band
product against a 1-band term — so raw HLS int16 DNs had to be converted to
true 0-1 reflectance first (`HLS_SCALE_FACTOR = 0.0001`, confirmed against
the HLS v2.0 product user guide). Missing this would silently produce wrong
numbers, not just rescaled ones — worth flagging for anyone touching this
code later.

Threshold: **0.865**, Filipponi's own calibration for a July 2017 Sicily
wildfire — the closest published value to this exact use case (same region,
same season), used ahead of the more generic >0.90 seen elsewhere in the
literature. BAIS2 is a single post-fire-image index by design (no pre-fire
baseline needed), which is exactly why it was worth testing: it sidesteps
dNBR's seasonal-vegetation-drying false positives structurally, since there's
no pre-fire image to be thrown off by.

## Result

| Fire | Known area | dNBR (existing) | BAIS2 (new) |
|---|---|---|---|
| Contrada Tiberio | ~2 ha | 1.35 ha @ 10m | **7,385m away, 315 ha** — total miss |
| Foce del fiume Pollina | ~12 ha (comune-clipped) | 4.41 ha @ 230m | 1.89 ha @ 259m — right place, undersized |

dNBR — the incumbent method, already in the repo before this test — actually
performs well on these two specific fires (Tiberio in particular: 1.35ha at
10m is excellent). BAIS2 is worse on both: a complete miss on Tiberio, and a
more severe undersize than dNBR on Pollina.

## Why: checked the actual pixel values, not just the threshold outcome

At the known fire's exact center pixel:
- **Tiberio**: BAIS2 ≈ 0.42–0.57 across the 5x5 core window — nowhere close
  to the 0.865 threshold. The real burn scar simply doesn't cross that bar
  at all; the "nearest detected patch" 7.4km away is unrelated background
  (bare karst/urban), not a positional error in the algorithm.
- **Pollina**: BAIS2 ≈ 0.72–0.78 at center — closer, but still under
  threshold at the core; only the most severe edge pixels cross 0.865,
  which is why the detected patch is real (right place) but a fraction of
  the true extent.
- Meanwhile **2.9–3.5% of each entire chip** exceeds 0.865 anyway (elevated
  baseline reflectance from bare rock/urban surfaces common in this
  terrain), which is what produces Tiberio's false "nearest patch."

This is a real, non-fitted, non-buggy negative result — not a coding error
and not a repeat of the RdNBR failure mode (RdNBR was numerically unstable;
BAIS2 computed cleanly, it just doesn't cross threshold on real small fires
here). Filipponi's own threshold, calibrated on one specific 2017 Sicily
fire, doesn't transfer even to a different fire in the same region — the
same fitted-threshold generalization problem that sank the mixed-vegetation
fix attempts. Lowering the threshold to catch Tiberio would sweep in even
more of the 3%+ background false-positive rate chip-wide; this isn't a
tuning knob with a good setting, it's evidence the index's dynamic range
for small/patchy Mediterranean burns is genuinely narrow.

## Decision

Don't pursue BAIS2 further (no per-scene threshold retuning, no combining
with dNBR) without a genuinely new idea — same standard applied to RdNBR
and the median-baseline attempt. Move to next-phase item 2 (Sicily registry
→ Prithvi fine-tuning training data), which is a training-based fix for
this exact problem rather than another hand-tuned spectral index.
