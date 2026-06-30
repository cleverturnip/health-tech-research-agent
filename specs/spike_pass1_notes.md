# Phase-2 Scoring Spike — Pass-1 Notes (regressions, staged wording, known issues, hardening)

Non-normative durability record for the disposable Phase-2 scoring spike (gated-then-ranked, clean-room from
SOT §B3–B7). Pairs with `SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md` (normative; v1.6). The spike is THROWAWAY —
Phase-3 hardening builds the committed scoring system separately. Captured here so nothing critical lives
only in chat.

## 1. Reset regression cases (AGENCY §B4 v1.5 — the 5 D+ reset calls)
The reset gate over-fired on Series-D+ in the spike's first run; SOT §B4 v1.5 sharpened it (substance-over-
label + IPO-prep non-qualifying + confidence bar). The 5 companies that hit the reset path, as named
regressions:

| company | reset | reason (per the EMITTED reset_events) |
|---|---|---|
| foodsmart | **FIRE** | clean founder→outside-CEO handoff (Kurt Knight, 2025-03), opening=yes leadership-change |
| grow therapy | **FIRE** | first-ever CFO seat (2026-04), opening=yes leadership-change (its integrated-care pivot = strategic-pivot, does NOT fire) |
| sword health | **EXCLUDE** | fired on "Sword Intelligence evolution" (declared-transformation) — substance is product-strategy = **pivot**; "Outcome Pricing" is a pricing pivot too |
| oura | **EXCLUDE** | fired on a confidential **S-1 / IPO-prep** draft — IPO-prep is non-qualifying |
| noom med | **EXCLUDE** | ⚠️ **accurate reason:** its leadership-change (a new CMO) was emitted `opening=yes`, NOT "unclear" as first characterized — excluded because it is a **growth-support exec add** ("to support GLP-1 / health-plan expansion"), not a reopening. (Its founder reconfig was `unclear`.) |

Spike re-run after v1.5: sword/oura/noom → AGENCY FAIL; foodsmart/grow → PASS; gate-floored 14→17 (surgical).

## 2. Reset-emitter wording — STAGED, awaiting joint-review re-validation (HARDENING)
The reset EMITTER (synthesis `reset_evidence` block in `research_runner.py build_fit_brief_prompt`) is
LLM-facing → brought for joint-review, **not self-merged**. The regen's emitter **pre-dates v1.5** and
mislabeled events (e.g. sword's pivot as "declared-transformation"), so the spike applies basis-regexes
(pivot / IPO-prep / growth-support) to the EMITTED events as a bridge. The permanent fix lands the
substance-classifying emitter below in the committed emitter during hardening, then the deterministic rule
is purely type + confidence (no basis-regex).

Final emitter wording (for the record):
- `event_type` classified by SUBSTANCE not press framing; a pricing/business-model/product-strategy change
  is `strategic-pivot` even if called a "transformation"; IPO / S-1 / public-market-readiness is `ipo-prep`;
  a growth-support exec add → `creates_high_agency_opening='unclear'`.
- `creates_high_agency_opening` ∈ {yes, unclear, no} — `yes` only when the event CLEARLY reopens a
  high-agency window; do not round up.
- Deterministic rule (code, Rule 7): `reset_fired = any(opening=="yes" AND event_type in {leadership-change,
  founder-transition, post-failure-rebuild, restructuring-layoffs, declared-transformation})`. strategic-
  pivot / ma-integration / ipo-prep are not firing types; `unclear`/`no` never fire; N unclears do not sum.

## 3. PMF growth-extraction — bug found + spike fix + residual limitation (HARDENING)
Pass-1 found the spike's PMF cap-squash (34/40 capped at 7, PMF nearly flat) was an **EXTRACTION bug, not a
data gap**: 52/54 growth findings carry quantified revenue/paid growth. Causes: (a) the spike capped every
`q4=credible-estimate` company (~30) as if missing; (b) zero-baseline ($0→$N) yields no %, so it scored only
the qualitative "growing". Fix (normative rule in SOT §B6 v1.6): derived/zero-baseline SCORE; cap only on
genuine absence. Result: cap 34/40 → **0/37**; PMF distribution now spreads 4–10 (a real ranker). This is
the extraction-layer twin of the Collaboration doc's web-search execution-variance root cause (absence ≠
measurement).

**Residual limitation (spike-grade; do NOT over-trust per-company growth):** the spike's regex extractor
still (a) **leaks count-growth** where revenue-growth is murky — `pomelo` (covered-lives +50%) and
`outcomes4me` (patient +485%) get an inflated growth_score because the fenced term sits outside the regex
window; and (b) **misses scattered figures** (e.g. `season`'s ~53.7% buried in the raw finding) → scores
qualitative instead. Per the convergence rule these were surfaced, **not** patched into a fragile
ever-widening regex. The permanent extractor (hardening) should be a robust parser or an LLM growth-presence
judgment (like the classifier) that reliably separates revenue/$-growth from member/patient/covered-lives
counts.

## 4. Classifier: human-locked floor + documented overrides (where they live)
Captured normatively in `SOURCE_OF_TRUTH.md` §B2 (v1.4) + `business_model_classifier_fixture.md` (v1.3):
- **Human-locked B2B floor (6):** openevidence, cohere health, zus health, om1, medically home, linus health
  — forced B2B (override the classifier); gate-fail Test A.
- **3 spike overrides:** noom med → B2C, signos → B2C (minor-employer who_pays), counsel health → B2B2C
  (evidence-thin). Scored from locked-fixture truth.

## 5. SEQUENCING — does scoring this checkpoint for Pass-2 calibration honor the second-regen gate?
The Collaboration doc locks: calibration is GATED behind a SECOND recovery-enabled regen (not the
untrustworthy V4.2 master). **Read: CONSISTENT.** The CSV the spike scores
(`v42_full_regen…full56_checkpoint_FINAL`) IS the second, recovery-enabled regen's output — exactly the
trustworthy data the gate requires. The cap-squash was a SPIKE-CODE extraction bug, not a data-trust
failure (the growth data is present, 52/54). Caveats for Pass-2: (a) calibrate on the EXTRACTION-FIXED
scores, not the buggy capped ones; (b) the spike's scoring logic (zero-baseline/derived scoring, the fence,
reset v1.5) must be carried into the hardened scorer or calibrated thresholds won't transfer.
**Katelynd's call — flagged, not overridden.**

## 6. HARDENING REQUIREMENTS (load-bearing — the biggest risk to Pass-2 transfer)
These are **requirements**, not notes. Pass-2 dials and thresholds will be calibrated against the spike's
scores; if the hardened Phase-3 scorer's extraction or gate logic drifts from the spike's, **those Pass-2
thresholds become INVALID** (they were fit to different numbers). Therefore:

**R1 — Carry the spike's scoring LOGIC into the hardened Phase-3 scorer, intact.** Specifically, the
hardened scorer MUST reproduce:
- **Zero-baseline scoring** ($0→$N scored on revenue magnitude × stage, not treated as missing) — SOT §B6 v1.6.
- **Derived-figure scoring** (credible third-party / Sacra/Latka/Growjo / "estimate" growth SCORES; it is not
  "undisclosed") — SOT §B6 v1.6.
- **The §B6.1 revenue-growth fence** (member / patient / covered-lives / download / headcount / utilization /
  partner / funding / valuation counts are SCALE, never growth_score).
- **Reset §B4 v1.5 substance + confidence rules** (substance-over-label; IPO-prep non-qualifying; `opening`
  must be a clear `yes`; growth-support exec adds do not fire; N unclears do not sum).
- **The PATH gates** (Test A B2B floor-fail; Test B B2C/B2B2C aliveness via revenue/scale/growth or a real
  institutional channel) and the **human-locked B2B floor** (SOT §B2 v1.4) + the 3 documented overrides.
- **The committed PMF scales (SOT §B6 v1.8):** Scale A (ARR-by-stage) + Scale B (growth-by-stage, engine-
  agnostic, `series-d-plus`→public row) + the shared GEOMETRIC round-half-up interpolation rule — NOT the
  spike's prior improvised `round(10·√(mag/ARR_BEST))` ARR curve or the stage-blind growth % bands.
- **NO acceleration bonus** (REMOVED + PARKED, SOT §B6 v1.8): growth_score is the BASE Scale-B value only;
  do not re-introduce +1/+2 unless a separate accelerating-at-scale metric is deliberately re-designed.
Any deviation in these is a calibration-invalidating change and MUST trigger re-calibration, not a silent ship.

**R2 — The hardened (LLM-based) growth extractor MUST handle these specific cases** that the spike's regex
extractor gets wrong (logged §3), because Pass-2 reads their spike scores with asterisks:
- `pomelo care` — must NOT count **covered-lives +50%** as revenue growth (spike LEAKS it → inflated).
- `outcomes4me` — must NOT count **patient +485%** as revenue growth (spike LEAKS it → inflated, grw=10).
- `season health` — must FIND the **~53.7%** revenue growth buried in the raw finding (spike MISSES it →
  scores qualitative 6, under-extracted).
The permanent extractor should be a robust parser or an LLM growth-presence judgment that reliably separates
revenue/$ growth from member/patient/covered-lives counts. Treat these three as named regression fixtures.

## 7. PMF improvised-curve bugs + acceleration provenance (FIXED v1.8; hardening regressions)
Pass-2 found BOTH halves of PMF were on §C-PLACEHOLDER curves the spike improvised (same root cause as the
§B6 growth-extraction bug — placeholder values invited improvisation):
- **ARR (Scale A):** the spike used `round(10·√(mag/ARR_BEST))` — a single sqrt curve that over-credited by
  2–4 pts vs the committed piecewise per-stage Scale A. FIXED → committed Scale A (SOT §B6 v1.8).
- **GROWTH (Scale B):** the spike used hardcoded STAGE-BLIND % bands (≥150→10, ≥80→8, ≥40→6, ≥15→4),
  ignoring that the bar must DECLINE across stages (100% YoY is a 5 at Series-A but a 10 at Pre-IPO).
  FIXED → committed stage-relative Scale B (SOT §B6 v1.8).
- **ACCELERATION (+1/+2):** provenance suspect (not a designed rule) and self-validating — its "+1 accel"
  anchors (Hinge/Omada/Maven) were exactly the base-7/7/4 companies it inflated to the cited 8/8/5. REMOVED
  from scoring + PARKED (SOT §B6 v1.8). The hardened scorer must NOT fire it.
- **Impact of the v1.8 fix** (deterministic re-run; bg_fit/strain unchanged): floor-eligible 20→15; five
  floor flips (9amhealth / allara / culina / oshi / summer → fail); FINAL distribution compressed downward
  (top 16-cluster 6→3). **Prior Step-B zero-baseline dial options are VOID** — recompute on the corrected
  scale.
- **Residual anchors investigated (reported, NOT overridden):**
  - **Rula** ~100% YoY / SerC → Scale-B base **8** (anchor expected 10). The dated rate IS ~100% (Sacra
    $235M→$471M). The anchor-10 reading only holds on the PUBLIC growth row, and Rula's **$471M revenue is
    public-scale** — a possible stage-LABEL artifact, not a scale error. Rula's pmf=**9 is STABLE** across
    series-c (arr10/grw8) vs public (arr7/grw10) — immaterial to ranking. No change.
  - **Cohere** +20% / SerC (anchor 3) → the spec's +20% input is **STALE**: the actual research shows
    **>60% YoY** (company-reported 2024) + ~9.1x over 2021–24 → Scale-B base **6**, not 2/3. Cohere is
    B2B-floored (ranking-moot) regardless. No change. Both confirm Scale B is sound.
- **Stage-label sensitivity (research-quality flag).** The committed scales are strongly stage-driven (the
  Series-B ARR row tops at $80M=10 while Series-C starts at $30M=1 — deliberate overlap), so a NOISY stage
  label swings arr_level 2–5 pts (zoe/bicycle/function/nourish/oula are the largest swings). Accurate
  research-layer stage assignment is now load-bearing; noisy labels are a Pass-2 review item, not a scale fix.

## 8. STAGE-ASSIGNMENT: DESIGNATED-SERIES discriminator (SOT §B4 v1.10; hardening requirement)
The STEP-0 stage audit surfaced a RULE GAP, not 3 separate errors: v1.9 excluded extensions/bridges/SAFE/debt
but did NOT cover a CLOSED, PRICED venture round under the SAME existing series, so the audit leaned toward
advancing on any real closed round. SOT §B4 v1.10 adds the **DESIGNATED-SERIES discriminator**: the series
letter advances ONLY on a round explicitly designated the next series; same-series capital (incl. a sizable
closed priced venture round) keeps the last designated series; undesignated later round → last confirmed
series + `stage_confidence=low`. Resolved 3 spike corrections (Katelynd): **signos** series-c→**series-b**
($20M 2026 = same-series venture round), **bicycle** series-c→**series-b** (later funding, no designated
Series C), **9amhealth** stays **series-b** (Series B was clean in the research output; the audit MISREAD it
as a Series A extension — a reading error on correctly-captured data).
- **HARDENING REQUIREMENT (adds to R1):** the hardened `funding_stage` mapper/synthesis MUST implement the
  v1.10 designated-series discriminator (a same-series round does not promote). The 9amhealth case shows the
  audit/extraction can MISREAD a correctly-captured label, so the hardened stage assignment must make the
  **designated-series signal explicit** (capture the round's series designation, not just "a later priced
  round exists"). Until then, stage corrections are applied as a spike STAGE_OVERRIDE (Katelynd-approved),
  the disposable analogue of the §B2 human-locked floor.
