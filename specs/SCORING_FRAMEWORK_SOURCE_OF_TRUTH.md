# Scoring & Priority Framework — SOURCE OF TRUTH

**FRAMEWORK_VERSION: v1.25 (2026-07-01)**
**Changelog:** v1.25 — §B6 GROWTH BAND-RULE REFINEMENT (the first v1.24 R1 ran clean — collapse gone, `grow` un-frozen 4→8 by the bg N=4 average → P0 — but surfaced TWO band-read errors: `pomelo` banded HIGH on covered-lives/member SCALE while revenue growth was undisclosed (a FENCE violation → wrong P0), and the first-cut "NEVER combine two sources" rule would have wrongly refused `equip`/`bicycle`, two genuinely fast-growing companies whose evidence is COMPLEMENTARY multi-source, not conflicting). TWO fixes, doc-first §B6, NO return of the derive machinery: (1) **BAND ON TRAJECTORY MAGNITUDE, complementary-multi allowed.** A band reads which side of the stage cutpoint the growth MAGNITUDE lands on — NOT a precise rate — so the hard same-source gate is the WRONG tool (it enforces a rate-precision the bands don't use). A band MAY rest on: a single-source stated rate; a single-source revenue series (≥2 same-source dated points); OR complementary multi-source revenue points (different years/sources, NO competing estimate for the same period) read as a trajectory magnitude (grew ~Nx over ~M years). The ONLY multi-source case to REFUSE is a genuine SAME-PERIOD conflict (contradictory figures for the same period) → fall to the most-credible single point / qualitative / UNKNOWN. The extractor RECORDS the figures + sources + the source mode (`single-source` / `complementary-multi` / `conflict`) for the review trail + future ledger. `derive_growth_from_figures` / `GROWTH_SOURCE_ALIASES` / the report-figures schema STAY REMOVED. (2) **FENCE — HARD.** A growth band may rest ONLY on revenue/$-growth evidence; if the only signal is a NON-revenue COUNT/SCALE (covered-lives / members / patients / users / downloads / headcount / partners) the band is UNKNOWN — never HIGH/SOLID on counts (§B6.1). The extractor reports the band's BASIS (`revenue-rate` / `revenue-trajectory` / `counts-scale` / `none`); a `counts-scale` / `none` basis is FORCED to UNKNOWN in CODE (§A gate-in-code — the mechanically-checkable fence the LLM failed goes in code, backstopping the prompt). Verify-by-name after build: `pomelo` (bands on a REVENUE series or drops to UNKNOWN — never on covered-lives), `equip`/`bicycle` (band on their legitimate complementary-multi trajectory), `grow` (HIGH + bg=8 → P0), and the v1.24 anchors (function/rula HIGH, hinge SOLID, maven SLOW, transcarent SOLID) still hold. Tally is an OUTPUT ratified by name, never forced. Doc-first §B6; code = band prompt (trajectory + fence + basis/source-mode) + a code fence backstop on the basis; the derive machinery does NOT return. v1.24 — GROWTH BAND-CLASSIFICATION REDESIGN + bg N=4-AVERAGE + WIDENED FLOOR FLAG (the v1.23 same-source DERIVE thesis was reframed as wrong: the research does not carry two same-source dated figures for most companies, so a DERIVE-from-figures growth read either refuses (→ neutral, distribution collapsed to P0=1 on the Fix-2 run) or grabs cross-source junk. STEP-0 conflict audit done first, all prior growth/pmf/bg patches classified). THREE changes, doc-first §B5/§B6/§B7: (1) **§B6 GROWTH = BAND CLASSIFICATION, not derivation.** The growth read now CLASSIFIES the company's growth into one of four bands — HIGH=9 / SOLID=6 / SLOW=3 / UNKNOWN=4 — with cutoffs ANCHORED to the LOCKED Scale B per-stage cutpoints (HIGH ≥ the stage's score-8 %-YoY column; SOLID = the score-5..7 band; SLOW ≤ score-4; no quantified rate → UNKNOWN=4, Rule-8 neutral-mid). Declining → SLOW=3 but the decline is RECORDED in the evidence trail (no separate 5th band — on this roster all 8 "decline" matches are false positives; a genuine decline still lands in the lowest band). The read reports `{growth_band, evidence}`, not figures. VALIDATED: the band score agrees with the retired Scale-B interpolation within 1pt on 15/16 anchors, within 2pt on 16/16 (mean |Δ| 0.94). **SUPERSEDED + REMOVED:** the same-source derive subsystem (`derive_growth_from_figures`, `GROWTH_SOURCE_ALIASES`, `_norm_growth_source`, `_year_or_none`, `_QUALITATIVE_GROWTH_SCORE`), the report-figures extractor schema, and the `PMF_MISSING_CAP` (§B6 cap@7 — dead once growth always yields a band). `PMF_NEUTRAL_HALF=4` KEPT but re-scoped to the ARR half only. The §B6.1 counts-are-scale-not-growth FENCE is KEPT. (2) **§B5 bg = MEAN of N=4 reads, then CACHED.** bg_fit is taken 4× at population, averaged, ROUNDED HALF-UP to an integer BEFORE the floor check, then cached (mean 4.5 → 5 → PASSES `> 4`; mean 4.4 → 4 → FAILS). This extends the v1.22 caching (4 passes taken ONCE, not per-score) to the one read that is still genuinely noisy — growth is now a stable band, reset/classifier are categorical, so bg is the sole averaging target. N=4 is a dial. (3) **§B7 FLOOR FLAG WIDENED** `floored_bg_near_threshold` → `floored_on_bg`: fires on ANY company floored SOLELY on bg (not gate-floored, not pmf; would floor-PASS if bg cleared), REMOVING the v1.23 `{3,4}` wobble window and RETIRING `BG_FLOOR_WOBBLE` for this flag (bg is now an N=4 average, not a single roll — "how far from the line" is no longer the right question; "the floor rests entirely on the one judgment read" is). The bg=None / READ-FAILED label stays DISTINCT. Doc-first §B5/§B6/§B7; code lands red→green (band-vs-ScaleB ±2 validation test + bg-average test); prompts changed → cache is stale → a FRESH full R1 run is required before any tally is ratifiable. v1.23 — TWO gate-in-code hardenings from the first caching R1's by-name verification (caching FREEZES a wrong read, so a mechanically-checkable rule the LLM fails goes in CODE). (1) §B6.1 SAME-SOURCE DERIVE now ENFORCED DETERMINISTICALLY: the prompt gate failed a 2nd time (`equip`: live extractor derived Latka-2021 + CB-Insights-2023 → bogus 7.8x → P1). The growth extractor now REPORTS figures ({value_usd_m, year, source, measure}); `derive_growth_from_figures` computes the rate in code ONLY from same-measure + same-source + time-order, with conservative source-alias normalization (unknown/ambiguous → DISTINCT → refuse; err toward refusing since a wrong derive inflates to P0/P1). equip cross-source → refused → qualitative → pmf 4 → **P2**. The prompt keeps the FENCE + report-figures (signed); the gate is the code's call. (2) §B7 `floored_bg_near_threshold` review flag: Katelynd deep-dives P0/P1 by hand (top errors self-correct), so the expensive error is a real prospect frozen-LOW in the un-reviewed P3 pile (`grow`, bg froze at 4). A company floored ONLY by a low bg in {3,4} (would pass if bg cleared, pmf>4, NOT gate-floored) is surfaced into the bounded `review_set` → consider a logged `--refresh`, never auto-un-floor. `BG_FLOOR_WOBBLE = 2` anchored to the observed pre-caching bg wobble (typical ±1, grow ±3). ALSO built this batch (from signed docs / build-acceptance): `DOCUMENTED_RESET_OVERRIDES` (§B4 v1.21, was signed-but-unbuilt — hinge/noom → no-fire, now in code); the floor label distinguishes bg READ-FAILED (None) from a low score; and `tally_r1` splits `review_set` (proximity+override+floored-but-close = bounded autonomy metric) from `floor_audit` (P3 rejects, on-demand). Doc-first §B6.1 + §B7; code lands with red→green. v1.22 — §B7 REPRODUCIBLE SCORING via PERSISTED READS (caching): RETIRE the N=5 stability mechanism (v1.20/v1.21), fix the read-noise at its SOURCE. GOAL is a reproducible PIPELINE, not a deterministic MODEL. The four scoring-path LLM reads (§B2 classifier, §B4 reset emitter, §B5 bg_fit, §B6 growth) are taken ONCE per company and PERSISTED (durable read-columns keyed by company + input-hash — the "gather once, derive freely" pattern, locked Rule 4/5); the scorer reads the persisted reads and never re-rolls → reproducible on ANY model; a read is re-taken only via an explicit `--refresh`. **temp-0 + seed was EVALUATED and REJECTED** (verified against current OpenAI docs): `gpt-5.4-mini` is a GPT-5-class reasoning model that REJECTS `temperature != 1` (400 error) and whose `seed` is best-effort, NOT a determinism contract — so model-level determinism is not viable; caching achieves reproducibility model-agnostically. The N=5 variance came ENTIRELY from RE-CALLING reads that were never persisted (confirmed: the checkpoint holds NO background_fit / who_uses / structured growth read; `run_r1` re-called all four live); caching removes the re-call → N=5 is moot. N=5 was a LATE downstream WORKAROUND (added for `season`'s bg_fit 5↔7); Commits 1–7 scored each company ONCE. RETIRE it (not left inert) + REPLACE with a `tier_review` PROXIMITY flag: a floor-PASS company whose FINAL is within **±1** of a boundary (FINAL ∈ {12,13,14,15,17,18}) is flagged for Gate-2 review — a REVIEW flag, NOT an auto-bump. The LLM STILL judges (asked ONCE, judgment frozen) — NOT a reversal of the LLM-reads decision. PROOF: score the roster TWICE off the persisted reads → BYTE-IDENTICAL by construction (checks nothing re-calls behind the scorer). MANDATORY read-correctness verification by name (caching FREEZES whatever it reads): noom/hinge (reset reads → don't fire) + equip (growth same-source gate → qualitative, not the 7.8x cross-estimator derive) + season (bg_fit stable) — if any read is WRONG, HARDEN that prompt (hard gate) + re-take, never revert to multi-run. Doc-first §B7; code = persist-the-reads cache + retire tier_stability + add the proximity flag in assembly. SUPERSEDES v1.21 MODE (single-run needs no resolution rule). v1.21 — §B7 STABILITY RESOLUTION: "highest observed" → MODAL tier (the R1 live run falsified the v1.20 err-UP rule). v1.20 resolved an unstable company to the HIGHEST tier seen across the N runs, on the assumption of FEW straddlers (only `season`). The live R1 run FALSIFIED that: broad live bg_fit/growth variance made **9** companies straddle, and "highest observed" applied broadly INVERTED the distribution (P0=7 vs target 4 — `affect`/`season` P3 in 4/5 runs resolved P2 off one outlier; `equip`/`hinge` P1 in 3/5 resolved P0). RULE NOW: UNSTABLE → assign the **MODAL** tier (most frequent across the N runs; a TIE resolves toward the HIGHER tier); the `tier_variance` flag STILL fires on ANY variance (high-recall surfacing preserved) — the assigned tier is the company's TYPICAL run, not its best-case run. Also RE-FRAMED the R1 target as an OUTPUT re-validated BY NAME, not a number to force (the spike's 4/6/6/38 was a frozen-score estimate; the six frozen-at-14 spike-P2 companies were coin-flips and scatter under live scoring). Doc-first §B7; the code change is `tier_stability` MAX→MODE. v1.20 — §B7 BOUNDARY-VARIANCE DETECTOR REWRITE (boundary-PROXIMITY → RUN-TO-RUN STABILITY; landed doc-first ahead of Commit-7 assembly). The v1.17/v1.19 detector fired on PROXIMITY ("any floor-PASS company whose FINAL is within ±2 of a boundary → bump higher"). A deterministic pre-Commit-7 check found that COLLAPSES P2: all six FINAL-14 companies (affect, equip, familywell, fay, foodsmart, jasper) sit within ±2 of the 15 boundary → all bump → P2=0, contradicting BOTH the R1 target (P2=6) and v1.17's own "only season changes" claim. Root cause: an intent-to-action mis-encoding — the "±2" was always run-to-run SCORE-MOVEMENT (a score that MOVES between runs), mis-attached to boundary-DISTANCE (a stable score that happens to sit near a line). v1.20 restores the intent as the actual mechanism: for each floor-PASS, non-overridden company, score it N=5 independent times (only the LLM-variable inputs — bg_fit; growth on R2 cases — re-run; deterministic parts are identical by construction); STABLE (same tier all 5) → that tier, no flag; UNSTABLE (tier differs on ANY run) → assign the HIGHEST tier observed + `tier_variance` flag (high-recall, §A7 — err UP). N=5 FIXED for R1. PRECEDENCE unchanged: floor → human-override → stability-detector, exactly one layer each. R1 (Commit 8) IS the stability machinery — it runs each eligible company 5×; target = "P0=4/P1=6/P2=6/P3=38 with `season` the one company whose tier MOVES (→ P1, flagged) and the six FINAL-14 STABLE at P2." Full AUDIT TRAIL recorded inline in §B7 so it is never "simplified" back to proximity. Doc-only; redefines the detector mechanism (season stays P1-flagged; the six FINAL-14 stop being wrongly bumped → restores P2=6). v1.19 — §B7 PRECEDENCE TIGHTENING (DETECTION-point clarity; no behavior change, landed doc-first ahead of Commit-7 assembly). The boundary-variance DETECTION line now states the detector's eligibility explicitly AT the detection point — "any floor-PASS company NOT resolved by a human override whose FINAL is within ±2 …" — so the override-vs-detector edge cannot be misread in isolation (a human-overridden company is TERMINAL per PRECEDENCE: its tier is the override's final word, never a boundary-straddler even within ±2; the detector does not re-touch it). The intent was already in the v1.17 PRECEDENCE bullet ("a human-overridden company is NOT double-handled by the detector"); v1.19 just makes it locally unambiguous after a fresh-reviewer misread. Precedence remains: floor → human override → boundary detector, exactly one layer each. Doc-only; no distribution change. v1.18 — §B6.1 SAME-SOURCE DERIVE GATE for the growth extractor (HARD 3-condition gate, not a caveat). A derived revenue-growth % is valid ONLY when the two dated figures are SAME-MEASURE (both annual revenue / both ARR), SAME-SOURCE (one company report OR one estimator's own dated series; two DIFFERENT estimators' single figures are not a series), and CORRECT-TIME-ORDER (earlier=baseline) — if any fails, NO derive (route to qualitative/absent). AUDIT TRAIL (why a hard gate): in Commit 5b this shipped as a soft sub-caveat and the model IGNORED it — it derived a bogus 102.5% for `pomelo` across two different estimators (Latka $127.6M 2025 + Growjo $63M 2026, chronology inverted), an R1-breaking junk rate. WORKED EXAMPLE: pomelo (two estimators → NO derive → qualitative) vs season (Latka's own $8M→$12.3M series → derive ≈ 53.7) — the gate cuts along the same-source line. Also recorded the CANONICAL growth-extractor evidence (growth_signal + revenue_or_arr + growth_finding, NOT the raw commercial_scale_finding — a Run-1 assembly bug flipped pomelo to a wrong absent) so Commit-7 assembly wires the right fields. Implementation lives in the staged prompt (the literal 3-condition checklist); §B6.1 records the PRINCIPLE + WHY. Doc-only; no distribution change (corrects an extractor bug toward the pinned reads). v1.17 — §B7 BOUNDARY-VARIANCE DETECTOR + `tier_variance` flag (built at assembly, Commit 7; sibling of the v1.15 floor_reason). The gradients carry ±2 LLM run-to-run variance (measured: the Commit-4 bg_fit live validation reproduced the frozen scores 37/37 within ±2), so a FINAL near a tier boundary can flip between runs (season P1/P2: bg_fit 7↔5 → FINAL 15↔13). RULE: any FLOOR-PASS company whose FINAL is within ±2 of a tier boundary (18 / 15 / 13) is a boundary-straddler → assign the HIGHER tier + a `tier_variance` review flag. Band N=±2 is FIXED (anchored to the measured variance, not an open dial). "Higher tier" is principled, not a convention: the model is a HIGH-RECALL FILTER (§A7) — a false-positive tier is cheap (human deep-research ranks it down), a false-negative is costly (a real prospect never gets the look). PRECEDENCE: floor rule → human overrides (Rule 6) → boundary detector (each company handled by exactly one layer). R1 inherits a CLEAN target: season is DEFINED as P1+flagged, so the variance becomes a documented expected-flag, not a parity threat. Surfaced on the Gate-2 card (floor-PASS → card). Doc-only; defines season=P1-flagged (no other distribution change). v1.16 — §B4 RESET EXEC-ADD OPENING = STRUCTURAL-ROLE rule (PROMOTED INTO THE PORT; supersedes the v1.15 stated-purpose ratification a live run FALSIFIED). The Commit-3a live emitter run scored 3/5: the stated-purpose boundary read grow's first-ever CFO `unclear` (grow wrongly EXCLUDED — P0 lost) and noom's "CMO to support expansion" `yes` (noom wrongly FIRED — un-floored). So the sharper structural-role rule is REQUIRED for R1 parity, not deferred (the v1.15 "deferred post-R1" decision is REVERSED — ratify-then-test was the error). New rule: an exec ADD to SUPPORT/SCALE existing growth → `unclear`; `yes` ONLY for a structural reset (new CEO replacing prior; founder stepping back; a FIRST-EVER / NEWLY-CREATED C-suite seat building a missing function). BLAST-RADIUS VERIFIED before promotion: a deterministic scan of the 10 D+/public AGENCY-floored companies found ZERO first-ever-seat hires (only grow hits → correctly un-floors), so the rule restores EXACT spike parity (grow FIRE, noom EXCLUDE, the other 9 unaffected) — no scoring distribution change. The two substance re-classifications (sword "evolution"→strategic-pivot; oura S-1→ipo-prep) already validated live. v1.15 — §B7 REVIEW-GRADE FLOOR-REASON requirement (the safety net that makes an imperfect gate safe: every floor is unrecoverable, so make every floor decision VISIBLE + OVERTURNABLE at Gate 2). Every floored company emits a stored `floor_reason` carrying its floor SOURCE + review-grade detail (B2B floor: human-locked-list vs classifier-professional-read; PATH Test B: what was looked for, to catch a Rule-8 missing-evidence floor; AGENCY: stage + the reset events + why-none-fired, to catch a reset MISS). Built at assembly (Commit 7, as a column — not bolted on); surfaced on the Gate-2 summary-table floor one-liner (`MASTER_REDESIGN_SPEC.md` §4 / `PHASE3_HARDENING_PLAN.md` §5) with the NEW requirement that the one-liner carry review-grade detail, not a bare floor type. Same surface-the-machine's-call principle as the §B2 floor + §B4 stage override. Also recorded the §B4 reset emitter STATED-PURPOSE boundary (growth-support `unclear` vs build-mandate `yes`) as RATIFIED-for-R1 with the structural-role sharper version DEFERRED post-R1 (next to the §B6 unknown-stage deferral). Doc-only; no scoring distribution change (the floor_reason is a review artifact; the boundary is ratified at spike parity). v1.14 — §B4 HUMAN-LOCKED STAGE OVERRIDE (the §B4 analogue of the §B2 B2B floor; landed doc-first ahead of the Commit-3b stage-rule build). `DOCUMENTED_STAGE_OVERRIDES = {"signos": "series-b", "bicycle health": "series-b"}`, authoritative over `funding_stage_from_rounds`. Surfaced by interrogating the live round data (Commit 3 scoping): the regen TYPED both companies' later rounds `series-c` (a higher letter than their prior `series-b`), which is indistinguishable from a real B→C advance by any deterministic rule on round `type` — the same-series-vs-new-series correction to `series-b` is HUMAN judgment NOT in the round record (signos $20M→$20M no step-up; bicycle no designated Series C). A lock (known-audited certainty) beats an LLM stage-designation emitter (probabilistic re-derivation, regress risk on a gate-critical input where a B↔C mislabel swings arr_level 2–5 pts) for two known companies — **no stage emitter planned** (LLM-facing co-drafts stay at two: 3a reset, 5b growth). The deterministic v1.10 discriminator is correct where the designation IS in the data: `rula` (2nd same-series series-c does not advance) + `9amhealth` (clean series-b; needs NO override — the audit misread it). So the Pass-2 "3 stage corrections" = **2 human-locked overrides + 1 deterministic-correct**. No scoring distribution change (these are the spike's STAGE_OVERRIDE values, ported as a maintained doc-first list). v1.13 — §B2 EVIDENCE-ONLY who_pays RULE (classifier-logic clarification; landed doc-first ahead of the Commit-1 classifier-prompt edit it governs). `who_pays` is decided ONLY on institutional payment channels MATERIALLY ESTABLISHED IN THE EVIDENCE — world-knowledge / background-reputation channels do not count; no material institutional channel evidenced → consumer cash-pay governs → `who_pays=consumer` (consistent with the `counsel` evidence-thin exception, Rule 8). This is Rule 7 (decide on gathered evidence) + Rule 8 (absence isn't filled in) applied to who_pays, and the principle behind the two §B2 who_pays hardening flags. Surfaced by the gate-B 7-case prompt-validation slice (2026-06-30): `oura` (zero institutional channel in its evidence) read B2B2C via a world-knowledge over-read; the evidence-confined read is `consumer`/B2C (its fixture truth). The staged classifier prompt gains a matching three-line MATERIALITY-BAR block (EVIDENCE-ONLY + FREE-TO-CONSUMER); mapper + fixture v1.3 UNCHANGED; no scoring distribution change (a who_pays over-read is a survivable recoverable miss, never a silent elimination — the gate-critical who_uses floor is held by the human-locked B2B list). v1.12 — PHASE-3 PRE-BUILD DOC EDITS (DOC-CLARIFICATION ONLY — no threshold/dial/distribution change; R1 parity preserved; landed doc-first before the Phase-3 build commits they gate, per `PHASE3_HARDENING_PLAN.md`). Three edits: (1) **§B6 PMF single-absent-half neutral = 4 — RATIFIED** from the spike (`spike_scoring_spine.py:178`): when exactly ONE PMF half is absent, the absent half is filled with neutral 4 before the 0.4/0.6 blend — this ratifies the behavior the §B7 thresholds were calibrated on (not a new value). (2) **§B6 unknown-stage PMF policy** — (a) RATIFY for R1: an unknown/undeterminable `funding_stage` scores PMF on the **series-b** row of both scales (`spike_scoring_spine.py:119,122`); never fires on the 54 (all clean stages), so parity-safe; (b) DEFERRED IMPROVEMENT (post-R1, NOT part of the port): once the §B4 v1.10 mapper can emit `unknown`+`stage_confidence=low`, route-to-human-review / cap (Rule 8) replaces the guessed series-b row — decided with eyes open after R1, never swapped in silently during the port. (3) **§B4 `ipo-prep` is a RECOGNIZED, non-qualifying (never-fire) reset event type — FAITHFUL-FIX to v1.5**: the deterministic `RESET_EVENT_TYPES` set must carry `ipo-prep` (alongside `strategic-pivot`/`ma-integration` on the never-fire list) so an emitted `ipo-prep` event is recognized + non-firing and is NOT routed to `reset_needs_review`; corrects oura's S-1 exclusion from review-flagged to clean (firing outcome UNCHANGED — still excluded; if it changed firing it would be a recalibration, not a faithful-fix). v1.11 — PASS-2 COMPLETE: §B7 THRESHOLDS + DIALS LOCKED (calibrated vs the v1.10 spike distribution). Replaced the §B7 PLACEHOLDER (P0=21-23…) with calibrated thresholds **P0 ≥18 / P1 15-17 / P2 13-14 / P3 <13**, and made the FLOOR-RULE-GATES-FIRST precedence explicit (a floor-FAIL is P3 regardless of FINAL; tiers apply only to floor-PASS). Promoted the dials to LOCKED: 40/60 split KEPT (near-inert), strain max KEPT +2, no-quantified-rate growth KEPT 5 (neutral-mid, Rule-8 don't-gate-on-absence), small-base growth dampener NONE-by-design (no double-count — revenue scale is gated by PATH + floor, not by penalizing growth). Net: no dial changed the v1.10 distribution. Recorded 2 review-time HUMAN DECISIONS (Rule 6): Function Health P3→**P1 OVERRIDE** (revenue+complexity unicorn exception, flagged, not a logic change); Angle + Oula **P3 by floor-rule** (FINAL=14 but floor-FAIL — episodic-vs-habitual split is intended at equal FINAL). Thresholds are SPIKE-PROVISIONAL and carry the R1 hardening caveat (re-validate if the hardened scorer drifts). Final tiered deliverable: `specs/SPIKE_FINAL_RANKING.md` (SPIKE OUTPUT — disposable, pending Phase-3 hardening). v1.10 — §B4 STAGE-ASSIGNMENT RULE sharpened with the DESIGNATED-SERIES discriminator. The STEP-0 audit surfaced a rule GAP (not 3 separate errors): v1.9 excluded extensions/bridges/SAFE/debt but did not cover a CLOSED, PRICED venture round under the SAME existing series, so the audit leaned toward advancing on any real closed round. Added: a new round advances the stage ONLY when DESIGNATED a new series; a same-series venture round / top-up / internal round / extension / bridge / SAFE / convertible / debt keeps the stage at the last DESIGNATED series (even if closed + priced + sizable); when a later round's designation is unstated, default to the last CONFIRMED designated series + stage_confidence=low (no promotion on an undesignated round). Resolves all 3 audit anomalies as same-cause: signos (Series B + later $20M venture round = still Series B → corrected series-c→series-b), bicycle (Series B + later funding, no designated Series C → corrected series-c→series-b), 9amhealth (Series B clean in the research output; the audit MISREAD it as a Series A extension → stays series-b as originally scored). v1.9 — §B4 STAGE-ASSIGNMENT RULE committed (LOCKED). The corrected v1.8 scales are strongly stage-driven (deliberate Series-B/C ARR overlap → a B↔C mislabel swings arr_level 2–5 pts), so `funding_stage` determination is now score-critical and must not be improvised. RULE: stage = the most-recent CLOSED, priced equity round (seed/A/B/C/D–E/pre-IPO–public) evidenced by a dated completed-raise announcement; announced-but-not-closed / rumored / extension / bridge / SAFE / convertible / debt does NOT advance the stage; date-stamp the determination and set stage_confidence=low + flag when ambiguous (no guessing, Rule 8); revenue scale does NOT override the funding label (a high-revenue Series-C stays Series-C — Rula — a mismatch is a signal to re-check currency, not a license to relabel by revenue). Pass-2 STEP-0 stage audit precedes any dial calibration. No scores changed by this rule alone (audit + corrections decided with Katelynd, then one re-run). v1.8 — §B6 PMF SCALES COMMITTED + ACCELERATION REMOVED. Both halves of PMF were on §C-PLACEHOLDER curves the spike improvised: ARR used `round(10·√(mag/ARR_BEST))` (over-credited 2–4 pts) and growth used stage-blind % bands. Replaced with the committed-intent **Scale A — ARR-by-stage** and **Scale B — growth-rate-by-stage** (engine-agnostic; declining bar across stages by design) tables, both LOCKED, plus a shared **geometric round-half-up INTERPOLATION RULE**. Stage maps: ARR "Series D/E"→series-d-plus, "Pre-IPO/Public"→public; growth series-d-plus→public row (no separate D/E growth row), seed/a/b/c 1:1. **ACCELERATION (+1/+2) REMOVED from scoring and PARKED** (open question) — provenance suspect + self-validating (its "+1 accel" anchors Hinge/Omada/Maven were exactly the base-7/7/4 companies it inflated to 8/8/5). growth_score is now the BASE Scale-B value only. Zero-baseline still scores the magnitude reached via Scale A (arr=growth collapse stays, numbers corrected); §B6.1 fence + missing-data cap@7 + derived-figure scoring UNCHANGED. Two residual anchors (Rula +100%/SerC base 8 vs anchor 10; Cohere +20%/SerC base 2 vs anchor 3) flagged for investigation, not overridden. v1.7 — §B5 BACKGROUND-FIT promoted STAGED → LOCKED: the bg_fit gradient wording was validated this session (Colab, 37/37 gate-passed; the Nourish "periodic"-mislabel regression PASSED at bg_fit=8; the data-feedback-loop flag fired only on the metabolic/tracking loops levels/signos/oova/9amhealth). The literal validated prompt is now embedded as the locked gradient prompt (data-feedback-loop top-of-scale amplifier 9–10; 6–8 floor-protection band for strong-habit-without-loop; bottom "do NOT under-score / periodic-trap" guard). Recorded the FUNCTION / low-frequency override note (audit trail, Rule 6): the gradient DELIBERATELY scores low-frequency engagement low (2×/year lab products → ~4) and this is CORRECT and intended; Function Health is a known REVIEW-TIME human-override candidate (revenue+complexity unicorn exception), NOT a scoring-logic change. Structure (gradient 1–10, errors recoverable, `who_uses==consumer` precondition, `data_feedback_loop` emitted as a separate flag) UNCHANGED. v1.6 — §B6 GROWTH-EXTRACTION SCOPE clarified (Pass-1 found the spike's PMF cap-squash was an EXTRACTION bug, not a data gap — 34/40 capped → 0): zero-baseline ($0→$N, scored on revenue-magnitude × stage, an OPEN DIAL) and DERIVED/third-party growth MUST be SCORED; the missing-data cap is ONLY for genuinely-absent revenue-growth; §B6.1 fence preserved (counts — covered-lives/patient/member — are scale, not growth). Non-normative Pass-1 records (reset regressions, emitter wording, extraction known-issue) live in `spike_pass1_notes.md`. v1.5 — §B4 RESET sharpened (Pass-1 found the emitter over-fired on Series-D+ via 3 patterns): (1) SUBSTANCE-over-label — a business-model/pricing/product-strategy change is a strategic-pivot and NEVER fires, even if labeled "declared-transformation" (sword); (2) IPO-prep / S-1 / public-market-readiness is NON-QUALIFYING, added to the NEVER-fire list (oura); (3) CONFIDENCE bar — an "unclear"/low-confidence event does NOT fire, and N unclear events do not sum to a fire (noom). Mapper + maturity buckets + Rule-7 single-emitter UNCHANGED. v1.4 — B2B floor is now a MAINTAINED HUMAN-LOCKED LIST (6: openevidence, cohere health, zus health, om1, medically home, linus health) that OVERRIDES the classifier (gate-critical; the classifier can't reliably hold the provider-tool / hospital-at-home-enablement vs own-care-team `who_uses` boundary — medically home oscillated across 3 tuning rounds). Mapper logic UNCHANGED; the floor is an override layer. Also synced the stale §B2 inline fixture block to v1.3 truth (6/8/41; angle→B2B2C; dropped angle/outcomes4me asserts). v1.3 — renamed `user_scale_signal` → `sponsored_user_scale` for clarity (institutionally-sponsored end-user reach; routing + structural bar unchanged). v1.2 — B6.1 LOCKED: secondary user-scale signal routing (headcount→A2 strain, partner/client-count→`institutional_distribution_signal`, funding→`funding_evidence`, non-paying user-scale→new `sponsored_user_scale`), with STRUCTURAL enforcement (no score-consumer reads `sponsored_user_scale`). v1.1 — added B6.1 (secondary user-scale signal routing) as a reserved OPEN slot. v1 — initial canonical capture.
**Status:** canonical. This is the ONE doc the design chats AND Claude Code point at for the scoring +
priority framework. If a decision about scoring logic isn't here, it isn't locked. When scoring logic
changes, it changes HERE first (version bumps), and Claude Code commits the doc-update BEFORE building
anything that depends on it (see DISCIPLINE, bottom).

> **DESTINATION — the master ledger (`MASTER_REDESIGN_SPEC.md`, RECONCILED v1).** This §B scoring system is
> the master's priority source: §B FINAL → §B7 threshold = `model_priority`, written **write-once** into the
> GATE-2 scoring-review ledger with a **per-entry `framework_version`** staleness stamp (no re-scoring; no
> drift flag). Human priority/taxonomy overrides live in the ledger's decision block (Rule 6); scores are
> never hand-edited (Rule 8). §B SUPERSEDES the `candidate_priority` V4.2 engine as the master's priority.

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
- **EVIDENCE-ONLY who_pays rule (v1.13 — the who_pays twin of the frequency firewall; Rule 7 + Rule 8).**
  `who_pays` is decided ONLY on payment channels **materially established in the company's EVIDENCE** —
  world-knowledge / background-reputation institutional channels do NOT count (the LLM must not import an
  employer/payer/enterprise channel it "knows" the company has but the evidence does not establish). When
  the evidence establishes **no material institutional channel**, the consumer cash-pay path governs →
  `who_pays = consumer` (consistent with the `counsel` evidence-thin exception, Rule 8: an evidenced
  under-read is an accepted input gap, not a fabricated channel). This is Rule 7 (decide on the gathered
  evidence) + Rule 8 (absence isn't something to fill in) applied to who_pays, and it is the principle behind
  the two §B2 who_pays HARDENING flags (minor-channel over-read; evidence-thin → decide on what's evidenced).
  Validated 2026-06-30 on `oura` — a consumer-hardware company whose evidence carries ZERO institutional
  channel; an evidence-confined read is `consumer` (B2C, its fixture truth); a world-knowledge read wrongly
  reaches B2B2C. (A who_pays over-read is in the SURVIVABLE zone — a recoverable tier-relevant miss, never a
  silent elimination; the gate-critical who_uses floor is held by the human-locked B2B list, not here.)
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
  - **HUMAN-LOCKED STAGE OVERRIDE (v1.14) — the §B4 analogue of the §B2 B2B floor; AUTHORITATIVE over the
    deterministic mapper.** `DOCUMENTED_STAGE_OVERRIDES = {"signos": "series-b", "bicycle health":
    "series-b"}`. **Why it's a lock, not a stand-in:** the regen research TYPED both companies' later rounds
    `series-c` (a higher letter than their prior `series-b`), which is **indistinguishable from a real B→C
    advance by any deterministic rule on round `type`** — the same-series-vs-new-series judgment that
    corrects them to `series-b` is HUMAN judgment NOT in the round record (signos: $20M→$20M, no step-up;
    bicycle: no designated Series C). This is structurally identical to the §B2 floor (the LLM cannot hold a
    gate-critical boundary, so a human locks the few exceptions) and is the CORRECT permanent pattern here,
    not a temporary patch: a lock is a KNOWN-audited certainty, whereas an LLM stage-designation emitter
    would re-derive that judgment probabilistically every run and could regress on a gate-critical input (a
    B↔C mislabel swings `arr_level` 2–5 pts via the §B6 scales). For TWO known companies, that trade is not
    worth an LLM surface (§A7 / floor reasoning). **No stage-designation emitter is planned.** The
    deterministic v1.10 discriminator (below) is correct for every case where the designation IS in the data
    — **`rula`** (a 2nd same-series `series-c` round correctly does NOT advance) and **`9amhealth`** (clean
    `series-b`; the audit MISREAD it but the data is right, so it needs **no override entry**). So the
    Pass-2 audit's "3 stage corrections" resolve as **2 human-locked overrides + 1 deterministic-correct**
    (a cleaner, more honest accounting). **MAINTENANCE:** adding/removing a stage override is a doc-first
    edit to THIS list (human judgment), not a code change.
  - **HUMAN-LOCKED RESET OVERRIDE (v1.21) — the reset analogue of the stage override; AUTHORITATIVE over the
    emitter's `creates_high_agency_opening` read.** `DOCUMENTED_RESET_OVERRIDES = {"hinge health": "no-fire",
    "noom med": "no-fire"}`, each carrying a reason. **Why:** the R1 live run showed the §B4 v1.16 substance
    emitter — itself an LLM — MISFIRES on its own textbook cases (LLM variance, the same class as bg_fit
    noise): (1) **`hinge health`** fired `restructuring-layoffs / yes` on a **public-company 10% layoff** whose
    own emitted basis hedges *"does not prove a broader re-foundation"* — a DEFENSIVE contraction (opening
    should be `no`, per v1.16's own "don't round up when uncertain"); (2) **`noom med`** fired
    `leadership-change / yes` on *"CMO … to support GLP-1 / health-plan expansion"* — the EXACT growth-support
    EXEC-ADD v1.16 scores `unclear`. Both wrongly un-floored a mature company to P0. These are documented human
    overrides (the same shape as the §B2 floor / stage override / Function P1-override — a human locks the few
    cases the LLM can't reliably hold), applied AFTER the emitter, forcing the reset to NOT fire → the company
    floors on its true maturity. **NOT a shim** (no basis-regex in `derive_reset_signal`; the emitter stays the
    substance-classifier) — a per-company human lock. **META (Decision-3 evidence, recorded not acted on):**
    that the emitter fumbles its own textbook cases is direct evidence the reset read is LLM-noisy, which folds
    into the deterministic-sampling question evaluated after R1. **MAINTENANCE:** adding/removing a reset
    override is a doc-first edit to THIS list.
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
    - **EXEC-ADD OPENING — STRUCTURAL-ROLE rule (v1.16; PROMOTED INTO THE PORT — supersedes the v1.15
      stated-purpose ratification, which a live run FALSIFIED).** The opening for an EXEC ADD is read by
      STRUCTURAL ROLE, not the evidence's growth phrasing: a senior exec ADDED to SUPPORT / DRIVE / SCALE an
      existing growth / expansion / partnerships / commercial motion (a CMO, CRO, similar growth hire) →
      `unclear`; `yes` ONLY for a CLEAR structural reset — a NEW CEO replacing the prior CEO, a founder
      stepping back for professional leadership, OR a FIRST-EVER / NEWLY-CREATED C-suite seat that stands up
      a function the company did not previously have (e.g. its FIRST CFO). The test: does it BUILD a missing
      operating function (→ `yes`) or STAFF an existing growth thrust (→ `unclear`)?
      - **WHY this replaced the v1.15 stated-purpose boundary (the falsification trail).** v1.15 RATIFIED a
        stated-purpose boundary "for R1" on the premise it reproduces the spike's `_GROWTH_SUPPORT` regex.
        The Commit-3a live emitter run (2026-06-30) **falsified that premise — 3/5**: grow's first-ever CFO
        read `unclear` (grow wrongly EXCLUDED — a P0 lost) and noom's "CMO to support expansion" read `yes`
        (noom wrongly FIRED — a floored company un-floored). The stated-purpose wording does NOT hold R1
        parity live, so the sharper structural-role rule is **REQUIRED for R1, not deferred** (the v1.15
        "deferred post-R1" decision is reversed — ratify-then-test was the error; this is test-then-ratify).
      - **BLAST-RADIUS VERIFIED before promotion (deterministic D+ scan, 2026-06-30).** The new "first-ever /
        newly-created C-suite seat → `yes`" trigger can only break parity for a company that is D+/public AND
        otherwise AGENCY-floored (Series A/B/C pass the gate regardless, so a reset there is inert). A scan of
        the 10 D+/public AGENCY-floored companies (headway, hinge, maven, midi, noom, omada, oura, sword,
        thyme, transcarent) found **ZERO first-ever-seat hires** — only `grow` hits (correctly un-floors to
        P0); `foodsmart` fires via the CEO handoff. So the rule **restores EXACT spike parity** (grow FIRE,
        noom EXCLUDE, the other 9 unaffected): **no scoring distribution change vs the spike deliverable.**
- **RECOGNIZED reset event-type vocabulary (v1.12 — emitter and deterministic rule MUST agree).** The
  recognized `event_type` vocabulary is the FIVE firing types (`leadership-change`, `founder-transition`,
  `post-failure-rebuild`, `restructuring-layoffs`, `declared-transformation`) PLUS the THREE non-qualifying
  NEVER-fire types (`strategic-pivot`, `ma-integration`, **`ipo-prep`**). **`ipo-prep` is a RECOGNIZED,
  non-qualifying type** — an event typed `ipo-prep` does NOT fire AND is NOT routed to `reset_needs_review`
  (it is a known never-fire type, exactly like `strategic-pivot`). The deterministic recognized-type set
  (`RESET_EVENT_TYPES`) and the never-fire set (`RESET_NEVER_FIRE`) must BOTH carry `ipo-prep` so the two
  sides agree; otherwise an emitted `ipo-prep` (oura's confidential S-1) falls through to a review flag
  instead of a clean exclude. FAITHFUL-FIX to v1.5 (which already lists IPO-prep on the never-fire list):
  this only makes the type RECOGNIZED so the firing OUTCOME (excluded) stays the same while the review flag
  clears. (Today `RESET_EVENT_TYPES` carries 7 types and omits `ipo-prep`; the Phase-3 build adds it to both
  sets — `RESET_FIREABLE_TYPES = RESET_EVENT_TYPES − RESET_NEVER_FIRE` then auto-excludes it.)
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
- **POPULATED as the MEAN of N=4 reads, then CACHED (v1.24 — noise reduction on the one noisy continuous
  read; EXTENDS v1.22 caching, does NOT reverse it).** `background_fit` is the ONE genuinely noisy continuous
  read (measured: `grow` wobbled 4↔8 run-to-run; the caching of a SINGLE sample froze `grow` at a low 4 and
  floored it). Growth is now a stable BAND (§B6 v1.24), and reset/classifier are categorical — so **bg is the
  ONLY read that gets averaging** (NOT a blanket return to multi-pass). At cache-population time bg is read
  **N = 4** times and the MEAN is cached; scoring then reads the ONE cached average → reproducible BY
  CONSTRUCTION (byte-identical re-score) AND noise-reduced (one bad roll can't swing it). This is NOT the
  retired N=5 (which RE-CALLED on every score — the variance source v1.22 fixed): the 4 passes run ONCE at
  population, not per re-score; caching REMAINS the reproducibility mechanism, averaging only improves the
  QUALITY of the cached value. `--refresh <company>` re-takes the 4-pass average for one company deliberately.
  **ROUNDING RULE (explicit):** the mean is ROUNDED HALF-UP to an integer BEFORE the floor check, so the floor
  gate `bg > 4` sees the rounded value (mean 4.5 → 5 → PASSES `> 4`; mean 4.4 → 4 → FAILS). **N = 4 is a dial.**
  **Cost:** ~4× the bg calls at POPULATION only (~54×4 once), not per re-score — noted so the run is not a
  surprise.
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
- **SINGLE-ABSENT-HALF NEUTRAL = 4 (LOCKED v1.12 — RATIFIED from the spike, `spike_scoring_spine.py:172–182`).**
  When exactly ONE PMF half is absent (only `arr_level_score` present, or only `growth_score` present), the
  ABSENT half is filled with the NEUTRAL value **4** before the 0.4/0.6 blend
  (spine:178: `al_e, g_e = (al if al is not None else 4), (g_final if g_final is not None else 4)`). This
  **ratifies the behavior the §B7 thresholds were calibrated against — it is not a new value.**
  - **Interaction with the missing-data cap@7 — stated explicitly so it need not be reverse-engineered (it
    does NOT double-penalize the same absence).** The cap keys off GROWTH absence ONLY —
    `cap = (g_final is None)` (spine:177) — applied as `if cap: val = min(val, 7)` (spine:181). When growth
    is absent, the growth half (60% weight) is filled with 4, so at the locked 40/60 split
    `pmf_raw ≤ 0.4·10 + 0.6·4 = 6.4 → val ≤ 6`; therefore **the cap@7 NEVER binds in the growth-absent path**
    (`min(≤6, 7)` is a no-op). The neutral-4 fill and the cap@7 are thus NOT a second deduction stacked on the
    first — the fill already bounds pmf below 7, and the cap is **redundant-but-harmless** given the fill (it
    is a stable mechanism + dial that would only bite if the 40/60 split were re-weighted hard toward level).
  - **Absent ARR half:** filled with 4, and `cap` is FALSE (it keys off growth, not ARR) → **no cap**
    (spine:177). Both halves absent → both filled 4 → `pmf_raw = 4.0 → val = 4` (cap True but inert).
- **UNKNOWN-STAGE PMF POLICY (v1.12) — (a) RATIFY for R1; (b) improvement DEFERRED post-R1.**
  - **(a) RATIFIED (the port reproduces this):** an `unknown` / undeterminable `funding_stage` scores PMF on
    the **series-b** row of BOTH scales (spike `spike_scoring_spine.py:119,122` — `_arr_stage` and
    `_growth_stage` fall back to `series-b`). On the 54 this path NEVER fires (every company has a clean
    stage), so ratifying it is **parity-safe** and the hardened scorer reproduces it for R1.
  - **(b) DEFERRED IMPROVEMENT (NOT part of the R1 port — a post-R1 decision, decided with eyes open):**
    once the §B4 v1.10 stage mapper can emit `unknown` + `stage_confidence=low` (the hardened
    designated-series discriminator), silently scoring a guessed series-b row is the wrong long-run
    behavior — the better policy is **route-to-human-review / cap (Rule 8)**. Do NOT swap (b) in during the
    port; it is a behavior change from the spike, filed as a deliberate improvement after R1, never folded
    into the port silently. The hardening / re-validation run uses (a).
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

- **GROWTH READ — BAND CLASSIFICATION (v1.24; SUPERSEDES Scale-B-interpolation-FOR-GROWTH + the entire v1.23
  report-figures / `derive_growth_from_figures` / same-source machinery).** The scoring thesis (a precise
  phase-relative YoY %) outran the research: only ~23/54 companies supply a clean stated rate; the rest were
  DERIVED (the pomelo/equip cross-source yo-yo) or DEFAULTED. So the growth READ changes from "produce a
  YoY %" to "CLASSIFY the growth evidence into a BAND for the stage" — a task the LLM holds reliably, where
  rate-derivation is the task it FAILED TWICE. **Four bands → `growth_score`:**
  - **HIGH = 9** — fast-growing for its stage: a stated rate AT/ABOVE the stage's Scale-B **score-8** cutpoint,
    OR "tripled / 3x / Nx", OR a clearly-high run-rate for stage.
  - **SOLID = 6** — real, credible growth: a stated rate in the stage's Scale-B **score-5..7** band, or clear
    scaling language.
  - **SLOW = 3** — modest / decelerating: evidence in the stage's Scale-B **score-2..4** band (or below).
  - **UNKNOWN = 4 (neutral) + REVIEW-FLAG** — no credible growth signal. NOT a silent low score: with the
    0.4/0.6 blend and a present ARR half, pmf stays recoverable (UNKNOWN does NOT auto-floor); it is FLAGGED
    for review (honest-absence, never fabricated).
  - **CUTOFFS ARE THE LOCKED SCALE B (anchor, not interpolated):** band boundaries are read from the stage's
    Scale B row — HIGH ≥ the score-8 column; SOLID = score-5..7; SLOW ≤ score-4 (series-d-plus → public row,
    per the existing stage map). This PRESERVES the phase-relative intent (a Series-A at 40% is unremarkable;
    a public co at 40% is excellent) WITHOUT re-inventing thresholds: Scale B stays LOCKED, but it now sets 4
    band cutpoints instead of a per-company interpolation. **Scale-B interpolation is RETAINED ONLY for Scale
    A (the ARR half) via `scale_interp`.**
  - **CLASSIFICATION ON TRAJECTORY MAGNITUDE, not rate-derivation (v1.25 — REFINED; the first v1.24 R1
    surfaced that "single-source only" was the WRONG fence).** The extractor BANDS a company's growth; it
    never computes a PRECISE RATE. But the first-cut v1.24 rule ("NEVER combine two DIFFERENT sources") was
    wrong: it would refuse `equip` ($4.5M-2021 Latka + $35M-2023 CB-Insights) and `bicycle` ($10M-2021
    CB-Insights + $81M-2023 GetLatka) — two genuinely fast-growing companies — for having TWO corroborating
    sources instead of one. That data is COMPLEMENTARY (different YEARS, different shops, NO competing estimate
    for the same period): it sketches a TRAJECTORY whose ORDER OF MAGNITUDE (grew ~Nx over ~M years) is
    unambiguous even when the exact multiple is not. Because the band reads which side of the stage cutpoint
    the magnitude lands on — NOT the precise rate — complementary-multi is SAFE, and two shops both showing
    several-fold growth is MORE credible, not less. **A band MAY rest on:** (a) a single-source stated rate;
    (b) a single-source revenue series (same source, ≥2 dated points); or (c) COMPLEMENTARY multi-source
    revenue points (different years/sources, no conflicting estimate for the same period) read as a TRAJECTORY
    MAGNITUDE. **The ONLY multi-source case to REFUSE:** two sources giving CONTRADICTORY figures for the SAME
    period (a genuine conflict) — then do NOT manufacture a rate; fall to the most-credible single point /
    qualitative / UNKNOWN. (Rare here, and DISTINCT from "different years, different shops," which is fine.)
    This is a BAND-RULE refinement, **NOT a return of the derive machinery** — `derive_growth_from_figures` /
    `GROWTH_SOURCE_ALIASES` / the report-figures schema STAY REMOVED: the hard same-source gate is the WRONG
    tool for banding (it enforces a rate-precision the bands do not use, discarding real signal to avoid it).
    The extractor RECORDS, per company, the figures + sources + the **source mode** (`single-source` /
    `complementary-multi` / `conflict`) for the floor_reason / review trail (and the future ledger).
  - **FENCE — HARD (v1.25; the real bug the first R1 exposed — `pomelo`).** A growth band may rest ONLY on
    REVENUE / $-growth evidence. If the ONLY growth signal is a NON-revenue COUNT/SCALE (covered-lives,
    members, patients, users, downloads, headcount, partners), the band is **UNKNOWN — never HIGH/SOLID on
    counts** (§B6.1). `pomelo` banded HIGH on "covered-lives / member scale expansion" while admitting revenue
    growth was not cleanly disclosed — the fence violation that inflated it to P0. The extractor reports the
    band's **basis** (`revenue-rate` / `revenue-trajectory` / `counts-scale` / `none`), and a self-reported
    `counts-scale` / `none` basis is FORCED to UNKNOWN **in code** — the mechanically-checkable fence goes in
    code (§A gate-in-code), a deterministic backstop to the prompt rule. (`pomelo` may still have a
    single-source Latka REVENUE series — if THAT is what it bands on, it may band on it; it may NEVER band on
    covered-lives. The R1 verify confirms which it used.)
  - **DECLINING → SLOW (3), RECORDED not banded separately:** the research shows ZERO genuine revenue
    decliners (all 8 "decline" hits are the word "contract" / "declined to disclose", not shrinking revenue),
    so a 5th DECLINING band would fire on nothing (overdesign). Genuine decline collapses to SLOW=3, but the
    extractor RECORDS "declining" in the evidence trail ("growth: declining (→SLOW)") so a future real
    decliner still SURFACES in review though it scores SLOW. (SLOW=3 sits well below the floor-relevant range
    and cannot clear an undeserved tier; the P0/P1 deep-dive catches decline anyway.)
  - **VALIDATION (reproduce as a test):** on the 16 companies with clean stated rates, band→score agrees with
    the old Scale-B interpolation within **1pt for 15/16, within 2pt for 16/16** (mean 0.94) — the bands
    PRESERVE the phase-relative intent while fitting the 53/54 companies the interpolation could not score
    without fabricating. Anchors: hinge 51%/public→SOLID(6), function 450%/series-b→HIGH(9), rula
    100%/series-c→HIGH(9), maven 26%/D+→SLOW(3), transcarent 35%/D+→SOLID(6).
- **INTERPOLATION RULE (LOCKED v1.8 — now Scale A ONLY; growth uses the band read above).** For value `v` at a stage with published
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
- **MISSING-DATA CAP (^c10) — SUPERSEDED + REMOVED (v1.24).** The `pmf` cap@7 keyed off growth being ABSENT
  (`growth_score is None`); under the band read growth is NEVER absent (no signal → UNKNOWN → 4), so the cap
  can never fire — it is dead code and is REMOVED (`PMF_MISSING_CAP` deleted), not left inert. (`PMF_NEUTRAL_HALF
  = 4` is KEPT but re-scoped to the ARR half only — growth is always a band value, so only the ARR half can be
  absent-and-filled.)
- **GROWTH-EXTRACTION SCOPE (v1.6 — zero-baseline path SUPERSEDED by the band read; FENCE KEPT).**
  (1) **zero-baseline SUPERSEDED (v1.24):** a launch-from-$0 trajectory is now classified by the run-rate
  REACHED for the stage → its band (a $0→$112M at Series-C is a HIGH run-rate → HIGH), NOT a separate Scale-A
  magnitude path in the growth read. (2) **DERIVED / third-party figures** are still real evidence and BAND:
  a single-source estimate, OR complementary multi-source points read as a trajectory magnitude (v1.25) —
  only same-period CONFLICTS refuse. The **§B6.1 FENCE is KEPT and now HARD-ENFORCED (v1.25 — counts never
  band; a `counts-scale` basis is forced to UNKNOWN in code):** growth_score is
  **revenue/$-growth only** — headcount /
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

**SAME-SOURCE DERIVE GATE — a derived revenue rate needs ONE consistent series (v1.18; HARD gate, not a
caveat).** The growth extractor (Commit 5b) MAY derive a revenue-growth % from two dated revenue figures —
but a derive is VALID only when ALL THREE hold; if ANY fails there is NO usable rate (route to qualitative /
absent, never a derived rate):
1. **SAME MEASURE** — both annual revenue, or both ARR (NOT funding-amount vs revenue; NOT run-rate vs
   trailing/annual).
2. **SAME SOURCE** — both from the SAME company report OR the SAME single estimator's own dated series.
   **Two DIFFERENT estimators' single figures are independent guesses (they often conflict, and can point
   opposite directions) — they do NOT form a series; never derive across them.**
3. **CORRECT TIME ORDER** — baseline = the earlier-dated figure, endpoint = the later-dated figure.
A text hedge ("a rate could not be computed") does NOT block a derive that passes all three (a real
same-source series is usable even when the synthesis hedged).
- **Why a HARD gate, not a caveat (the audit trail — recording the WHY so a future editor does not soften
  it back):** this rule first shipped in Commit 5b as a soft sub-caveat under the "derive even if hedged"
  instruction, and the model IGNORED it — it computed a bogus **102.5%** for `pomelo` by deriving across two
  DIFFERENT estimators (Latka $127.6M + Growjo $63M) **and inverted the chronology** ($127.6M is 2025, $63M
  is 2026 — chronologically a DECREASE). A junk rate from conflicting estimates is the extractor being
  broken regardless of whether the resulting tier survives. So the rule is promoted to a HARD all-three-or-
  nothing gate.
- **Worked example (proves the gate cuts along the right line):** `pomelo` — Latka $127.6M + Growjo $63M =
  TWO estimators → SAME-SOURCE fails → NO derive → `qualitative "growing"` (revenue-implies-growth statement
  present). `season` — Latka's OWN dated series $8.0M (2022) → $12.3M (2023) = ONE estimator's series →
  all three hold → derive ≈ **53.7%**. Same gate, opposite outcomes, along the same-source line.
- **CANONICAL GROWTH-EXTRACTOR EVIDENCE (recorded so Commit-7 assembly wires it):** the growth extractor
  reads **`growth_signal` + `revenue_or_arr` (the synthesized commercial_evidence fields) + `growth_finding`
  (the raw search)** — NOT the raw `commercial_scale_finding`. (Run-1 of the 5b validation fed the wrong
  fields and the missing revenue-direction statement flipped `pomelo` to a wrong `absent`.) Commit 7 MUST
  wire exactly these fields or it silently reintroduces the absent-vs-qualitative bug.
- **NOW ENFORCED IN CODE, not asked-for in the prompt (v1.23 — the gate is deterministic; the prompt gate is
  advisory).** The prompt gate FAILED TWICE (pomelo Run-1; then `equip` at R1, where the live extractor again
  derived a cross-estimator rate — Latka-2021 $4.5M + CB-Insights-2023 $35M → a bogus 7.8x that put equip at
  P1). Caching FREEZES a wrong read, so a twice-failed prompt-trust is exactly what we cannot afford. So the
  DERIVE moves to code (same philosophy as the §B2 floor / §B4 stage & reset overrides — a mechanically-
  checkable rule the LLM can't reliably hold goes in code): the extractor's job becomes **REPORT the
  figures** (each `{value_usd_m, year, source, measure}`, source = the NAMED publisher) — it does NOT derive.
  `structured_evidence.derive_growth_from_figures` computes the rate ONLY from two figures that pass all three
  conditions IN CODE, with a CONSERVATIVE source normalization (`GROWTH_SOURCE_ALIASES`: "CB Insights" ==
  "CB Insights financials" but ≠ "Latka"; an UNKNOWN/ambiguous source keeps its own slug → treated as
  DISTINCT → derive REFUSED). Same-source = same NAMED publisher; when unsure, DIFFERENT wins (refuse) — a
  wrongly-derived rate inflates into P0/P1, so err toward refusing. `equip`: cross-source → refused →
  qualitative → pmf 4 → **P2**. The prompt still carries the FENCE + the report-figures instruction (signed);
  the same-source gate itself is now the code's call.

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
- **REVIEW-GRADE FLOOR REASON — every floored company emits a `floor_reason` (v1.15; built at assembly,
  Commit 7).** Any floor is an UNRECOVERABLE elimination, so each floored company MUST carry a stored
  `floor_reason` detailed enough to judge whether the floor was RIGHT (not merely that it fired), for human
  OVERTURN at Gate 2. This is the same surface-the-machine's-call principle as the §B2 B2B floor and the §B4
  stage override: when the model can't perfectly hold a boundary, the human reviews its call. The reason
  carries its floor SOURCE + review-grade detail, per source:
  - **PATH Test A (B2B floor):** distinguish the human-locked list from a classifier read —
    `"B2B — human-locked floor list"` (review list membership) vs `"B2B — classifier read who_uses=professional (basis: …)"` (review the classification).
  - **PATH Test B:** `"engine-not-alive — B2C: no revenue/scale/growth"` / `"B2B2C: no institutional channel"`.
    The case to catch: a company floored on MISSING evidence that actually exists (Rule 8 — an evidence gap
    floored as a dead engine), so the reason must show what was looked for.
  - **AGENCY fail:** `"AGENCY-fail — [stage]; reset events [event → type / opening, …]; none fired"` — enough
    event detail to judge a reset MISS (the motivating case: a CFO-described-as-growth-support wrongly
    excluded). A bare `"AGENCY-fail"` is useless for review; the events + why-none-fired make it reviewable.
  - **BUILD (Commit 7):** the `floor_reason` is emitted + stored AS A COLUMN when the floor decision is made
    (part of assembly, not bolted on later). **SURFACE (Phase-4):** the Gate-2 review surface renders it on
    the summary-table floor one-liner (`MASTER_REDESIGN_SPEC.md` §4 / `PHASE3_HARDENING_PLAN.md` Section 5) —
    v1.15 ADDS the requirement that the one-liner carry review-grade detail, not a bare floor type.
- **REPRODUCIBLE SCORING via PERSISTED READS (caching) + `tier_review` proximity flag (v1.22 — SUPERSEDES
  the v1.20/v1.21 N=5 stability mechanism).** The reproducibility GOAL is a reproducible PIPELINE, not a
  deterministic MODEL. The four scoring-path LLM reads (§B2 classifier, §B4 reset emitter, §B5 bg_fit, §B6
  growth extractor) are taken ONCE per company and PERSISTED (durable read-columns keyed by company +
  input-hash — the same "gather once, derive freely" pattern as the research findings, locked Rule 4/5); the
  scorer then reads from the PERSISTED reads and never re-rolls. Re-scoring is fully reproducible on ANY
  model. A read is re-taken ONLY DELIBERATELY (a `--refresh` for a company whose data changed — e.g. `equip`'s
  new rounds). **Model-level determinism (temp-0 + seed) was EVALUATED and REJECTED:** `gpt-5.4-mini` is a
  GPT-5-class reasoning model that REJECTS `temperature != 1` (400 error) and whose `seed` is best-effort, NOT
  a determinism contract — so temp-0 is not viable and is NOT used; caching achieves reproducibility
  model-agnostically. The N=5 variance came ENTIRELY from RE-CALLING these reads (they were never persisted);
  caching removes the re-call, so N=5 is MOOT and RETIRED — **not left inert** (dead-but-present logic is a
  comprehension landmine). The LLM still JUDGES (Katelynd's LLM-reads decision is untouched — this is NOT a
  reversal); it is asked ONCE and its judgment is frozen. The single frozen score's tier is the threshold's
  call; a `tier_review` flag surfaces borderline companies:
  - **MECHANISM (score off persisted reads):** each **floor-PASS, non-overridden** company is scored from its
    ONE persisted read-set. Tier = `threshold_tier(FINAL)` (P0≥18 / P1 15-17 / P2 13-14 / P3<13). NO N-run
    loop, NO MAX/MODE resolution — a re-score reads the same frozen values → identical tier, by construction.
  - **`tier_review` PROXIMITY FLAG (margin = ±1, floor-PASS only):** a company whose stable FINAL sits
    **within 1** of a tier boundary — i.e. `threshold_tier(FINAL−1) != threshold_tier(FINAL)` OR
    `threshold_tier(FINAL+1) != threshold_tier(FINAL)` — is flagged for Gate-2 human review. Concretely
    FINAL ∈ {12, 13, 14, 15, 17, 18} (the boundary-adjacent scores). This is a REVIEW flag, **NOT an
    auto-bump**: the tier stands at the threshold's call; the flag says "one point from a line — a human
    should look." (Floored / human-overridden companies are NOT proximity-flagged — their tier is not
    threshold-driven.)
  - **`floored_on_bg` — the FLOORED-ON-BACKGROUND review flag (v1.24 WIDENED from v1.23
    `floored_bg_near_threshold`; the piece that makes the P3 floor trustworthy under caching).** Katelynd
    deep-dives every P0/P1 by hand, so top-bucket errors self-correct; the EXPENSIVE error is a real prospect
    frozen-LOW in the un-reviewed P3 pile (`grow`: its bg froze at 4 → floored, but it is a real P0 candidate
    — it only surfaced because she happened to know it). So EVERY company floored SOLELY by its bg read is
    surfaced into the bounded `review_set`. ALL must hold: (a) floored on **bg** specifically (NOT gate-
    floored maturity/B2B — those are deterministic, a re-read wouldn't change them; NOT pmf); (b) would
    floor-PASS if bg cleared (pmf > 4). **v1.24 REMOVES the v1.23 `{3,4}` wobble window (and retires
    `BG_FLOOR_WOBBLE` for this flag):** the window was a proxy for "a noisy single bg read could have rolled
    to passing," calibrated to the OBSERVED pre-caching wobble (typical ±1, `season` ±2, `grow` ±3). Two
    v1.24 changes make the proxy both unnecessary and wrong-shaped: (1) bg is now the **mean of N=4 reads,
    rounded half-up, then cached** (§B5) — a single-read wobble no longer exists to bound; the frozen value is
    an average, not one roll. (2) The remaining risk is not "how far from the line" but simply "the floor rests
    ENTIRELY on the one read that is judgment, not arithmetic" — a bg=2 floor is exactly as worth a human
    glance as a bg=4 floor, because BOTH are the model's call on fit and BOTH block a real prospect if the read
    is wrong. So the flag now fires on ANY bg-binding floor, not just near-the-line ones — high-recall by
    design (§A7), the review_set stays bounded because bg-SOLELY-floored companies (pmf>4, not gate-floored)
    are inherently few. **The bg=None / READ-FAILED label stays DISTINCT** (a separate flag): an ABSENT bg is
    a pipeline failure to re-take, not a low-fit judgment to review. **Action = a REVIEW flag → consider a
    deliberate, logged `--refresh <company>` (re-take that one company's N=4 bg); NEVER an auto-un-floor,
    NEVER a revert to multi-run.** A refresh that comes back ALSO low confirms the floor. Everything else in
    P3 floored for a deterministic reason (maturity / B2B) or a genuinely-low pmf can be trusted un-reviewed.
  - **PRECEDENCE (exactly ONE layer):** (1) floor rule gates FIRST (floor-FAIL → P3), (2) human overrides
    (Rule 6 — Function P1-override; the §B4 reset overrides), (3) the single-run threshold tier + the
    `tier_review` proximity flag on what remains.
  - **REPRODUCIBILITY PROOF (run-twice-identical):** because scoring reads the PERSISTED read-columns,
    re-scoring is identical BY CONSTRUCTION (same frozen inputs → same tiers) on any model — no API-determinism
    dependency. The proof is still run: score the roster TWICE off the persisted reads and assert the two
    distributions are BYTE-IDENTICAL (this checks the caching is wired correctly, i.e. nothing re-calls the LLM
    behind the scorer's back). The ONLY LLM calls are the ONE-TIME reads that populate the cache; if a company
    is re-read, that is an explicit `--refresh`, logged, never silent.
  - **MANDATORY READ-CORRECTNESS VERIFICATION (the one real risk — caching FREEZES whatever it reads):** a
    one-time read that is WRONG is now frozen wrong, so the read must be CORRECT before it is trusted. Before
    any tally is ratifiable, the previously-noisy companies are checked BY NAME on their FROZEN read: `noom`
    (reset emitter must read "CMO to support expansion" → growth-support → `unclear`, NOT fire), `hinge`
    (public-company layoff → defensive → `no`), `equip` (growth extractor must apply the §B6.1 same-source gate
    to Latka + CB-Insights → qualitative, NOT the 7.8x cross-estimator derive), `season` (bg_fit reads in a
    stable tier). **If any read is WRONG → HARDEN that
    prompt (make the rule a hard gate the read must pass), re-take the read, re-verify — NEVER revert to
    multi-run.** Multi-run was MASKING these; a single frozen read EXPOSES them; hardening FIXES them
    permanently (a reproducible wrong answer is findable and fixable). The §B4 reset overrides + the Equip data
    refresh stay as documented belt-and-suspenders; the verification checks whether the read is ALSO correct on
    its own.
  - **AUDIT — why RETIRE, not keep (the full lineage, so it is never mis-simplified):** v1.17 proximity-bump
    (collapsed P2) → v1.20 N=5 run-to-run stability (added specifically for `season`'s bg_fit 5↔7 wobble) →
    v1.21 MODE (the R1 live run showed "highest observed" inverted the distribution — 9 straddlers). N=5 was
    NEVER an original design — Commits 1–7 scored each company ONCE; N=5 was a LATE DOWNSTREAM WORKAROUND for
    read-noise. It already COLLAPSED the variance to one tier (MODE) + a flag — it treated the variance as
    noise-to-resolve, not signal-to-preserve. Its only real signal ("this company is borderline") is fully
    recovered by proximity-on-a-stable-score (a company wobbles precisely because its true score sits near a
    line). So v1.22 fixes the ROOT (the noise, by PERSISTING the reads — take each once, score off the frozen
    value) and removes the workaround, keeping its one signal as `tier_review`. (Intent-to-action: retiring
    N=5 is removing a WORKAROUND after its root cause is fixed — cleanup, not reversal; the LLM-reads decision
    is untouched.)
  - **R1 (Commit 8) — the target is an OUTPUT, re-validated by name, NOT forced:** R1 runs each floor-PASS,
    non-overridden company ONCE (reproducible by construction — scored off the persisted reads),
    TWICE-to-prove-identical. The spike's `P0=4/P1=6/P2=6/P3=38`
    was a FROZEN-score ESTIMATE; the persisted-read hardened system produces its own distribution for REAL
    reasons (the six frozen-at-FINAL=14 spike-P2 companies were coin-flips and scatter), ratified company-by-
    company. Forcing the output back to 4/6/6/38 (shim / threshold nudge / silent adjustment) is a FAILED R1;
    a reproducible distribution understood by name is a PASSED one.
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
