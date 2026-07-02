# Commit 8 — R1 RE-VALIDATION PROTOCOL (§B v1.24 — caching; growth BAND + bg N=4-average)

> The R1 re-validation is the LAST Phase-3 hardening step: re-derive the tiering by NAMED company
> (`R1_TARGET = P0=4 / P1=6 / P2=6 / P3=38`, the live-54 — an OUTPUT re-validated by name, never forced) by
> taking each company's four §B reads ONCE, caching them, and scoring off the cache. It is a LIVE Colab job.
> Code branch `phase3-commit8-r1` (v1.24 = commit `730df7e`), against SOT **v1.24** (docs-scoring-sot
> `c84a91c`). **R1 is an HONEST check — a tally that only hits 4/6/6/38 via a quiet threshold nudge is a
> FAILED R1. Drift is diagnosed real-bug vs documented-exception BEFORE any re-fit; a re-fit is doc-first,
> never a silent nudge.**
>
> **v2 (2026-06-30):** the first draft of this cell was WRONG and was caught by the gate-point check —
> it fed raw checkpoint rows to the scorer (which expects flattened columns) and used a mis-assembled
> bg_fit evidence blob. Root cause: the `_FINAL` checkpoint is RAW research output; the scoring inputs live
> inside `fit_brief_json`. The corrected flow below runs entirely through committed, tested package code.

## The verified data contract (checked against the real `_FINAL` CSV)

The checkpoint is **11 raw columns**: `company`, `date_researched`, the six findings (`funding_finding`,
`payer_institutional_finding`, `outcomes_finding`, `commercial_scale_finding`, `growth_finding`,
`org_events_finding`), `paying_finding`, `operating_characteristics_finding`, and `fit_brief_json`. **None
of the flattened scoring columns exist top-level** — they live inside `fit_brief_json`
(`commercial_evidence`, `maturity_evidence`, `capability_evidence`, `reset_evidence`). Note: `commercial_evidence`
carries the OLD `user_scale_signal` key (pre-v1.3 rename) — the adapter maps it.

`structured_evidence.flatten_checkpoint_row(row)` unpacks all of this via the committed `flatten_*` bridge;
verified on all 54 real rows (54/54 flatten, capability_a2 present 54/54, no crashes). The three
LLM-variable reads are NOT in the checkpoint and run live: the §B2 classifier (who_uses/who_pays), the §B6
growth extractor, the §B5 background_fit. Their evidence assemblies are TESTED package functions
(`classifier_evidence`, `canonical_growth_evidence`, `background_fit_evidence`) — the literal blobs the
signed cells 180/177/178 fed.

## What runs (v1.24 — CACHING; growth is a BAND, bg is an N=4 average)

- **Once per company (cached, never re-rolled):** the four §B scoring reads — §B4 v1.16 hardened reset
  re-emit, §B2 classifier, §B6 **growth BAND** (v1.24 — the LLM CLASSIFIES growth into high/solid/slow/unknown
  against the stage's Scale-B cutpoints; it no longer reports figures or derives a rate), §B5 background_fit.
  Floored companies skip bg/growth (no spend).
- **§B5 bg is the MEAN of N=4 reads (v1.24):** background_fit is the one genuinely noisy read (grow wobbled
  4↔8), so it is read **4×** at population and the ROUNDED-HALF-UP mean is cached (mean 4.5 → 5 → passes
  `bg > 4`). This is noise reduction at population, NOT the retired N=5 re-score loop — scoring still reads the
  ONE cached average, so re-scores are identical by construction.
- **Scoring reads OFF the cache** — no re-score passes, no temp-0 (rejected on `gpt-5.4-mini`). A re-score
  reads the same frozen values → identical tiers **by construction**. `run_r1(..., cache=rep["cache"])`
  re-scores without re-calling; `refresh=["equip health"]` re-takes only that company's reads (its N=4 bg +
  band, logged).
- **Cost: ~290 model calls, ONE time** (≈54 reset + 54 classifier + ~37 growth + ~37×4 bg). Re-scores are free.
- **⚠️ v1.24 — a cache from ANY prior run is STALE.** The growth + bg prompts changed, so a pre-v1.24 cache
  holds the OLD reads. Run **fresh** (do NOT pass an old `cache=`); the reproducibility proof (Cell 3b) reuses
  only THIS run's own cache.

**Option-B hardened reset (built into the reads).** The checkpoint's `reset_evidence` came from the OLD
liberal emitter (18 fire naively). The cached reset read re-runs the **committed hardened v1.16 emitter** over
`org_events_finding` and patches `fit_brief_json.reset_evidence`, so `derive_reset_signal` reads clean
type+opening (NO shim). This un-floors `grow` (first-CFO) and rejects the over-fires — the §B4
`DOCUMENTED_RESET_OVERRIDES` (hinge/noom) stay as belt-and-suspenders. **The frozen read must be CORRECT
(caching freezes it):** the run confirms `noom`/`hinge`/`equip`/`season` read correctly (or flagged).

## Documented anchors to verify BY NAME (the target is an OUTPUT, re-validated, NOT forced)

The `R1_TARGET` 4/6/6/38 is the spike's frozen-score ESTIMATE. v1.24 re-scores growth as a BAND and bg as an
N=4 average, so the distribution is the hardened system's OWN output — companies may move vs the estimate.
That is EXPECTED: verify each anchor lands for the RIGHT reason by name; a shift is diagnosed (real bug vs a
better read), never nudged back to the number.

- `function health` → **P1** (human override; pure model call P3).
- `angle` / `oula` → **P3** (floor result, bg_fit=4).
- `signos` / `bicycle` → stage **series-b** (v1.14 human-locked override, applied in `score_company`);
  `9amhealth` deterministic.
- `grow therapy` → un-floored by the hardened reset (first-CFO fires) — a real P0 candidate; if it floors on
  bg it MUST surface in `floored_on_bg` (v1.24 widened flag), not hide in the P3 pile.
- **Growth-BAND spot-checks (v1.24 — the new read):** `equip` → NOT a fabricated cross-source high (no derive
  exists now → banded on its real single-source signal); `pomelo` / `outcomes4me` → banded on revenue only,
  the covered-lives / patient counts FENCED (a count-only company → `unknown`=4, never a leaked high);
  `hinge` 51%/public → `solid`; `function` 450%/series-b → `high`.
- **bg N=4 spot-check:** no eligible company should floor on a single-roll fluke — the cached bg is an
  average; a bg-floored real prospect appears in `floored_on_bg` for a possible `--refresh`.

## The fresh notebook (thin — all logic is in the tested package)

The old notebook's middle (Old Flow → To Delete) is outdated and NOT used. Start a fresh notebook with four
cells. Everything scoring-side is committed package code; the notebook only sets up the client and calls one
function.

**Cell 1 — install the package from the branch + load the checkpoint:**
> ⚠️ **RE-RUN GOTCHA (cost us a whole R1 run — 2026-07-01):** the branch ref (`@phase3-commit8-r1`) is unchanged
> across versions, so pip sees the package "already satisfied" and KEEPS the old wheel that is already on the
> Colab VM disk. **`Runtime → Restart runtime` does NOT fix this** — it restarts the kernel but leaves the
> installed package on disk, so the plain install still skips the upgrade and you silently run the OLD code.
> Two reliable fixes:
> - **BEST — `Runtime → Disconnect and delete runtime`** (a FRESH VM: nothing installed, no wheel cache), then
>   run this cell as-is. A fresh VM always fetches the branch HEAD.
> - **OR — force it in place:** run the `--force-reinstall --no-deps --no-cache-dir` line below, THEN
>   `Runtime → Restart runtime` (to drop the already-imported OLD module from memory), then continue.
> **Then ALWAYS run the Cell 1b version guard before trusting any output.**
```python
!pip -q install --force-reinstall --no-deps --no-cache-dir "git+https://github.com/cleverturnip/health-tech-research-agent.git@phase3-commit8-r1"
import hashlib, pandas as pd
CKPT = "/content/drive/MyDrive/.../v42_full_regen_clean_slate_20260622_full56_checkpoint_FINAL.csv"  # your path
print("sha256:", hashlib.sha256(open(CKPT, "rb").read()).hexdigest())   # (optional) record the fingerprint
df = pd.read_csv(CKPT).fillna("")
print(len(df), "rows;", len(df.columns), "cols")
```

**Cell 1b — VERSION GUARD (MANDATORY — run before Cell 3; a wrong version silently re-runs the old code):**
```python
from health_tech_research_agent import structured_evidence as se
assert hasattr(se, "GROWTH_BAND_SCORE"), "STILL OLD CODE — growth band scorer missing; reinstall (delete runtime)"
assert hasattr(se, "floored_on_bg"), "STILL OLD CODE — floored_on_bg missing; reinstall (delete runtime)"
assert not hasattr(se, "derive_growth_from_figures"), "STILL OLD CODE — derive subsystem present; reinstall"
print("v1.24 OK — bands:", se.GROWTH_BAND_SCORE)     # -> {'high': 9, 'solid': 6, 'slow': 3, 'unknown': 4}
```

**Cell 2 — OpenAI client (your existing Step-2 setup):**
```python
from openai import OpenAI
client = OpenAI(api_key=...)   # your key
```

**Cell 3 — run R1 (takes the reads ONCE + scores off them; ~290 calls incl. N=4 bg, ~10–25 min):**
```python
from health_tech_research_agent import research_runner as rr
rep = rr.run_r1(df, client=client, model=MODEL, progress=print)
```

**Cell 3b — reproducibility proof (re-score off the cache; ZERO new calls, must be identical):**
```python
rep2 = rr.run_r1(df, client=client, model=MODEL, cache=rep["cache"])
print("REPRODUCIBLE (identical off cache):", rep["resolved"] == rep2["resolved"])
```

**Cell 4 — the report to paste back (tally + review set + reset reads + components):**
```python
print("R1 PASSED:", rep["passed"], "| tally:", rep["tally"], "| target:", rep["target"])
print("drift:", rep.get("discrepancies"))
print("REVIEW SET SIZE (bounded-review metric):", rep["review_set_size"], "/ 54")

print("\n-- proof + exceptions (resolved tier + why-flagged) --")
for co in ["season health", "affect therapeutics", "equip health", "familywell health", "fay",
           "foodsmart", "jasper health", "grow therapy", "function health", "angle health", "oula",
           "signos", "bicycle health", "pomelo care", "outcomes4me", "hinge health", "noom med"]:
    if co in rep["resolved"]:
        r = rep["resolved"][co]
        print(f"  {co:22} {r['final_priority']} ({r['layer']}) "
              f"{'FLAG:' + ','.join(rep['review_set'][co]) if co in rep['review_set'] else ''}")

print("\n-- RESET reads (hardened re-emit: who fires; the over-fires must be rejected by substance) --")
for co in sorted(rep["reset_reads"]):
    rr_ = rep["reset_reads"][co]
    if rr_["events"]:
        ev = "; ".join(f"{e.get('event_type')}/{e.get('creates_high_agency_opening')}" for e in rr_["events"])
        print(f"  {co:22} fires={str(rr_['fires']):5} [{ev}]")

print("\n-- component detail (bg/pmf/strain/stage/final) --")
for co in sorted(rep["detail"]):
    d = rep["detail"][co]
    print(f"  {co:22}{str(d['stage']):13} bg={str(d['bg_fit']):4} pmf={str(d['pmf']):4} "
          f"str={str(d['strain']):3} final={str(d['final']):6} ({d['layer']})")
```

## Paste back for adjudication

The Cell-4 output in full: the resolved tally, the proof + exception lines, the **RESET reads** (so we can
confirm `grow` fires and `sword`/`oura`/`noom` are correctly rejected by substance), the component detail,
and any DRIFT / INCONSISTENT. We adjudicate **by name**.

## The adjudication rule (agreed before the run)

R1 PASSES only if: the distribution is explainable **by name** — every documented anchor lands for the RIGHT
reason, the growth-BAND spot-checks read correctly (equip/pomelo/outcomes4me/hinge/function), no company
floors on a single-roll bg fluke (the cached bg is an N=4 average; a bg-floored real prospect surfaces in
`floored_on_bg`), and the `review_set` stays bounded. The 4/6/6/38 target is the spike ESTIMATE — under v1.24
(band growth + bg average) companies MAY move; a shift is diagnosed real-bug vs a genuinely-better read, never
nudged back. Any threshold/dial change is doc-first (SOT vX.Y bump on docs-scoring-sot), never a silent nudge.
On a clean, by-name-explained R1 → **Katelynd ratifies by name** → push Commit 8, merge docs+code to main,
delete `spike_disposable/` → Phase-3 complete.
