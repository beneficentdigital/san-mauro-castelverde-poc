# FireHR — dependency deadlock, not resolved (2026-09-14)

FireHR (`pip install FireHR`) pulls in `banet`, which pulls in `nbdev<2` and
`fastai` pinned to `>=2.1.4,<2.2.7` (2020-era). Tracing the actual failure
chain rather than just retrying:

1. `fastai==2.1.10` imports `torchvision.models.utils.load_state_dict_from_url`,
   removed from torchvision in ~0.13 (2022). **Worked around**: monkeypatched a
   shim module before import (the function just moved to `torch.hub`, nothing
   structural changed) - this part is fixed.
2. Past that, `fastai`'s own internals (`@typedispatch` in `fastai/data/core.py`)
   need an old `fastcore` (~1.3.x) - `fastai` 2.1.x predates modern fastcore.
3. Pinning `fastcore` down to 1.3.x breaks straight away: `nbdev` (a **hard
   FireHR/banet dependency**, not optional) requires `ghapi`, and `ghapi`'s
   current PyPI releases require `fastcore>=2.2.7`. `nbdev` doesn't pin ghapi's
   version, so pip always resolves the newest one, which is incompatible with
   the old fastcore fastai needs.

Net effect: there is no fastcore version on PyPI today that satisfies both
`fastai==2.1.x`'s internals and `nbdev`'s unpinned `ghapi` dependency
simultaneously. This is a real deadlock in FireHR's own dependency tree
against the current package index, not a transient install glitch - confirmed
by tracing it to the specific conflicting requirement pins rather than assumed.

**Isolation already done correctly**: FireHR was installed in its own venv
(`.venv_firehr`, Python 3.11) precisely so a fix attempt here couldn't risk
breaking the already-working Prithvi/terratorch environment (`.venv311`) - that
separation held throughout this investigation and nothing outside
`.venv_firehr` was touched.

## Ways past this, not attempted (time-boxed rather than open-ended)

- Build in a container pinned to circa-2021 package versions (a full
  historical lockfile, not just FireHR's direct deps) - the actual fix, but a
  half-day task, not the "hours-level adapter script" the brief anticipated.
- Fork/patch `banet`'s `setup.py` to drop the `nbdev` dependency at import
  time (it's likely only used for docs/dev tooling, not runtime prediction) -
  plausible but unverified without reading banet's source in more depth.
- Try `micromamba`/`conda` with a pinned old `fastai` conda-forge build, which
  may carry compatible transitive pins that PyPI's flat resolver can't express.

## Second attempt (2026-09-16): lighter fix tried, also failed

Tried pinning `nbdev==1.0.18`, which predates `ghapi` being a dependency at
all (uses `fastscript` instead) - a reasonable, lower-effort alternative to
a full Docker rebuild. Two more, unrelated incompatibilities surfaced
immediately: `fastscript>=1.0.0` itself is no longer available on PyPI (only
a stub `0.0.0.1` remains), and separately `fastprogress` (a simple, supposedly
lightweight progress-bar package) now pulls in a whole `fasthtml` web
framework in its current release, which needs a `fastcore.xml` module that
doesn't exist in older fastcore versions.

That's four distinct, unrelated incompatibilities found across two sessions
(torchvision's moved API, fastcore's `typedispatch`, `nbdev`'s `ghapi`
dependency, and now `fastprogress`'s `fasthtml` dependency) - confirms this
isn't a single bad pin fixable by one substitution. The entire fast.ai
ecosystem's current dependency graph has moved on from 2020-era assumptions
in ways that cascade regardless of which single package gets pinned.

## Recommendation

Per the brief's own framing, FireHR was always the "genuinely optional, most
likely to slip" layer, with Prithvi as the fallback high-resolution detector.
Prithvi is fully working and validated (see `docs/validation_note_2023_fires.md`).
Given a real, traced dependency deadlock rather than a quick fix, this is
where FireHR should be left for Thursday - named honestly as a known
next-phase item, not silently dropped.
