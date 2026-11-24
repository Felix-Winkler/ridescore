# Prompt log

Template for every important prompt (copy the block):

```markdown
### #NN – <short title>  (date, who)
**Goal:**
**Prompt:**
> ...
**Result:** worked / partly / failed
**What we changed or learned:**
```

### #01 – Project skeleton from the brief  (2026-11-24)
**Goal:** Generate the whole project (models, logic, data layer, UI, tests) from `RideScore_PROJECT.md`.
**Prompt:**
> can you make me a project in FLET according to this Markdown
**Result:** worked (38 unit tests pass; UI built in demo mode)
**What we changed or learned:**
- Claude checked first which Flet map/chart packages exist for our version (flet-map / flet-charts 1.1.2).
- Everything runs without API keys (demo mode); real APIs are implemented but untested with real keys.
- EVIS.AT and the roadwork source are stubs until access/format are clarified (open questions in the brief).
- TODO for us: add real sample responses, verify GeoSphere parameter names, calibrate thresholds.
