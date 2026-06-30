# Commit 8 — R1 RE-VALIDATION PROTOCOL (§B7 v1.20 N=5 stability)

> The R1 re-validation is the LAST Phase-3 hardening step: reproduce the spike tiering by NAMED company
> (`R1_TARGET = P0=4 / P1=6 / P2=6 / P3=38`, the live-54 — firefly + videahealth deferred) by running each
> floor-eligible company **5×** and resolving via the §B7 v1.20 stability detector. It is a LIVE Colab job
> (the LLM-variable inputs re-run): build against SOT v1.20, code branch `phase3-commit8-r1`. The
> deterministic machinery (`score_company`, `revalidate_r1`) is committed + tested; this doc is the live
> run protocol. **R1 is an HONEST check — a tally that only hits 4/6/6/38 via a quiet threshold nudge is a
> FAILED R1. Any drift is diagnosed real-bug vs documented-exception BEFORE any re-fit, and a genuine
> re-fit is doc-first §B7.**

## What re-runs (and what does NOT)

- **Re-runs each pass (LLM-variable):** `background_fit` for every floor-eligible consumer company; `growth`
  for the R2 cases ONLY (`pomelo`, `outcomes4me`, `season` — confirm the set).
- **Identical every pass (deterministic BY CONSTRUCTION — do NOT re-roll):** the classifier read, PATH,
  AGENCY (stage + reset), ARR-level, strain, floor rule, thresholds. They come from the persisted columns.

## Column contract — `score_company` reads these persisted columns (CONFIRM they exist in the checkpoint)

`company` · `who_uses` · `who_pays` · `who_uses_confidence` · `funding_stage` · `ipo_status` ·
`reset_events_json` · `reset_event_types` · `revenue_or_arr` · `sponsored_user_scale` ·
`paying_customer_count` · `growth_signal` · `payer_institutional_finding` · `business_model_type` ·
`growth_kind` · `growth_rate_pct` · `growth_magnitude_usd_m` · `growth_qualitative` · `growth_source` ·
`capability_a2_score` · `operating_characteristics`.
(`background_fit` is NOT read from the checkpoint — it is the live re-run input, passed per pass.)

## Documented exceptions the run must reproduce (each lands as recorded, NOT forced)

- `season` → the ONE company whose TIER MOVES across the 5 runs → resolved **P1, `tier_variance` flagged**
  (grw=3 after the R2 fix — expected lower than the spike's 5).
- the six FINAL-14 (`affect`, `equip`, `familywell`, `fay`, `foodsmart`, `jasper`) → **STABLE at P2**, no
  flag. **This is the proximity-collapse-is-gone proof — on real data, not seeded.**
- `function` → **P1** (human override; model call P3, not scored for stability).
- `angle` / `oula` → **P3** (floor result, bg_fit=4).
- `signos` / `bicycle` → stage **series-b** (v1.14 human-locked override); `9amhealth` deterministic.
- R2 cases → `pomelo` / `outcomes4me` qualitative (no leaked rate); `season`'s ~53.7% found.

## The cell (fingerprint-gated) — DRAFT, pending the two CONFIRM points

Prepend the standard Step-A branch-pull cell (pull `phase3-commit8-r1`) and the Step-2/3 cells that define
`client` + `call_openai`.

```python
# === Commit 8 — R1 RE-VALIDATION (§B7 v1.20 N=5 stability) — fingerprint-gated ===
import hashlib, json
import pandas as pd
from health_tech_research_agent import structured_evidence as se
from health_tech_research_agent import research_runner as rr

# --- 0. FINGERPRINT GATE (CONFIRM the path + the known sha256) ---
CKPT = "/root/Downloads/v42_full_regen_clean_slate_20260622_full56_checkpoint_FINAL.csv"
EXPECT_SHA = "<<PASTE THE KNOWN CHECKPOINT SHA256>>"
sha = hashlib.sha256(open(CKPT, "rb").read()).hexdigest()
assert sha == EXPECT_SHA, f"checkpoint fingerprint mismatch: {sha} (refusing to run on the wrong data)"
df = pd.read_csv(CKPT).fillna("")

# --- 1. config ---
N = 5
R2_CASES = {"pomelo", "outcomes4me", "season"}     # CONFIRM the R2 set (growth re-runs live)

def bg_evidence_for(row):
    # CONFIRM: assemble the SAME bg_fit evidence blob the SIGNED Commit-4 bg_fit run fed (the habit /
    # engagement / operating-characteristics evidence). Reuse that exact line — do not improvise it.
    return str(row.get("operating_characteristics") or "")

# --- 2. deterministic floor-eligibility (computed once; bg_fit re-runs ONLY for floor-eligible consumers) ---
def floor_eligible(r):
    bm, _ = se.business_model_for(r.get("company"), r.get("who_uses"), r.get("who_pays"),
                                  r.get("who_uses_confidence"))
    pa, _ = se.path_gate(bm, r)
    stage = se._norm_stage(r.get("funding_stage"))
    key = se._norm_company(r.get("company"))
    if key in se.DOCUMENTED_STAGE_OVERRIDES:
        stage = se.DOCUMENTED_STAGE_OVERRIDES[key]
    ag, _, _ = se.agency_gate(stage, se.derive_reset_signal(r), ipo_status=r.get("ipo_status"))
    return pa and ag and se.background_fit_applies(r.get("who_uses"))

# --- 3. the N=5 runs ---
rosters = []
for run_i in range(N):
    roster = []
    for _, srow in df.iterrows():
        r = dict(srow)
        bf = None
        if floor_eligible(r):
            raw = rr.run_company_background_fit(r["company"], bg_evidence_for(r), client=client)
            bf = se.flatten_background_fit_fields(json.loads(raw)).get("background_fit")
            if se._norm_company(r["company"]) in R2_CASES:
                graw = rr.run_company_growth(r["company"], se.canonical_growth_evidence(r), client=client)
                r.update(se.flatten_growth_read(json.loads(graw)))
        roster.append(se.score_company(r, background_fit=bf))
    rosters.append(roster)
    print(f"run {run_i + 1}/{N} complete")

# --- 4. resolve + report ---
rep = se.revalidate_r1(rosters)
print("R1 PASSED:", rep["passed"], "| tally:", rep["tally"], "| target:", rep["target"])
print("tier_variance (flagged straddlers):", rep["tier_variance"])
for co in ["season", "affect", "equip", "familywell", "fay", "foodsmart", "jasper"]:
    if co in rep["vectors"]:
        print(f"  {co:14} runs={rep['vectors'][co]} -> {rep['resolved'][co]}")
if rep["discrepancies"]:
    print("DRIFT (target vs actual):", rep["discrepancies"])
if rep["inconsistent_companies"]:
    print("INCONSISTENT (missing from a run):", rep["inconsistent_companies"])
```

## CONFIRM before the run (≈200 LLM calls — don't spend it on an unverified contract)

1. **Checkpoint path + `EXPECT_SHA`** — paste the known sha256 (refuse to run on the wrong bytes).
2. **`bg_evidence_for`** — the exact bg_fit evidence assembly the signed Commit-4 run used.
3. **Column contract** — the columns above all present in the checkpoint.
4. **`R2_CASES`** — confirm `{pomelo, outcomes4me, season}`.

## Paste back for adjudication

The per-company 5-run vectors for `season` + the six FINAL-14, the resolved tally, the `tier_variance` set,
and any DRIFT / INCONSISTENT lines. Then: clean 4/6/6/38 with every exception as documented → R1 passes →
Phase-3 hardening complete (merge-to-main milestone). Any drift → diagnose real-bug vs documented-exception
first; a re-fit is doc-first §B7, never a silent nudge.
