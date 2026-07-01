# Commit 8 — R1 RE-VALIDATION PROTOCOL (§B7 v1.20 N=5 stability)

> The R1 re-validation is the LAST Phase-3 hardening step: reproduce the spike tiering by NAMED company
> (`R1_TARGET = P0=4 / P1=6 / P2=6 / P3=38`, the live-54) by running each floor-eligible company **5×** and
> resolving via the §B7 v1.20 stability detector. It is a LIVE Colab job. Code branch `phase3-commit8-r1`,
> against SOT v1.20. **R1 is an HONEST check — a tally that only hits 4/6/6/38 via a quiet threshold nudge
> is a FAILED R1. Drift is diagnosed real-bug vs documented-exception BEFORE any re-fit; a re-fit is
> doc-first §B7, never a silent nudge.**
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

## What runs (v1.22 — CACHING, single read per company)

- **Once per company (cached, never re-rolled):** the four §B scoring reads — §B4 v1.16 hardened reset
  re-emit, §B2 classifier, §B6 growth, §B5 background_fit. Floored companies skip bg/growth (no spend).
- **Scoring reads OFF the cache** — no N passes, no temp-0 (rejected on `gpt-5.4-mini`). A re-score reads the
  same frozen values → identical tiers **by construction**. `run_r1(..., cache=rep["cache"])` re-scores
  without re-calling; `refresh=["equip health"]` re-takes only that company's reads (logged).
- **Cost: ~145 model calls, ONE time** (≈54 reset + 54 classifier + ~37 growth + ~37 bg). Re-scores are free.

**Option-B hardened reset (built into the reads).** The checkpoint's `reset_evidence` came from the OLD
liberal emitter (18 fire naively). The cached reset read re-runs the **committed hardened v1.16 emitter** over
`org_events_finding` and patches `fit_brief_json.reset_evidence`, so `derive_reset_signal` reads clean
type+opening (NO shim). This un-floors `grow` (first-CFO) and rejects the over-fires — the §B4
`DOCUMENTED_RESET_OVERRIDES` (hinge/noom) stay as belt-and-suspenders. **The frozen read must be CORRECT
(caching freezes it):** the run confirms `noom`/`hinge`/`equip`/`season` read correctly (or flagged).

## Documented exceptions the run must reproduce (each lands as recorded, NOT forced)

- `season health` → the ONE company whose TIER MOVES across the 5 runs → resolved **P1, `tier_variance`
  flagged**. **This + the six FINAL-14 staying P2 is the proximity-collapse-is-gone proof on real data.**
- the six FINAL-14 (`affect`, `equip`, `familywell`, `fay`, `foodsmart`, `jasper`) → **STABLE at P2**, no flag.
- `function health` → **P1** (human override; model call P3, not scored for stability).
- `angle` / `oula` → **P3** (floor result, bg_fit=4).
- `signos` / `bicycle` → stage **series-b** (v1.14 human-locked override, applied in `score_company`);
  `9amhealth` deterministic.
- R2 cases → `pomelo` / `outcomes4me` qualitative (no leaked rate); `season`'s ~53.7% found.

## The fresh notebook (thin — all logic is in the tested package)

The old notebook's middle (Old Flow → To Delete) is outdated and NOT used. Start a fresh notebook with four
cells. Everything scoring-side is committed package code; the notebook only sets up the client and calls one
function.

**Cell 1 — install the package from the branch + load the checkpoint:**
```python
!pip -q install "git+https://github.com/cleverturnip/health-tech-research-agent.git@phase3-commit8-r1"
import hashlib, pandas as pd
CKPT = "/content/drive/MyDrive/.../v42_full_regen_clean_slate_20260622_full56_checkpoint_FINAL.csv"  # your path
print("sha256:", hashlib.sha256(open(CKPT, "rb").read()).hexdigest())   # (optional) record the fingerprint
df = pd.read_csv(CKPT).fillna("")
print(len(df), "rows;", len(df.columns), "cols")
```

**Cell 2 — OpenAI client (your existing Step-2 setup):**
```python
from openai import OpenAI
client = OpenAI(api_key=...)   # your key
```

**Cell 3 — run R1 (takes the reads ONCE + scores off them; ~145 calls, ~5–15 min):**
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

R1 PASSES only if: the tally is 4/6/6/38 by name AND every documented exception lands as documented AND the
only flagged company is `season` (any additional flag must be a genuine, explainable wobble). Any drift →
diagnose real-bug vs documented-exception FIRST; a re-fit is doc-first §B7, never a silent nudge. On a clean
R1 → push Commit 8, merge docs+code to main, delete `spike_disposable/` → Phase-3 complete.
