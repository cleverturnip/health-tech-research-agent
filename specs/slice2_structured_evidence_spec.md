# Slice 2 — Structured Evidence Fields (maturity + commercial signal)

Implements the Rule 7 fix the research-runner audit surfaced: the LLM gathers EVIDENCE
(facts + answers to pointed questions); DETERMINISTIC rules assign the labels/signals.
Replaces the current pattern where the LLM emits judgments (a maturity label, a
commercial strength signal) that can't be checked — the cause of the Function Health
mislabel and the Solace false-strong.

Core principle: gather facts once (expensive research), derive labels deterministically
from stored components (cheap, re-runnable). Persist the COMPONENTS as columns, not just
the derived label — so labels/signals can be recalibrated WITHOUT re-running research.

---

## Part A — Maturity (deterministic from funding stage)

Decision: funding stage alone anchors maturity. Revenue/scale NEVER touches maturity
(it lives in the commercial signal). This separation is the Function Health fix — a
Series B hypergrowth company stays early-growth, not "late-stage."

### LLM gathers (facts, persisted as columns):
- `funding_stage` — most recent round: seed | series-a | series-b | series-c |
  series-d-plus | public | unknown
- `ipo_status` — private | filed | public (+ date if public)
- `founding_year`
- `last_raise_date`, `last_raise_amount`, `total_funding` — disclosure-dependent, supporting
- `funding_stage_evidence` — short source/basis text for the stage determination

### Deterministic maturity rule (reads the stored facts):
```
ipo_status == public           -> "public"
ipo_status == filed (S-1)      -> "near-ipo"
funding_stage == series-d-plus -> "late-stage"
funding_stage == series-c      -> "scale-up"
funding_stage in {series-a, series-b} -> "early-growth"
funding_stage in {seed, pre-seed}     -> "early"
otherwise (unknown / undeterminable)  -> "unclear"  + FLAG for human review
```

Rules:
- near-IPO = filed S-1 ONLY (clean/deterministic; no "effectively pre-IPO" fuzziness).
- Unknown stage -> "unclear" + flag. NO LLM guessing/inference of a stage.
- The old keyword text-scan maturity inference (`_rt_infer_maturity_read`, and STEP 26's
  `step26_infer_maturity_and_cap` defined twice) is RETIRED — same brittle pattern as the
  reset text-scan already removed.

---

## Part B — Commercial signal (Option C: facts + structured red-flags -> deterministic)

Decision: the LLM gathers commercial facts AND answers four pointed red-flag questions;
a deterministic rule assigns the 0-3 signal. Funding evidence is captured but
STRUCTURALLY EXCLUDED from the signal (the Solace fix). The revenue-to-customer RATIO
carries signal that neither number carries alone, so the red-flag questions surface it
rather than a fixed threshold (which would misfire across business models).

### LLM gathers (facts, persisted as columns — funding kept separate):
- `revenue_or_arr` — figure + source
- `paying_customer_count` — PAYING users/subs/members (not free/pilot) + source
- `revenue_per_user` — derived or gathered
- `growth_signal` — growing | flat | declining (+ rough rate if available)
- `business_model_type` — consumer-subscription | enterprise | payer-reimbursed | other
  (context for reading the ratio)
- `funding_evidence` — raises/valuation; CAPTURED but EXCLUDED from the commercial signal

### LLM answers four structured red-flag questions (persisted as columns):
- `q1_acquisition` — paying base growing | flat | declining
- `q2_monetization` — revenue-per-user strong | typical | weak *for this business model*
- `q3_funding_dependent` — does the commercial story rest mainly on funding/valuation
  rather than revenue/paying customers? yes | no  (the explicit Solace catch)
- `q4_evidence_quality` — company-reported | credible-estimate | unverified-promotional

### Deterministic commercial signal rule (reads stored facts + red-flags):

A "genuine traction strength" = high revenue-per-user (q2=strong) OR large-and-growing
paying base (substantial paying_customer_count AND q1=growing).

```
STRONG (3):
  has a genuine traction strength
  AND q4 in {company-reported, credible-estimate}      (unverified/promotional cannot be strong)
  AND q3_funding_dependent == no
  AND NOT the trap (NOT [q1==declining AND q2==weak])

MODERATE (2):
  real paying customers + revenue exist, no standout strength; OR
  would-be-strong signals resting only on unverified/promotional evidence (q4 fails -> capped here); OR
  funding-dependent (q3==yes) BUT real traction exists  (funding-dependence is a hard ceiling: never strong)

WEAK (1):
  minimal real commercial evidence (tiny paying base); OR
  the trap: q1==declining AND q2==weak; OR
  funding-dependent (q3==yes) with negligible real traction

NONE (0):
  no credible commercial traction evidence at all
```

Key rules:
- Funding-dependence (q3=yes) is a HARD CEILING: caps at moderate if real traction exists,
  drops to weak if real traction is negligible. Never strong. (Solace.)
- Credible third-party estimates CAN support strong (retention/revenue data is often not
  public); only unverified/promotional evidence is disqualifying from strong. (Function's
  Sacra-estimated $100M counts; pure promotional claims do not.)
- The old dollar-token commercial text-scan (`infer_commercial_signal` strong_markers:
  "$100m", "$1b", "arr", "revenue run-rate" — which can't tell revenue from funding) is
  RETIRED.

---

## Part C — Calibration note (why components are persisted)

The MODERATE/WEAK boundary is inherently RELATIVE — "typical monetization," "modest base,"
"strong revenue-per-user for the model" only mean something against a distribution of
comparable companies, which does not exist until the first regeneration produces it.

Therefore:
- The first regeneration is the pass that BUILDS the reference frame. Its job is to gather
  evidence completely and granularly, and to get STRONG right (strong is anchored on
  near-objective conditions: funding-dependence, evidence quality, a genuine traction
  strength — it will hold).
- The MODERATE/WEAK boundaries are CALIBRATED AFTER the frame exists, against the assembled
  distribution — NOT expected to be perfect on the first pass.
- Because the 0-3 signal is a DETERMINISTIC FUNCTION OF STORED COMPONENTS, recalibrating the
  thresholds is a cheap deterministic re-score — NO re-research needed. The expensive part
  (gathering facts) runs once; the cheap part (where moderate ends and strong begins) is
  tuned iteratively against the distribution.

Design requirement this imposes: PERSIST THE COMPONENTS as columns (both maturity facts and
commercial facts + red-flag answers), and make the maturity label and the 0-3 commercial
signal DETERMINISTIC FUNCTIONS of those stored columns — recomputable without research.

---

## What this slice does NOT include (separate slices)
- Reset as a researched field (Slice 3) — distinct from a strategic pivot (the Noom point).
- Real capability-fit / the three-attribute rubric (Slice 4).
- The runner extraction itself (Slice 1) — this slice defines the prompt fields + derivation
  rules; the extraction wires the runner into the package. Sequencing of 1 vs 2 TBD with the
  build (the prompt fields here will be added to run_company_fit_brief, which Slice 1 moves).

## Open implementation notes for the build
- The fit-brief prompt (`run_company_fit_brief`) is the single insertion point and feeds both
  STEP 7 (fresh research) and STEP 26 (rescore) — one prompt edit covers both.
- Add the new fields to the prompt's structured output; parse in the STEP 10 flatten
  (same `extract_score`/field pattern); persist as master columns.
- Maturity derivation and the commercial 0-3 rule should be DETERMINISTIC PACKAGE FUNCTIONS
  (testable, red->green), reading the stored component columns — not notebook text-scans.
- Retire: `_rt_infer_maturity_read`, `step26_infer_maturity_and_cap` (x2), and
  `infer_commercial_signal`'s dollar-token strong_markers.
