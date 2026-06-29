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
