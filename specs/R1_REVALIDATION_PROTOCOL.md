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

## What re-runs (v1.20 + Option-B reset re-emission)

- **Once per company:** the **§B4 v1.16 HARDENED RESET re-emission** (Option B — see below); §B2 classifier;
  base §B6 growth (floor-eligible only).
- **Every pass (LLM-variable):** §B5 background_fit (every floor-eligible company); §B6 growth (R2 cases —
  `pomelo care`, `outcomes4me`, `season health`).
- **Floored companies:** None bg/growth reads → P3 every run (they still get the once reset re-emit + classifier).

**Option-B reset re-emission (built into `run_r1`).** The checkpoint's `reset_evidence` was researched with
the OLD liberal emitter (18 events fire naively). `run_r1` re-runs the **committed hardened v1.16 emitter**
(validated 5/5 in Commit 3a) over each company's `org_events_finding` and patches `fit_brief_json.reset_evidence`
in place, so `derive_reset_signal` reads clean type+opening (NO shim). This un-floors `grow` (first-CFO →
P0) and rejects the liberal over-fires (`sword`/`oura`/`noom` → pivot/ipo-prep/growth-support). **Cost: ~350
model calls** (≈54 reset + 54 classifier + ~37 base growth + 5×(~37 bg + 3 R2 growth)).

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

**Cell 3 — run R1 (one call; ~5–20 min, ~350 model calls incl. the reset re-emission):**
```python
from health_tech_research_agent import research_runner as rr
rep = rr.run_r1(df, client=client, n=5, progress=print)
```

**Cell 4 — the report to paste back (tally + proof companies + component detail + RESET reads):**
```python
print("R1 PASSED:", rep["passed"], "| tally:", rep["tally"], "| target:", rep["target"])
print("tier_variance (flagged):", rep["tier_variance"], "| drift:", rep.get("discrepancies"))

print("\n-- proof + exceptions (5-run vectors -> resolved) --")
for co in ["season health", "affect therapeutics", "equip health", "familywell health", "fay",
           "foodsmart", "jasper health", "grow therapy", "function health", "angle health", "oula",
           "signos", "bicycle health", "pomelo care", "outcomes4me"]:
    if co in rep["resolved"]:
        print(f"  {co:22} runs={rep['vectors'].get(co)} -> {rep['resolved'][co]}")

print("\n-- RESET reads (hardened re-emit: who fires, and why the naive over-fires are rejected) --")
for co in sorted(rep["reset_reads"]):
    rr_ = rep["reset_reads"][co]
    if rr_["events"]:   # only companies with reset events
        ev = "; ".join(f"{e.get('event_type')}/{e.get('creates_high_agency_opening')}" for e in rr_["events"])
        print(f"  {co:22} fires={str(rr_['fires']):5} [{ev}]")

print("\n-- component detail (bg/pmf/strain/stage/final, first run) --")
for co in sorted(rep["detail"]):
    d = rep["detail"][co][0]
    print(f"  {co:22}{str(d['stage']):13} bg={str(d['bg_fit']):4} pmf={str(d['pmf']):4} "
          f"str={str(d['strain']):3} final={str(d['final']):6} {d['tier']} ({d['layer']})")

if rep["inconsistent_companies"]:
    print("INCONSISTENT:", rep["inconsistent_companies"])
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
