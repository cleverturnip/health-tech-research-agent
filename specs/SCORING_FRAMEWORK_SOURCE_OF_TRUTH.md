# Scoring & Priority Framework — SOURCE OF TRUTH

**FRAMEWORK_VERSION: v1.11 (2026-06-29)**
**Changelog:** v1.11 — PASS-2 COMPLETE: §B7 THRESHOLDS + DIALS LOCKED (calibrated vs the v1.10 spike distribution). Replaced the §B7 PLACEHOLDER (P0=21-23…) with calibrated thresholds **P0 ≥18 / P1 15-17 / P2 13-14 / P3 <13**, and made the FLOOR-RULE-GATES-FIRST precedence explicit (a floor-FAIL is P3 regardless of FINAL; tiers apply only to floor-PASS). Promoted the dials to LOCKED: 40/60 split KEPT (near-inert), strain max KEPT +2, no-quantified-rate growth KEPT 5 (neutral-mid, Rule-8 don't-gate-on-absence), small-base growth dampener NONE-by-design (no double-count — revenue scale is gated by PATH + floor, not by penalizing growth). Net: no dial changed the v1.10 distribution. Recorded 2 review-time HUMAN DECISIONS (Rule 6): Function Health P3→**P1 OVERRIDE** (revenue+complexity unicorn exception, flagged, not a logic change); Angle + Oula **P3 by floor-rule** (FINAL=14 but floor-FAIL — episodic-vs-habitual split is intended at equal FINAL). Thresholds are SPIKE-PROVISIONAL and carry the R1 hardening caveat (re-validate if the hardened scorer drifts). Final tiered deliverable: `specs/SPIKE_FINAL_RANKING.md` (SPIKE OUTPUT — disposable, pending Phase-3 hardening). v1.10 — §B4 STAGE-ASSIGNMENT RULE sharpened with the DESIGNATED-SERIES discriminator. The STEP-0 audit surfaced a rule GAP (not 3 separate errors): v1.9 excluded extensions/bridges/SAFE/debt but did not cover a CLOSED, PRICED venture round under the SAME existing series, so the audit leaned toward advancing on any real closed round. Added: a new round advances the stage ONLY when DESIGNATED a new series; a same-series venture round / top-up / internal round / extension / bridge / SAFE / convertible / debt keeps the stage at the last DESIGNATED series (even if closed + priced + sizable); when a later round's designation is unstated, default to the last CONFIRMED designated series + stage_confidence=low (no promotion on an undesignated round). Resolves all 3 audit anomalies as same-cause: signos (Series B + later $20M venture round = still Series B → corrected series-c→series-b), bicycle (Series B + later funding, no designated Series C → corrected series-c→series-b), 9amhealth (Series B clean in the research output; the audit MISREAD it as a Series A extension → stays series-b as originally scored). v1.9 — §B4 STAGE-ASSIGNMENT RULE committed (LOCKED). The corrected v1.8 scales are strongly stage-driven (deliberate Series-B/C ARR overlap → a B↔C mislabel swings arr_level 2–5 pts), so `funding_stage` determination is now score-critical and must not be improvised. RULE: stage = the most-recent CLOSED, priced equity round (seed/A/B/C/D–E/pre-IPO–public) evidenced by a dated completed-raise announcement; announced-but-not-closed / rumored / extension / bridge / SAFE / convertible / debt does NOT advance the stage; date-stamp the determination and set stage_confidence=low + flag when ambiguous (no guessing, Rule 8); revenue scale does NOT override the funding label (a high-revenue Series-C stays Series-C — Rula — a mismatch is a signal to re-check currency, not a license to relabel by revenue). Pass-2 STEP-0 stage audit precedes any dial calibration. No scores changed by this rule alone (audit + corrections decided with Katelynd, then one re-run). v1.8 — §B6 PMF SCALES COMMITTED + ACCELERATION REMOVED. Both halves of PMF were on §C-PLACEHOLDER curves the spike improvised: ARR used `round(10·√(mag/ARR_BEST))` (over-credited 2–4 pts) and growth used stage-blind % bands. Replaced with the committed-intent **Scale A — ARR-by-stage** and **Scale B — growth-rate-by-stage** (engine-agnostic; declining bar across stages by design) tables, both LOCKED, plus a shared **geometric round-half-up INTERPOLATION RULE**. Stage maps: ARR "Series D/E"→series-d-plus, "Pre-IPO/Public"→public; growth series-d-plus→public row (no separate D/E growth row), seed/a/b/c 1:1. **ACCELERATION (+1/+2) REMOVED from scoring and PARKED** (open question) — provenance suspect + self-validating (its "+1 accel" anchors Hinge/Omada/Maven were exactly the base-7/7/4 companies it inflated to 8/8/5). growth_score is now the BASE Scale-B value only. Zero-baseline still scores the magnitude reached via Scale A (arr=growth collapse stays, numbers corrected); §B6.1 fence + missing-data cap@7 + derived-figure scoring UNCHANGED. Two residual anchors (Rula +100%/SerC base 8 vs anchor 10; Cohere +20%/SerC base 2 vs anchor 3) flagged for investigation, not overridden. v1.7 — §B5 BACKGROUND-FIT promoted STAGED → LOCKED: the bg_fit gradient wording was validated this session (Colab, 37/37 gate-passed; the Nourish "periodic"-mislabel regression PASSED at bg_fit=8; the data-feedback-loop flag fired only on the metabolic/tracking loops levels/signos/oova/9amhealth). The literal validated prompt is now embedded as the locked gradient prompt (data-feedback-loop top-of-scale amplifier 9–10; 6–8 floor-protection band for strong-habit-without-loop; bottom "do NOT under-score / periodic-trap" guard). Recorded the FUNCTION / low-frequency override note (audit trail, Rule 6): the gradient DELIBERATELY scores low-frequency engagement low (2×/year lab products → ~4) and this is CORRECT and intended; Function Health is a known REVIEW-TIME human-override candidate (revenue+complexity unicorn exception), NOT a scoring-logic change. Structure (gradient 1–10, errors recoverable, `who_uses==consumer` precondition, `data_feedback_loop` emitted as a separate flag) UNCHANGED. v1.6 — §B6 GROWTH-EXTRACTION SCOPE clarified (Pass-1 found the spike's PMF cap-squash was an EXTRACTION bug, not a data gap — 34/40 capped → 0): zero-baseline ($0→$N, scored on revenue-magnitude × stage, an OPEN DIAL) and DERIVED/third-party growth MUST be SCORED; the missing-data cap is ONLY for genuinely-absent revenue-growth; §B6.1 fence preserved (counts — covered-lives/patient/member — are scale, not growth). Non-normative Pass-1 records (reset regressions, emitter wording, extraction known-issue) live in `spike_pass1_notes.md`. v1.5 — §B4 RESET sharpened (Pass-1 found the emitter over-fired on Series-D+ via 3 patterns): (1) SUBSTANCE-over-label — a business-model/pricing/product-strategy change is a strategic-pivot and NEVER fires, even if labeled "declared-transformation" (sword); (2) IPO-prep / S-1 / public-market-readiness is NON-QUALIFYING, added to the NEVER-fire list (oura); (3) CONFIDENCE bar — an "unclear"/low-confidence event does NOT fire, and N unclear events do not sum to a fire (noom). Mapper + maturity buckets + Rule-7 single-emitter UNCHANGED. v1.4 — B2B floor is now a MAINTAINED HUMAN-LOCKED LIST (6: openevidence, cohere health, zus health, om1, medically home, linus health) that OVERRIDES the classifier (gate-critical; the classifier can't reliably hold the provider-tool / hospital-at-home-enablement vs own-care-team `who_uses` boundary — medically home oscillated across 3 tuning rounds). Mapper logic UNCHANGED; the floor is an override layer. Also synced the stale §B2 inline fixture block to v1.3 truth (6/8/41; angle→B2B2C; dropped angle/outcomes4me asserts). v1.3 — renamed `user_scale_signal` → `sponsored_user_scale` for clarity (institutionally-sponsored end-user reach; routing + structural bar unchanged). v1.2 — B6.1 LOCKED: secondary user-scale signal routing (headcount→A2 strain, partner/client-count→`institutional_distribution_signal`, funding→`funding_evidence`, non-paying user-scale→new `sponsored_user_scale`), with STRUCTURAL enforcement (no score-consumer reads `sponsored_user_scale`). v1.1 — added B6.1 (secondary user-scale signal routing) as a reserved OPEN slot. v1 — initial canonical capture.
**Status:** canonical. This is the ONE doc the design chats AND Claude Code point at for the scoring +
priority framework. If a decision about scoring logic isn't here, it isn't locked. When scoring logic
changes, it changes HERE first (version bumps), and Claude Code commits the doc-update BEFORE building
anything that depends on it (see DISCIPLINE, bottom).

**How to read this doc — three layers, on purpose:**
1. **NARRATIVE / WHY** (§A) — what changed from the old model and the reasoning behind each change.
   Preserved verbatim-in-spirit from the old-vs-new diff. If we ever reopen the scoring logic, START
   HERE — this is the expensive-to-reconstruct part.
2. **LOCKED BUILDABLE DETAIL** (§B) — the specific, buildable logic Claude Code implements. The "what."
3. **STABILITY MARKINGS** (§C) — every point tagged STABLE / OPEN-DIAL / PLACEHOLDER so no one builds
   or calibrates against a number that's still moving.

A note on scope: the RESEARCH-LAYER work (search_with_recovery, per-field N, derive) lives in its own
thread/docs; it is referenced here only where it gates the scoring model (the second regen → calibration
bar). This doc is the SCORING + PRIORITY framework.

---

# §A — NARRATIVE / WHY (the reasoning; start here if reopening the logic)

## TL;DR — the one-sentence diff
OLD = a single blended score that rewarded ABSOLUTE revenue magnitude (favoring mature/big companies)
and used fuzzy fit/quality judgments as if they were reliable; NEW = a GATED-then-RANKED model where
reliable facts ELIMINATE (gates), fuzzy judgments only RANK (gradients, errors recoverable), revenue is
graded RELATIVE TO STAGE (a strong Series B beats a big-but-flat public co), and the hardest judgments
are routed to human review instead of forced into the model.

## A1. ARCHITECTURE — blended score → gated-then-ranked
**OLD:** effectively a weighted blend of signals (thesis_fit, pmf_scale, capability/role_fit,
operator_timing, evidence_confidence) producing a priority. Problem: averaging everything lets a company
that's great on three signals and disqualifying on one (a pure-B2B company, or a public mega-cap) float
UP when it should be floored. Original symptom: a collapsed distribution (the spec's "93%-P3 problem").
**NEW:** three stages, each fact enters EXACTLY ONCE:
- STAGE 1 GATES (pass/fail, eliminate): AGENCY + PATH-TO-SCALE. Fail either → P3, stop.
- STAGE 2 GRADIENTS (1–10, rank): BACKGROUND FIT + PMF SIGNS.
- STAGE 3 MODIFIER: STRAIN (small capped bump).
- FINAL = Background Fit + PMF + Strain; FLOOR RULE: P0/P1 require BOTH gradients > 4.
**Why:** reliable binary facts (maturity, is-there-a-consumer) belong in gates that eliminate; fuzzy
judgments (how-good-a-fit, how-proven) belong in gradients that rank. Gating first prevents the
great-on-three-bad-on-one float-up. **Why "each fact once" is load-bearing:** the old blend implicitly
double-counted (a fast-growth company got credit in pmf_scale AND again wherever growth leaked into fit/
timing). The new model assigns each fact ONE home so a single strength can't inflate multiple stages —
this is the invariant every later rule protects (see B1).

## A2. PMF — absolute magnitude → STAGE-RELATIVE
**OLD:** `pmf_scale_score` rewarded ABSOLUTE revenue/scale → systematically favored mature, big companies
(the exact bias the thesis rejects — the goal is to join EARLY and build to $100M ARR).
**NEW:** PMF grades revenue RELATIVE to a hardcoded per-stage benchmark (two 1–10 scales: ARR-by-stage +
growth-by-stage). A Series B at $100M ARR is best-in-class; a public co at $260M can score mid. Composite
= 40% ARR-level + 60% growth (growth-weighted because the thesis bets on the slope). Missing-revenue cap
(≤7 on estimates-only). Acceleration bonus (+1/+2) on the growth scale.
**Why growth-weighted:** the thesis is a bet on the SLOPE to $100M ARR, not the current level — so the
heavier weight goes on growth. **Why a cap on estimates:** a company scored on inferred/estimated revenue
can't be allowed to reach best-in-class on numbers we're not sure of (carry-and-rate, never pretend
confidence). This is NEW deterministic logic (the stage-benchmark map), NOT a re-bucketing of the old
score.

## A3. BUSINESS MODEL — wrong-axis fuzzy field → forced who-pays/who-uses classifier
**OLD:** `business_model_type` was on the REVENUE-MECHANISM axis ("consumer-subscription / enterprise /
payer-reimbursed / other") — and mislabeled the key B2B case (OpenEvidence) as B2B2C. Unreliable, and the
PATH gate can't floor on it.
**NEW:** a forced B2B/B2B2C/B2C classifier, Rule-7 style — LLM extracts who_uses (consumer|professional)
+ who_pays (consumer|institution|mixed); a DETERMINISTIC mapper emits the label (LLM never emits it).
who_uses rule locked (consumer-interacts-with-THIS-product = B2B2C even if an institution pays; product-
operated-behind-the-scenes = B2B). Frequency firewall (a daily-using clinician is still `professional`).
**Why the who_uses axis (not who_pays) decides B2B:** the thesis cares whether a CONSUMER is the end-user
(that's the business Katelynd knows how to build); who-pays is a revenue-mechanism detail that doesn't
change whether there's a consumer to build for. **Why the frequency firewall:** the old model let high
usage frequency push a professional tool into the consumer bucket (the OpenEvidence error) — frequency is
scored elsewhere (engagement), it must not contaminate who_uses. This classifier is the LINCHPIN — PATH
Test A floors B2B on it.

## A4. AGENCY GATE — (largely new as an explicit gate)
**NEW (explicit):** maturity from funding stage. Series A/B/early-C PASS; Series D+ FAILS unless a RESET
fired (leadership change / declared transformation / restructuring reopens the build-window for a mature
company). Reset acts on the GATE (flips fail→pass).
**Why an explicit eliminator:** "too late-stage to join and still shape the build" is a real disqualifier
the old blended score couldn't express cleanly — a big late-stage company scored well on revenue and
floated up. Making maturity a GATE lets it eliminate. **Why reset exists:** a mature company that just had
a leadership change / restructuring has effectively REOPENED its build-window — the maturity FAIL no
longer reflects reality, so reset flips it. **Why maturity stays factual (funding stage only):** funding
stage is reliable and verifiable; letting LLM "timing" judgments re-enter as a parallel signal would put
a fuzzy read into a gate (forbidden — gates must rest on reliable facts).

## A5. BACKGROUND FIT — gate-like/load-bearing → GRADIENT (errors recoverable)
**OLD:** fit/habit judgments were effectively load-bearing for the outcome, despite being the signal the
LLM most often misreads (it mislabeled Nourish, a daily-engagement company, as "periodic").
**NEW (LOCKED):** Background Fit is a GRADIENT, NOT a gate. An LLM misread LOWERS the score (recoverable,
visible, calibratable) instead of FLOORING a good company. The reliable B2B exclusion lives in the PATH
gate, never here.
**Why move it out of gate-territory:** you never want your LEAST-reliable signal to be an ELIMINATOR. Fit
is exactly that signal (the Nourish "periodic" mislabel). As a gradient, a misread costs a company a few
points (visible, fixable in calibration) instead of wrongly killing it. The reliable exclusion (is there
a consumer end-user) is handled by the PATH gate on the classifier — so nothing reliable is lost by
demoting fit to a gradient.

## A6. EVIDENCE CONFIDENCE — was a GATE → now a FLAG-and-rescore (^c0)
**OLD:** evidence confidence was used as a GATE (low confidence could eliminate).
**NEW:** evidence_confidence_score is a deterministic FLAG that (a) gates TIERS (P0 needs ≥60, P1 ≥55 — so
a thin figure can't reach top tiers on fabricated confidence) and (b) routes weak cases to human review —
but it doesn't silently eliminate a company. Same chain the research-layer thread verified in code
(candidate_priority.py:226/315; calibration flags priority.py:402; q4 hard-gate
structured_evidence.py:208). Carry-and-rate, never carry-and-filter.
**Why flag-not-gate:** low confidence means WE don't know yet, not that the company is bad — eliminating on
it would throw away companies for OUR research gaps (the exact Rule-8 error). Flagging keeps the company
in play, caps how high it can rank on thin evidence, and routes it to the human who can actually resolve
it. This is the meeting point between the scoring model and the research-layer recovery work.

## A7. "HIGH REVENUE ≠ HEALTHY" — DELIBERATELY left to human review (new explicit stance)
**NEW (LOCKED):** the model does NOT try to catch the high-revenue-but-secretly-dying company (high burn,
churn, bad unit economics — e.g. Truepill scored "well" on revenue while failing). That judgment is too
nuanced for a gate (a gate must not rest on a fragile read). The model is a HIGH-RECALL FILTER that
surfaces the right ~10–15 companies; the operator deep-researches every P0/P1 manually and ranks down
under-the-surface problems.
**Why deliberately NOT modeled:** over-engineering a gate to catch "looks healthy but isn't" makes the
gate fragile for a job the human does better with a few hours of deep research. The model's job is RECALL
(surface the right shortlist with honest confidence ratings); the human provides PRECISION on the
shortlist. This is WHY the research-layer recovery work matters — it feeds the human the best evidence
with confidence ratings, rather than pretending the model is the final arbiter.

## A8. PRIORITY OUTPUT — interim bridge → real (and still un-wired)
**OLD/INTERIM:** the engine ran as a V4.2-interim "capability bridge" (capability-fit == role_fit) and was
INERT (did not write `final_priority_level`); false "Human Reviewed" labeling existed.
**NEW:** real capability-fit (A1/A2/A3 rubric) replaces the bridge; `final_priority_level` gets populated
by Commit 5 (still un-built; RE-GATED behind the second/recovery regen — calibrating on the untrustworthy
V4.2 master would bake in wrong thresholds). Thresholds are PLACEHOLDERS to be CALIBRATED against the 55
on trustworthy data, never guessed.

## What did NOT change (carried, not diffed)
- The NORTH STAR: two-gate human-in-the-loop autonomous flow; inside an autonomous segment, surface at
  the next gate (flag-for-review), never rely on a human noticing mid-flow.
- Rule 7 (LLM gathers evidence; deterministic rules decide; evidence persists as columns).
- Rule 8 (absence is an upper bound on non-existence, not a measurement, until a live test discriminates).
- The roster (the 55) and canonical test cases (ZOE = reset; Function = maturity/commercial;
  Nourish = the "periodic" mislabel regression; OpenEvidence = the B2B classifier regression).
- Calibrate against trusted data only; do NOT hand-edit the master.

---

# §B — LOCKED BUILDABLE DETAIL (the "what" Claude Code implements)

> Everything in §B is the buildable form of §A. Where a number is a calibration knob, it's marked here
> AND in §C. Stable structure with a tunable number = build the mechanism, expose the knob.

## B0. ARCHITECTURAL INVARIANTS (do not violate)
- **Rule 7:** LLM gathers EVIDENCE; deterministic rules DECIDE. Evidence persists as columns
  (recomputable without re-research).
- **Each fact enters the model EXACTLY ONCE** — no double-count across gate / gradient / modifier.
  Enforced instances (B1).
- Gates use the most reliable signals (errors unrecoverable → only reliable facts may gate). Fuzzy
  judgment lives in gradients (errors only LOWER a score). **Never weaken a gate to make something pass.**
- Load-bearing / LLM-facing changes ship as a reviewed change — never self-merged.

## B1. THE NO-DOUBLE-COUNT INVARIANT — enforced instances
This is the invariant A1 describes, made concrete. Each must hold in the build:
- **Growth is read ONCE:** the PATH gate floors only on the PRESENCE/absence of a growth signal (loose
  "alive" check); the STRENGTH of growth is scored only in PMF. Growth strength must NOT influence the
  gate. (This is why growth-in-the-gate was rejected — see B3.)
- **Reset vs Strain are separated:** RESET acts on the GATE (flips a maturity fail→pass). STRAIN acts on
  the RANK (a small capped bump). They are cousins (both turnaround-related) deliberately separated so the
  SAME turnaround event cannot count twice. Build guard: a single org event that feeds reset must not ALSO
  feed strain in a way that double-weights it (the Slice 3.7 forward-note: ensure A2-strain and reset
  aren't double-weighted when both feed a combined priority signal).
- **Maturity is FACTUAL only** (funding stage); LLM "timing" judgments must not re-enter as a parallel
  signal.

## B2. BUSINESS-MODEL CLASSIFIER (Item #1 — the linchpin)
- LLM extracts: `who_uses` (consumer|professional), `who_pays` (consumer|institution|mixed), plus
  `who_uses_basis`, `who_pays_basis`, `who_uses_confidence` (high|low). LLM does NOT emit the label.
- **Deterministic mapper:**
  ```
  if who_uses == "professional":          return "B2B"     # FLOOR (PATH Test A fail), regardless of who_pays
  if who_pays == "consumer":              return "B2C"
  if who_pays in ("institution","mixed"): return "B2B2C"
  ```
- `who_uses == professional` floors to B2B REGARDLESS of who_pays (the OpenEvidence fix — a professional-
  operated product can't be rescued by who-pays).
- **B2B FLOOR — MAINTAINED HUMAN-LOCKED LIST (authoritative; takes precedence over the classifier).** The
  B2B floor is a maintained list of behind-the-scenes professional/enablement products that must NEVER
  enter scoring. It is **human-locked, not classifier-emitted**: for any company on this list,
  `business_model` is FORCED to `B2B` regardless of the classifier's output. Rationale: the floor is
  gate-critical (a floor company wrongly admitted to scoring is the worst gate error) and the classifier
  cannot reliably hold the provider-tool / hospital-at-home-enablement vs own-care-team boundary
  (medically home oscillated across three tuning rounds). The classifier is therefore NOT expected to emit
  the floor, and a classifier floor-miss on a listed company is a **NON-FAILURE by design**.
  - **The locked floor (6):** `openevidence`, `cohere health`, `zus health`, `om1`, `medically home`, `linus health`.
  - **Maintenance:** adding/removing a floor company is a **doc-first edit to THIS list** (human judgment),
    NOT a classifier change. The classifier still runs on all companies and still emits B2B via the mapper
    when it reads `who_uses=professional`; the locked list is an OVERRIDE that guarantees these 6 are B2B
    even if the classifier reads them consumer.
- `who_pays == mixed` with consumer user → B2B2C (a real institutional channel exists; cash-pay strength
  surfaces later in PMF, not here).
- **`who_uses_confidence == low` → set `business_model_needs_review = True`, route to human gate (flag,
  don't gate).** Expected to fire ~never on the current 55.
- **Frequency firewall (in the prompt):** usage frequency is IRRELEVANT to who_uses (daily-using clinician
  = still professional; occasional-using patient = still consumer).
- **Persisted columns (Rule 7):** who_uses, who_uses_basis, who_pays, who_pays_basis, who_uses_confidence,
  and the derived business_model (written by the mapper).
- **Replaces** old `business_model_type` (revenue-mechanism axis) as the PATH signal. Keep the old field
  only if other code reads it; it is NO LONGER the gate signal.
- **REGRESSION FIXTURE — the locked 55 (v1.3 truth; `business_model_classifier_fixture.md`, commit
  `72cc199`, is the AUTHORITATIVE regression target — this is the summary):** B2B-floor **6** / B2C **8** /
  B2B2C **41** = 55 (re-run target with `firefly health` deferred: **6/8/40 = 54**); `needs_review`
  expected **0** (>1–2 ⇒ prompt logic is off). NOT the v1.2-era 7/11/37.
  Canonical asserts (**7**): openevidence→B2B (was mislabeled B2B2C); nourish→B2B2C; zoe→B2C;
  medically-home→B2B; headway→B2B2C; rula→B2B2C; grow-therapy→B2B2C. (Dropped in v1.3: `angle-health→B2B`
  and `outcomes4me→B2C` — both reclassified **B2B2C**.)
  - **B2B-floor (6, = the human-locked list above):** openevidence, cohere health, zus health, om1,
    medically home, linus health. (`angle health` left the floor in v1.3: member login = consumer uses
    Angle's own product → B2B2C.)
  - Full per-bucket lists live in `business_model_classifier_fixture.md` (the locked source).
  - **Spike classifier overrides (documented; scored via locked-fixture truth, NOT a fixture change):** the
    spike classifier self-classifies 50/54; four are scored from locked truth — `medically home`→B2B (now
    covered by the human-locked floor above), `noom med`→B2C, `signos`→B2C (minor employer-page `who_pays`
    over-read as mixed), `counsel health`→B2B2C (evidence-thin input gap, Rule 8). **HARDENING flags:**
    (a) provider-tool / hospital-at-home vs own-care-team `who_uses` — handled in the spike by the
    human-locked floor, permanent solution TBD; (b) minor-channel `who_pays` (single-proof-point employer
    page over-reading as mixed) — tighten in hardening.
- **Classifier PROMPT wording is STAGED** — live Colab test vs this fixture before final-merge. Mapper +
  fixture are LOCKED.

## B3. PATH-TO-SCALE GATE (Item #2) — runs on classifier output; two sequential tests
**Test A — is there a consumer end-user? (deterministic)**
```
# Apply the B2B floor list FIRST (§B2 human-locked list): if company in LOCKED_B2B_FLOOR,
#   business_model := "B2B" (override the classifier).
if business_model == "B2B":  GATE_FAIL     # no consumer end-user (locked-floor companies fail here by the override)
else:                        proceed to Test B   # B2C and B2B2C both have a consumer user
```
**Test B — is the engine viable? (TWO-TIER, loose "engine alive" floor only)**
```
# B2C path
if business_model == "B2C":
    alive = has_any_revenue(c) or has_meaningful_user_scale(c) or has_positive_growth_signal(c)
    return GATE_PASS if alive else GATE_FAIL
# B2B2C path
if business_model == "B2B2C":
    return GATE_PASS if has_real_institutional_channel(c) else GATE_FAIL
```
- **Gate job = loose floor only.** It floors ONLY the genuinely dead (no revenue AND no meaningful user/
  customer scale AND no growth signal). Engine STRENGTH is NOT judged here — that's PMF's job (this is the
  no-double-count invariant, B1). **Do not put growth-strength in the gate** — doing so would floor ~45
  companies on missing growth data (the reason growth-in-gate was rejected).
- `has_real_institutional_channel` = a REAL durable channel (named customers / covered lives / scaled
  adoption), NOT pilots/positioning. **Do not change this logic (^c4 says it's accurate).** Refining the
  exact "line" is deferred.
- **No-revenue fallback (^c10):** a B2C company with no revenue figure STILL PASSES if user-scale or
  growth evidence exists. Missing revenue ≠ dead. The missing-data audit discriminates `recoverable` vs
  `genuinely-absent` BEFORE any company is floored for absence.
- **`payer_institutional` SCOPE FIX (verified, parked for this gate):** the field is named for PAYER
  reimbursement, but `has_real_institutional_channel` needs "ANY real institutional/B2B2C channel."
  Function Health proves the gap — real EMPLOYER-DIRECT channel ("Function for Work"), but insurance-free,
  so a payer-only field scores it "no institutional channel" and mis-gates it. **When building Test B,
  the institutional-channel check MUST cover employer-direct, not just payer-reimbursed.** (Verified live.)
- **^c3 OPEN QUESTION (not yet decided — see §C PLACEHOLDER):** the B2C unit-economics / viable-engine
  LINE (the "$2M-equivalent" threshold). Instinct: use revenue GROWTH / SensorTower app-store revenue as
  the signal. Test B's STRUCTURE is stable; this specific LINE is open.

## B4. AGENCY GATE (Item #3) — deterministic from funding_stage + ipo_status, with reset
```
Series A / B          -> early-growth -> PASS
Series C (early)      -> scale-up     -> PASS
Series C (late)       -> scale-up     -> PASS (okay; see late-stage dial)
Series D+             -> late-stage   -> FAIL unless reset fired
Public / pre-IPO      -> mature       -> FAIL unless reset fired
Seed / pre-seed       -> too-early    -> FAIL (no reset rescue)
```
- **STAGE ASSIGNMENT (LOCKED v1.10) — how `funding_stage` is determined.** Load-bearing for BOTH this gate
  AND the §B6 Scale A/B stage rows; the corrected v1.8 scales made it score-critical (a B↔C mislabel swings
  arr_level 2–5 pts).
  - **Stage = the company's most-recent CLOSED, priced equity round** (seed / A / B / C / D–E / pre-IPO–
    public), as evidenced by a **dated announcement of a completed raise** in `funding_finding`.
  - **A new round advances the stage ONLY when it is DESIGNATED a new series (v1.10).** A closed, priced
    venture round raised under the **SAME existing series does NOT advance** the stage — the series letter
    moves only on a round explicitly designated the next series (e.g. an announced/closed "Series C").
    Additional capital under the current series — a same-series venture round, extension, top-up,
    internal/insider round, bridge, SAFE, convertible, or debt — keeps the stage at the last DESIGNATED
    series, even when closed + priced + sizable. (signos: Series B + a later $20M venture round = still
    Series B. bicycle: Series B + later funding with no designated Series C = still Series B.) When a later
    round's series designation is genuinely unstated in the evidence, **default to the last CONFIRMED
    designated series and set `stage_confidence = low`** — do NOT promote on an undesignated round.
  - **Announced-but-not-closed / rumored / "in talks" / extension / bridge / SAFE / convertible / debt does
    NOT advance the stage** — fall back to the last CLOSED priced round.
  - **Date-stamp the determination:** record the round + its date. If the most-recent closed round is
    ambiguous in the evidence, set `stage_confidence = low` and FLAG for review — do NOT guess (Rule 8).
  - **Revenue scale does NOT override the funding label.** A high-revenue Series-C is still Series-C (Rula:
    ~$471M revenue, Series-C-funded). A revenue/stage mismatch is a SIGNAL to double-check the label is
    CURRENT (did a newer round close?), NOT a license to relabel by revenue — only the EVIDENCE of a newer
    closed round moves the stage, never the revenue magnitude.
- **RESET (ZOE-validated; SHARPENED v1.5):** fires on a qualifying event — genuine leadership change,
  founder transition (clean handoff), post-failure rebuild, restructuring/layoffs, or a declared-
  transformation that is NOT a relabeled pivot/IPO-prep — creating a forward-looking high-agency opening.
  Reset flips a maturity-FAIL (D+, public/pre-IPO) to PASS. Reset does NOT rescue seed/pre-seed (too-early
  ≠ reopened window). **Strategic-pivot, M&A-integration, AND IPO-prep NEVER fire.** Three sharpenings
  (v1.5 — Pass-1 found the emitter over-fired on D+ via each; the test reads the event's SUBSTANCE +
  CONFIDENCE, never the synthesis's label):
  - **Substance over label (sword):** an event whose substance is a business-model / pricing /
    product-strategy change is a **strategic-pivot and NEVER fires, even if labeled "declared-
    transformation."** (Sword's "Outcome Pricing" + "Sword Intelligence evolution" — both relabeled
    pivots — is the regression case.)
  - **IPO-prep is NON-QUALIFYING (oura):** IPO preparation, an S-1 / draft registration statement, or
    public-market-readiness is **not** a reopened window — it is a mature-trajectory event, the opposite of
    a reset. It joins strategic-pivot + M&A-integration on the NEVER-fire list. (Oura's confidential S-1.)
  - **Confidence bar — "unclear" does not fire (noom):** a reset fires ONLY on a CLEARLY qualifying
    opening. An event the synthesis self-assesses `unclear` / low-confidence does NOT fire, and **N unclear
    events do NOT sum to a fire.** A routine growth-support exec addition (e.g. adding a CMO "to support
    expansion") is a growth move, not a reopening. (Noom — a partial founder reconfig + a growth-support
    exec expansion — is the regression case.)
- **Reset mechanism (Rule-7):** search GATHERS events; synthesis EMITS the canonical reset_events (SINGLE
  emitter); the deterministic rule DECIDES firing. Synthesis must NOT re-derive/override the opening.
  Multi-event: evaluate each event's opening SEPARATELY so a loud pivot can't bury a co-occurring
  restructuring (the ZOE case).
- **Maturity is FACTUAL only** (funding stage) — no LLM timing judgments as a parallel signal.
- **OPEN DIAL — late-Series-C / late-stage treatment:** clean pass vs soft pass that also lowers the final
  score. Build as CLEAN PASS; expose a flag so calibration can switch it. (§C OPEN-DIAL.)

## B5. BACKGROUND FIT GRADIENT (1–10) (Item #4) — LOCKED (v1.7; wording validated 2026-06-29)
- A GRADIENT, not a gate. **Precondition:** `who_uses == consumer` (reuse the classifier field; every
  gate-passed company meets it — `professional` was floored at PATH Test A). The gradient then scores HOW
  CLOSE the consumer-habit model is to the high-frequency "mobile-games loop." Errors are recoverable
  (re-runnable per company). It emits `background_fit` (int 1–10) AND a separate `data_feedback_loop`
  ("yes"/"no") flag, so the top-of-scale amplifier is visible per company.
- **Scale (locked):** a DATA-FEEDBACK LOOP (consumer sees their OWN body data → acts → sees it reflected →
  repeats) = top-of-scale amplifier (9–10, `data_feedback_loop="yes"`). A strong consumer-health company
  LACKING that loop still scores SOLIDLY (6–8), not floored. Genuine episodic/intermittent engagement =
  3–5. Near-zero recurring consumer surface = 1–2.
- **VALIDATED + LOCKED:** Colab-tested this session over the 37 gate-passed companies (37/37; the Nourish
  "periodic" mislabel regression PASSED — Nourish read as a strong consumer habit = **8**, not floored;
  the data-loop flag fired only on the metabolic/tracking loops: levels/signos/oova/9amhealth). The LITERAL
  locked prompt (a Python `str.format` template — note the doubled `{{ }}` for the emitted JSON braces):

```text
You score BACKGROUND FIT for a CONSUMER-facing health company: HOW CLOSE its consumer-engagement model is to the "mobile-games loop" -- habitual, high-frequency, retention-driven engagement the consumer keeps returning to on their own. This is a GRADIENT (1-10), not a pass/fail. (Precondition already met upstream: the consumer is the end-user of the company's OWN product/service.)

Output ONE JSON object and nothing else:
{{"background_fit": <integer 1-10>,
  "data_feedback_loop": "yes" or "no",
  "basis": "<one line describing the consumer's ACTUAL ongoing engagement>"}}

SCALE:
- 9-10 = a tight DATA-FEEDBACK LOOP: the consumer sees their OWN body/health data -> acts on it -> sees the result reflected back -> repeats. The habitual self-tracking loop (metabolic / CGM / wearable / biomarker / continuous activity or glucose tracking). This loop is the top-of-scale AMPLIFIER -> set data_feedback_loop = "yes".
- 6-8 = a STRONG consumer-habit model WITHOUT that tight data-loop: frequent, retention-driven engagement the consumer actively sustains (recurring coaching / therapy / care they personally show up for, a consumer app with real habitual use, an ongoing condition-management relationship). A strong consumer-health company that simply LACKS the data-feedback loop STILL SCORES SOLIDLY HERE -- do NOT floor it merely for lacking the loop.
- 3-5 = a genuinely EPISODIC / intermittent consumer relationship: the consumer engages around a discrete need or event and then largely leaves, with little sustained habit.
- 1-2 = almost no recurring consumer-engagement surface.

DO NOT under-score (the "periodic" trap): judge the consumer's ACTUAL ongoing engagement with the company's OWN product/service. Care delivered through the company's employed clinicians/coaches, or paid for by an employer/health-plan, is STILL the consumer's own habit -- do not label it "periodic" for that reason. A serious or medically-driven condition is NOT automatically low-frequency: a daily nutrition program, an ongoing therapy relationship, or continuous condition management is HABITUAL even when the underlying need is medical. Score 3-5 ONLY when the engagement is genuinely one-off / intermittent.

Company: {company}
Evidence:
{evidence}
```

- **FUNCTION / low-frequency override note (audit trail — Rule 6).** The gradient DELIBERATELY scores
  low-frequency engagement low: a twice-a-year lab-testing product (e.g. **Function Health**, InsideTracker)
  scores ~4 even with elite PMF, because it is NOT the high-frequency loop. This is CORRECT and INTENDED —
  every 2×/year product must score the same, so the gradient is consistent. **Function Health is a known
  HUMAN-OVERRIDE CANDIDATE at review time:** Katelynd may manually relax Function's background-fit decision
  vector, justified by exceptional revenue strength + problem complexity (a unicorn exception). That is a
  REVIEW-TIME HUMAN OVERRIDE (Rule 6: human override beats the automated value), NOT a scoring-logic change.
  The gradient KEEPS scoring low-frequency low; recording this here makes the later Function override a
  documented exception rather than an apparent inconsistency. (`who_uses == consumer` precondition, the
  gradient structure, and errors-recoverable behavior were LOCKED before this; only the wording was STAGED,
  now LOCKED.)

## B6. PMF GRADIENT (1–10) (Item #5) — assembly LOCKED
```
pmf_raw = 0.4 * arr_level_score + 0.6 * growth_score     # 40/60 split is an OPEN DIAL
pmf     = round_even_bands(pmf_raw)                       # 8.4->8, 8.5->9
```
- **SCALE A — ARR-by-stage (LOCKED v1.8).** Representative ARR in $M at each score 1–10 (engine-shared —
  one table). Look up the company's ARR at its stage and interpolate (rule below). Replaces the prior §C
  PLACEHOLDER (and the spike's improvised `round(10·√(mag/ARR_BEST))` curve, which over-credited 2–4 pts).

| stage | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| seed | 0.10 | 0.178 | 0.316 | 0.562 | 1.0 | 1.4 | 1.9 | 2.6 | 3.6 | 5.0 |
| series-a | 5 | 6.6 | 8.7 | 11.4 | 15 | 19.1 | 24.3 | 30.9 | 39.3 | 50 |
| series-b | 15 | 20.3 | 27.4 | 37 | 50 | 54.9 | 60.3 | 66.3 | 72.8 | 80 |
| series-c | 30 | 38.3 | 49 | 62.6 | 80 | 104 | 136 | 177 | 230 | 300 |
| series-d-plus | 50 | 65.8 | 86.6 | 114 | 150 | 191 | 243 | 309 | 393 | 500 |
| public | 100 | 126 | 158 | 199 | 250 | 330 | 435 | 574 | 758 | 1000 |

  Stage map: "Series D/E" → `series-d-plus`; "Pre-IPO / Public" → `public`. Asserts: SerA $24M→7, $50M→10,
  $4M→1, $39.3M→9; every published point → its own index.

- **SCALE B — growth-rate by stage (LOCKED v1.8).** % YoY growth at each score 1–10. ENGINE-AGNOSTIC — ONE
  table for D2C + B2B2C (unlike ARR). score-1 cell = "< that %", score-10 = "> that %", interpolate between.
  Replaces the prior §C PLACEHOLDER (and the spike's improvised stage-blind % bands).

| stage | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| seed | 25 | 30 | 45 | 65 | 90 | 120 | 160 | 210 | 280 | 350 |
| series-a | 30 | 45 | 60 | 80 | 100 | 125 | 155 | 200 | 280 | 400 |
| series-b | 25 | 35 | 45 | 60 | 75 | 90 | 110 | 135 | 170 | 200 |
| series-c | 15 | 22 | 30 | 38 | 48 | 58 | 70 | 90 | 120 | 150 |
| public | 10 | 15 | 20 | 27 | 35 | 42 | 50 | 62 | 80 | 100 |

  Stage map (LOCKED): `series-d-plus` → reads the **public** row (no separate D/E growth row; late-stage =
  late-stage); seed/a/b/c map 1:1. **DESIGN INTENT:** the bar DECLINES across stages deliberately (law of
  large numbers — 100% YoY is a 5 at Series-A but a 10 at Pre-IPO); a mature company at "only" 50–60% may be
  a 7–8 FOR ITS STAGE — do NOT read raw % stage-blind. Asserts (NO acceleration): Function +450%/SerB→10,
  Fay +200%/SerB→10, Hinge +51%/public→7, Omada +53%/public→7, Maven +26%/D+(→public)→4. **TWO RESIDUAL
  ANCHORS UNDER INVESTIGATION** (not silently fixed): Rula +100%/SerC → base **8** vs spec-anchor 10; Cohere
  +20%/SerC → base **2** vs spec-anchor 3 (B2B-floored, ranking-moot, but a scale data point). Check the
  actual dated rates vs the round numbers; the Series-C row may warrant a look. Report, don't override.

- **INTERPOLATION RULE (LOCKED v1.8 — same for BOTH scales).** For value `v` at a stage with published
  points `p[1..10]`: if `v ≤ p[1]` → 1; if `v ≥ p[10]` → 10; else find the bracketing points `lo` (score s)
  and `hi` (score s+1) with `lo ≤ v ≤ hi`, then `score = round_half_up( s + ln(v/lo) / ln(hi/lo) )`, clamp
  1–10. GEOMETRIC because both ARR and growth scale multiplicatively; round-half-up (distinct from the
  `pmf` round-even step).

- **ACCELERATION — REMOVED + PARKED (v1.8, open question).** The prior +1/+2 acceleration bonus is REMOVED
  from scoring — it does NOT fire. Provenance was suspect (not a designed rule) and it was self-validating:
  the spec's "+1 accel" anchors (Hinge +51%/public, Omada +53%/public, Maven +26%/D+) are exactly the
  companies whose BASE Scale-B values (7/7/4) it inflated to the cited 8/8/5 — the bonus was baked into its
  own validation points. growth_score is now the BASE Scale-B value only. PARKED as an open question
  (revisit later whether a separate accelerating-at-scale metric is warranted — not deleted from history).
- **MISSING-DATA CAP (^c10):** when revenue/growth genuinely undisclosed after the recovery pass, fall
  back to subscriber/user-scale + funding context as a WEAKER proxy and CAP pmf at 7 (can't hit best-in-
  class on estimates alone). Cap MECHANISM stable; the value 7 is a dial.
- **GROWTH-EXTRACTION SCOPE (clarified v1.6 — the cap is for GENUINELY-ABSENT growth ONLY):** two
  present-but-non-standard growth forms MUST be SCORED, never routed to the cap as if undisclosed —
  (1) **zero-baseline:** a launch-from-zero trajectory ($0 → $N ARR) has an undefined %, so score it on the
  **absolute revenue magnitude reached × stage** ($0→$112M at Series-C is top-of-scale growth, not missing
  data); the magnitude→stage mapping is now **Scale A (LOCKED v1.8)** — the arr=growth collapse stays, only
  the underlying numbers change. (2) **DERIVED / third-party** figures
  (Sacra / Latka / Growjo / "DERIVED:") are real growth evidence and SCORE (a credible estimate is not
  "undisclosed"). The **§B6.1 FENCE is preserved**: growth_score is **revenue/$-growth only** — headcount /
  download / MAU / partner-count / funding growth AND non-$ COUNTS (covered-lives / patient / member counts)
  are SCALE, not growth, and must NOT feed growth_score. This is the extraction-layer twin of the
  Collaboration doc's web-search EXECUTION-VARIANCE root cause (absence ≠ measurement, one layer down — the
  growth data exists and was captured; the spike's parser under-extracted it). The spike's regex extractor
  is spike-grade (residual leaks/misses recorded in `spike_pass1_notes.md`); the permanent extractor is a
  hardening-phase job.
- **40/60 LEVEL:GROWTH split is an OPEN DIAL** — tune toward growth (35/65, 30/70) if big-but-slowing
  companies rank too high; toward level (45/55) if small-base spikes. Worked anchors: Function 10/10;
  Nutrisense 7→6 for decelerating; an "$80M-but-flat" hypothetical 6→5.
- **DEPENDENCY:** the growth half scores most of the roster only AFTER the research-layer growth recovery
  lands (37/55 lacked quantified growth pre-recovery). Build the assembly now; it scores fully once the
  recovery regen lands.

## B6.1. SECONDARY USER-SCALE SIGNALS — routing (LOCKED v1.2)
**Status: LOCKED (FRAMEWORK_VERSION v1.2).** Reserved as an OPEN slot in v1.1; locked here with the routing
below. The fence + the new field build red→green on the research branch citing v1.2 (doc-first).

**The problem this addresses:** non-revenue growth figures (headcount/employee growth,
download/install/MAU growth, partner/client-count growth, funding growth) are abundant on aggregators
(Growjo headcount, app-store downloads) and the LLM can mistake them for the revenue/paid-user growth
signal (live cases: Solace 304% EMPLOYEE growth and Midi "0→435 employees" surfaced as candidate growth
"rates"). Two design facts govern how they're handled:
- **They are REAL secondary signals, not noise** — they feed the §B3 no-revenue fallback (a B2C company
  with no revenue still passes Test B on user-scale) and the §B6 missing-data PMF proxy (user-scale +
  funding context, capped at 7). A turnaround operator also cares about speed-of-scale as a §B7 STRAIN
  structural signal. So they must be CAPTURED + CARRIED (carry-and-rate, never carry-and-filter) — NOT
  discarded.
- **But they must NEVER masquerade as revenue/paid-user growth** — they must NOT satisfy the
  `growth_rate_presence_check` and must NOT feed `growth_score` (the 60%-of-PMF signal). Letting "they're
  hiring fast" stand in for "revenue is growing fast" corrupts the heaviest signal in PMF. This is the
  inverse of the §A7 high-recall-filter stance: just as the model must not over-credit high revenue, it
  must not let user-scale proxies impersonate revenue traction.

**The LOCKED routing (v1.2) — code-grounded.** Each secondary signal is captured + carried in a specific
field and fenced out of growth-rate. Three categories already have homes; one needs a new field:
- **headcount / employee / speed-of-scale growth → existing A2 STRAIN** (`search_operating_characteristics`
  + the a2 synthesis already capture "headcount ~100→500 in ~6mo" as a §B7 structural signal).
- **partner / client-count growth → existing `institutional_distribution_signal`** (scale_signal_assessment).
- **funding growth → existing `funding_evidence`** (context-only; already structurally excluded from the
  commercial signal).
- **non-paying digital user-scale (total/registered/active users, MAU, downloads/installs) + its growth →
  NEW captured field `sponsored_user_scale`** (in `commercial_evidence` next to `paying_customer_count`,
  persisted via structured_evidence.py). The one genuine gap: `paying_customer_count` is paid-only,
  `growth_signal` is barred, and `scale_signal_assessment` holds assessments not raw counts — yet §B3
  `has_meaningful_user_scale` + the §B6 user-scale proxy are meant to read exactly this. `sponsored_user_scale`
  fills a gap the framework already assumes is filled (not scope creep).

**The bar (fixed):** every routed signal is captured + carried + tagged as the secondary signal it is;
NONE satisfies revenue presence; NONE feeds `growth_score`. A precision FENCE keeps headcount / non-paying
user / download / MAU / partner-count / funding growth OUT of `growth_rate_source_directed_prompt` and
`growth_rate_presence_check`, so `growth_signal` / `growth_score` stay revenue/paid-only.

**Enforcement is STRUCTURAL, not just instructional:** the bar holds because `revenue_presence_check` reads
the revenue union and `growth_score` reads `growth_signal` — neither reads `sponsored_user_scale` — so
misfiling into this field cannot reach revenue presence or growth_score without a deliberate, visible edit
to a consumer. A future change cannot quietly wire `sponsored_user_scale` into the score; it would have to
change what a consumer reads, which is a reviewable edit.

## B7. STRAIN + FLOOR + FINAL ASSEMBLY (Item #7) — LOCKED
```
final_score = background_fit + pmf + strain        # strain: 0..+2 (max LOCKED +2, calibrated 2026-06-29)
# FLOOR RULE (gates FIRST): floor-FAIL == NOT (background_fit > 4 AND pmf > 4) -> P3 regardless of FINAL.
#   The tiers below apply ONLY to floor-PASS companies.
# THRESHOLDS (LOCKED — calibrated 2026-06-29 vs the v1.10 spike distribution):
#   P0: FINAL >= 18   |   P1: 15-17   |   P2: 13-14   |   P3: < 13
```
- **LOCKED DIALS (calibrated 2026-06-29 — promoted from OPEN-DIAL/PLACEHOLDER; net: no dial changed the v1.10 distribution):**
  - **40/60 PMF level:growth split — KEPT** (near-inert on this roster; confirmed).
  - **STRAIN max — KEPT at +2.**
  - **No-quantified-rate growth — KEPT at 5** (deliberate neutral-mid: a company is NOT gated on growth alone;
    a strong-other-component company surfaces to human deep-dive — Rule 8, don't gate on absence of measurement).
  - **Small-base growth dampener — NONE (declined by design):** growth is growth; revenue scale is gated by
    PATH + the floor rule, NOT by penalizing the growth half (no double-count).
- **HUMAN DECISIONS (review-time, recorded for audit — Rule 6):**
  - **Function Health → P1 OVERRIDE.** By rule it is P3 (floor-FAIL: bg_fit=4 from 2×/yr lab cadence). Katelynd
    manually overrides to P1, flagged, justified by exceptional revenue strength + problem complexity (the
    unicorn exception established when §B5 locked). REVIEW-TIME human override, NOT a logic change — the gradient
    + floor rule stay correct; Function is a documented exception sitting above the rule.
  - **Angle + Oula → P3 (confirmed intended).** Both FINAL=14 (equal to the six P2 companies) but floor-FAIL
    (bg_fit=4: insurance-admin / episodic maternity). The floor rule deliberately separates EPISODIC from
    HABITUAL even at equal FINAL — this split is intended, not an artifact.
- **CALIBRATION CAVEAT (R1):** these thresholds + dials are calibrated against the SPIKE distribution and carry
  the R1 hardening caveat (`spike_pass1_notes.md`): if the hardened Phase-3 scorer's extraction/gate logic
  drifts from the spike's, the thresholds MUST be re-validated. SPIKE-PROVISIONAL until re-validated.
- **STRAIN is a GLOBAL-RANK modifier** — cannot move a company across a tier alone. Cousin of reset
  (reset acts on the GATE, strain on the RANK) — separated so the same event can't double-count (B1).
- **STRAIN evidence split (WORDING-LOCKED):** B1-structural vs B2-reported, with a STRICT bar on B2
  (multiple independent sources on the SAME breakdown; prefer Reddit/forums over Glassdoor; routine
  griping does NOT count; speed-of-scale e.g. 100→500 staff in 6mo is a strong STRUCTURAL signal,
  reported as evidence not verdict). Absence-is-a-finding default: default LOW unless strain clearly
  demonstrated. Strength-tagged (STRONG/MODERATE/WEAK) output.
- **Gate fail (either gate) → P3 floor, stop** (score not computed).
- **EVIDENCE CONFIDENCE = FLAG not gate:** low-confidence evidence routes to human review + rescore, does
  NOT floor. `who_uses_confidence == low` feeds this same route.

## B8. MISSING-REVENUE / GROWTH AUDIT (prerequisite to growth-recovery #6)
For each company missing revenue/growth, a TARGETED check classifies it `recoverable` (exists, research
missed) vs `genuinely-absent`. Output a table: company | missing field | recoverable? | best source |
est. effort — this DEFINES the recovery batch scope. (Method: B2C → SensorTower; B2B2C/B2B → press
releases, funding announcements, covered-lives counts.) Resolves ^c10's "is missing = absent?" before any
company is floored for absence. (This is the bridge to the research-layer thread, which is executing the
recovery.)

## B9. BUILD ORDER (scoring track — resumes AFTER the research layer + second regen)
1. Classifier (mapper LOCKED build-now; prompt STAGED — live Colab test vs the 55-fixture FIRST).
2. PATH gate (Test A + Test B two-tier + no-revenue fallback + the employer-direct scope fix).
3. AGENCY gate (maturity buckets + reset exception + D-fails).
4. BACKGROUND FIT gradient (STAGED rewording — A1/A3 to consumer-end-user; the Nourish regression).
5. PMF gradient + the stage-benchmark ARR/growth scales.
6. STRAIN modifier + FLOOR rule + final assembly → Commit 5 wires `final_priority_level`.
7. Score the 55 → calibrate thresholds (AFTER the second regen — trustworthy data; NEVER before).
8. Document final model + rationale in the repo.
**Sequencing bar:** research layer (all fields enabled) → SECOND run-once regen → THEN scoring builds +
calibrates. Calibration on pre-regen data is BARRED (^c10).

---

# §C — STABILITY MARKINGS (build/calibrate discipline)

> **WHERE THESE CLOSE (forward-pointer; no framework change).** The OPEN-DIAL knobs and PLACEHOLDER
> numbers below are RESOLVED in **Phase 2** of the regen tail — pressure-test THIS framework against the
> **Phase-1 research output**, then set thresholds against the validated framework (evidence-driven from
> real data, never guessed). A framework revision discovered there is a **doc-first FRAMEWORK_VERSION bump
> (v1.2 → v1.3)** — the SOT changes first, then code. The §C markings were never permanent ambiguity;
> Phase 2 is when they close. Calibration-on-pre-regen-data stays BARRED. Cross-ref:
> `PRE_REGEN_READINESS.md` §5 (the regen's three-phase tail). The STABLE items remain safe to build now.

**STABLE — locked as reference; safe to build against:**
- Gated-then-ranked architecture (3 stages; fact-enters-once). [A1/B0]
- The no-double-count invariant + enforced instances (growth gate-vs-PMF; reset-vs-strain). [B1]
- Classifier: who_uses/who_pays extraction, deterministic mapper, frequency firewall, Rule-7 split,
  needs_review routing. (PROMPT wording STAGED.) [B2]
- The locked 55-fixture counts + canonical asserts (regression target). [B2]
- AGENCY gate: maturity buckets, D+ fails-without-reset, reset rescues D+/public not seed/pre-seed. [B4]
- Reset mechanism: which events fire/never-fire, multi-event per-event eval, search-gathers/synthesis-
  emits single-emitter. [B4]
- PATH Test A (B2B floor). PATH Test B two-tier STRUCTURE (loose engine-alive floor; strength in PMF). [B3]
- No-revenue fallback rule (missing revenue ≠ dead). [B3]
- `payer_institutional` → employer-direct scope FIX (the fix is known + verified). [B3]
- Background Fit is a GRADIENT not a gate (errors recoverable). (A1/A3 rewording STAGED.) [A5/B5]
- Evidence-confidence FLAG-and-rescore + the deterministic tier-gate chain (P0≥60/P1≥55) + code
  locations. [A6/B7]
- High-recall-filter stance — model surfaces ~10–15; human deep-researches P0/P1. [A7]
- PMF STRUCTURE: stage-relative grading, the two scales, composite-of-level-and-growth, missing-data cap
  MECHANISM, acceleration-bonus MECHANISM, round-even banding. [A2/B6]
- STRAIN STRUCTURE: global-rank modifier, capped, can't move a tier alone; B1/B2 split + strict B2 bar. [B7]
- FLOOR rule: P0/P1 require BOTH gradients > 4. [B7]
- **Secondary user-scale signal ROUTING (LOCKED v1.2)** — three categories to existing homes
  (headcount→A2 strain, partner/client-count→`institutional_distribution_signal`, funding→`funding_evidence`),
  non-paying user-scale→new `sponsored_user_scale`; STRUCTURALLY barred from revenue presence + growth_score
  (no score-consumer reads `sponsored_user_scale`). [B6.1]
- North Star; Rule 7; Rule 8; carry-and-rate; calibrate-on-trusted-data-only.

**OPEN-DIAL — build the mechanism, EXPOSE the knob, do NOT treat the number as final:**
- PMF composite split **40% level / 60% growth** — tune 35/65, 30/70, or 45/55 per the anchors. [B6]
- Missing-data cap **value (≤7)** — cap mechanism stable; the 7 is a dial. [B6]
- Acceleration bonus **magnitude (+1/+2)** — mechanism stable, size is a dial. [B6]
- STRAIN **max bump (+2 vs +3)** — explicitly open. [B7]
- AGENCY **late-Series-C / late-stage** treatment — clean-pass vs soft-pass-that-lowers; build clean pass,
  expose a flag. [B4]
- Per-field recovery **N** (research-layer) — N=5 set for revenue/paying-count/growth; permanent per-field
  N is a later calibration. (Cross-ref only; lives in the research-layer docs.)

**PLACEHOLDER — committed for context but DO NOT BUILD/CALIBRATE AGAINST:**
- ~~**All P0/P1/P2/P3 THRESHOLD NUMBERS** (21–23 / 15–20 / 9–14 examples).~~ **✓ NOW CALIBRATED + LOCKED
  (§B7 v1.11, 2026-06-29)** against the second-regen v1.10 spike distribution: P0 ≥18 / P1 15-17 / P2 13-14 /
  P3 <13, floor-rule-gates-first. SPIKE-PROVISIONAL — re-validate against the hardened scorer (R1). [B7]
- ~~**The specific ARR-by-stage / growth-by-stage benchmark VALUES** inside the two PMF scales.~~ **✓ NOW
  COMMITTED + LOCKED (§B6 v1.8)** as Scale A + Scale B + the geometric interp rule. [B6]
- **^c3 — the B2C unit-economics / viable-engine LINE** (the "$2M-equivalent" threshold). Open question,
  not yet decided (instinct: revenue-growth / SensorTower as the signal). Test B's STRUCTURE is stable;
  this LINE is open. [B3]

---

# DISCIPLINE — how this doc stays the source of truth (read every time)
- **This doc changes FIRST.** Any scoring-logic decision locked in a design chat is written HERE before
  anything is built against it. FRAMEWORK_VERSION bumps on every change.
- **Doc-update-before-build, as its own commit.** Claude Code commits the doc change SEPARATELY from and
  PRIOR to any logic build that depends on it. The doc-commit IS the sync; the build references the
  committed doc.
- **Both sides cite the version.** Research-layer + scoring work reference "built against
  FRAMEWORK_VERSION vN." Output citing an old version is an instant staleness flag — a mismatch is VISIBLE
  instead of remembered.
- **Placeholders are load-bearing.** Never build or calibrate against a §C PLACEHOLDER. OPEN-DIALs get the
  mechanism built with the knob exposed, never the number hardcoded as final.
- **Nothing important lives only in chat.** If it's a locked decision and it's not in this doc, it isn't
  locked.
