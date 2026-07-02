# Scoring Framework — Phase 3 Hardening: Process History & Decision Record
### The R1 re-validation arc, v1.20 → v1.25, and why we landed where we did

This document records the full reasoning arc of the Phase-3 R1 re-validation — the decisions, the dead ends,
and why the framework ended at v1.25. It is a companion to the SOT (`SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`),
which holds the *current* rules; this holds the *why*, so the path isn't re-litigated or a fixed bug
reintroduced.

---

## The starting point (entering R1)

Phase-3 hardening had rebuilt the scorer as committed package code (Commits 1–7). R1 re-validation was meant
to confirm the hardened scorer reproduced the spike's tiering estimate (P0=4/P1=6/P2=6/P3=38) — **by name**,
company-by-company, with the understanding that the spike number was a *frozen estimate*, not a target to
force. The governing standard throughout: **the tally is an OUTPUT ratified by name; forcing the number (via
shim, threshold nudge, or silent adjustment) is a FAILED R1.**

---

## Arc 1 — The N=5 stability detour, and why it was retired (v1.20 → v1.22)

**v1.20 — N=5 stability detector.** The first R1 run was noisy: `bg_fit` (the background-fit LLM read)
wobbled run-to-run (e.g. `season` 5↔7, `grow` 4↔8), flipping companies across tier lines. The first fix
scored each company N=5 times and resolved the tier.

**v1.21 — MAX → MODE resolution.** N=5 with "highest tier observed" resolution ran top-heavy (P0=7): it
promoted companies off a single lucky run. Changed to MODE (typical tier). Still didn't reproduce the
distribution, because the underlying reads were genuinely noisy *and* two LLM steps were misapplying their own
rules on live runs.

**The diagnosis that changed direction:** the N=5 variance wasn't signal — it was an artifact of *re-calling*
the LLM. Investigation (Task 2) found the checkpoint persisted the research findings but **none of the four
scoring reads** (`background_fit`, `who_uses/who_pays`, growth) — so `run_r1` re-called all four live every
run. The variance came entirely from re-calling reads that should have been persisted once.

**The model-determinism dead end (Task 1, verified against current docs):** we considered temperature-0 +
seed to make reads deterministic. Verified: `gpt-5.4-mini` is a GPT-5-class reasoning model that **rejects
`temperature != 1` (400 error)**, and `seed` is best-effort, not a determinism contract. Model-level
determinism was never available.

**v1.22 — REPRODUCIBLE SCORING via PERSISTED READS (caching).** The resolution: take each read ONCE →
persist it (durable read-columns keyed by company + input-hash) → the scorer reads from the cache, never
re-rolls. Reproducible **by construction**, on any model, no API-determinism dependency. N=5 retired (not left
inert — dead-but-present logic is a comprehension landmine). Replaced with a `tier_review` proximity flag
(FINAL ∈ {12,13,14,15,17,18}) — a REVIEW flag, not an auto-bump. The key realization: the LLM-reads decision
was *not* reversed (the LLM still judges); we removed a late *workaround* (N=5) after fixing its root cause
(re-calling noise).

---

## Arc 2 — Correctness under caching: the reset overrides & metric honesty (v1.23)

Caching solved *reproducible* but not *correct* — a frozen wrong read is permanently wrong. So by-name
verification became the load-bearing gate. It caught:

- **A signed-but-unbuilt gap:** `DOCUMENTED_RESET_OVERRIDES` (hinge/noom → no-fire) was documented in §B4
  (signed 53a85c5) but the **code was never written** — so hinge's reset over-fire wasn't caught. A doc-vs-code
  divergence class. Built it (v1.23) + scanned for other signed-but-unbuilt decisions (none).
- **The reset emitter is itself LLM-noisy:** noom's over-fire and hinge's public-layoff over-fire were the
  emitter misapplying its own documented rules — the evidence that LLM reads need deterministic backstops
  where the rule is mechanically checkable.
- **A misleading autonomy metric:** `review_set_size` counted all 40+ floored companies; the real must-review
  set (proximity + overrides) is ~6. Split into `review_set` (bounded, must-look) vs `floor_audit`
  (on-demand). This is the honest autonomy number.
- **The floored-but-close flag (v1.23):** to make the P3 floor trustworthy without reviewing all of it, a
  company floored *only* on a near-threshold bg (the frozen-low-roll risk, like `grow`) was surfaced to
  review.

---

## Arc 3 — The growth-scoring redesign: the core fix (v1.24)

**The recurring yo-yo, diagnosed.** Every run swung the distribution, and the swing traced to one place:
**growth (pmf) logic churn.** Each growth fix (same-source gate v1.18, deterministic backstop v1.23,
report-figures schema) was locally correct but re-sorted the whole pmf column — and because pmf is a hard
floor gate, that re-sorted the whole distribution. The deeper cause: **the scoring thesis (a precise
phase-relative YoY %, via the locked Scale B interpolation) required data the research doesn't have.** Only
~23/54 companies supply a clean stated rate; the rest were *derived* (the cross-source bug) or *defaulted*
(pmf suppressed). The precision of Scale B outran the precision of the growth research.

**Two kinds of instability, separated:**
- **pmf swings = OUR logic churn** (self-inflicted; stops if we stop changing growth logic).
- **bg swings = model noise** (inherent LLM sampling variance; caching froze *one* sample, which is why
  `grow` got floored on a frozen-low 4).

**v1.24 — the band redesign.** Replaced the Scale-B-*interpolation*-for-growth with a **4-band
classification**: HIGH=9 / SOLID=6 / SLOW=3 / UNKNOWN=4(flagged). The band **cutoffs are anchored to the
locked Scale B's own per-stage cutpoints** (HIGH ≥ score-8 column; SOLID = score-5..7; SLOW ≤ score-4) — so
the phase-relative intent is *preserved*, not re-invented (a Series-A at 40% is unremarkable; a public co at
40% is excellent). **Validation:** on the 16 companies with clean rates, banding reproduced Scale B within 1pt
for 15/16, 2pt for 16/16 (mean 0.94) — the bands ARE Scale B at lower resolution, matching the granularity
the evidence actually supports. The extractor's job became *classification* (which the LLM holds reliably),
not *derivation* (which it failed twice). The entire v1.23 derive subsystem (report-figures,
`derive_growth_from_figures`, same-source aliases) was SUPERSEDED and REMOVED.

**Accompanying v1.24 changes:**
- **bg N=4-average-then-cache (§B5):** bg is the one noisy continuous read, so it's read N=4 times ONCE at
  population, averaged, then cached — reproducible (cached average) AND noise-reduced (one bad roll can't
  swing it). This EXTENDS caching (4 passes once, not re-call per score), it does not reverse v1.22. Scoped to
  bg only (growth is now a stable band; reset/classifier categorical). Rounding: mean rounded half-up before
  the floor check. This un-froze `grow` (4 → 8 average → P0).
- **cap@7 removed** (dead code — growth is never None under bands), `PMF_NEUTRAL_HALF` re-scoped to the ARR
  half.
- **floored_on_bg (§B7, widened from floored_bg_near_threshold):** ANY company floored solely on bg → review
  (not just near-threshold). After averaging, a bg-caused floor is a stronger "look at this" signal.
- **Declining → SLOW, recorded not banded** (zero genuine decliners in the data → no 5th band; the word
  "contract" caused false positives).

---

## Arc 4 — The same-source-gate reflex, corrected (v1.25)

The first v1.24 R1 run reintroduced apparent "cross-source derives" (equip: Latka-2021 + CB-Insights-2023;
bicycle: CB-Insights-2021 + GetLatka-2023). The reflex was to restore the hard same-source gate. **This was
judged the WRONG fix**, and the correction is the key insight of v1.25:

- The same-source gate existed to prevent deriving a *precise rate* across estimators — meaningful only when
  the score depended on the precise rate (old interpolation). **The band read doesn't use a precise rate — it
  uses which side of the stage cutpoint.**
- The data is NOT conflicting estimators — it's **complementary** points (different years, different shops, no
  competing estimate for the same period) sketching a trajectory whose *order of magnitude* is unambiguous.
- A hard same-source refusal would drop equip + bicycle (genuinely fast-growing) to UNKNOWN — **penalizing
  them for having two corroborating sources instead of one.** Perverse.

**v1.25 — trajectory-magnitude banding + hard fence.**
- **Trajectory-magnitude rule:** a band may rest on a single-source rate, a single-source series, OR
  **complementary multi-source points** (different years, no same-period conflict) read as a trajectory
  magnitude. The ONLY multi-source case refused: two sources CONTRADICTING on the SAME period.
- **The real bug, fixed — the HARD FENCE (pomelo):** a growth band may rest ONLY on revenue/$-growth
  evidence. Counts/scale (covered-lives, members, patients) can NEVER band HIGH/SOLID — a `counts-scale` or
  `none` basis is forced to UNKNOWN **in code** (gate-in-code, deterministic backstop to the prompt). pomelo
  had banded HIGH on covered-lives; v1.25 forces it to UNKNOWN.
- **Source-mode recording:** the extractor records `basis` (revenue-rate / revenue-trajectory / counts-scale /
  none) + `source_mode` (single-source / complementary-multi / conflict) per company, for the review trail.
- The derive machinery stays REMOVED (the hard same-source gate is the wrong tool for banding).

**The v1.25 R1 run (ratified):** pomelo → UNKNOWN/fence-forced → P1-flagged (off the fabricated P0);
equip/bicycle → legitimate trajectory HIGH; grow → P0 (bg un-frozen); every counts-scale basis → UNKNOWN
(fence firing); `read_failures` empty; all bg=None are gate-floored B2B. Distribution 5/7/5/37 — an output,
ratified by name.

---

## Standing principles established across the arc (the meta-lessons)

1. **Gate-in-code beats gate-in-prompt for mechanically-checkable rules** — applied to the B2B floor, stage
   override, structural-role reset, and the v1.25 fence. But *not* over-applied: the same-source gate was
   *removed* because banding made its precision-enforcement the wrong tool. The test is whether the rule is
   both mechanically checkable AND relevant to how the score is used.
2. **Match scoring precision to evidence precision.** The band redesign's core lesson: a precise scoring
   thesis on ragged evidence produces the yo-yo. Coarsen the score to the granularity the data supports.
3. **Reproducible ≠ correct.** Caching freezes reads; a frozen wrong read is permanent. By-name verification
   is the load-bearing gate, not the tally.
4. **The tally is an output, never forced.** Every distribution was ratified by name; the spike's 4/6/6/38 was
   a frozen estimate that legitimately scattered under live scoring.
5. **Retire workarounds after fixing root causes** (N=5 → caching), and never leave dead-but-present logic
   (cap@7, N=5 machinery) — it's a comprehension landmine.
6. **Intent-to-action:** when a design intent isn't directly actionable, confirm the exact translation rather
   than filling the gap with the plausible reading (the phase-relevance guard was investigated and NOT built
   when its blast radius was near-zero; the same-source-gate reflex was stopped before it discarded real
   signal).

---

## Known watch-items carried forward (for the ledger review, NOT bugs)

- **GetLatka $0→$N single-source trajectories:** several HIGH bands rest on GetLatka series where "$0 in year
  one" may reflect the estimator having no early-year data rather than the company genuinely starting at zero.
  The band is doing what it's told, but the *data credibility* warrants scrutiny in the ledger review (fay,
  foodsmart, nourish, berry street, summer, visana partly).
- **bg=None: gated vs. low-score distinction.** A B2B/non-consumer company correctly FLOORS (gated); a
  consumer company with weak habitual use should score LOW (bg 3-4, capped not gated). Currently bg=None
  conflates "correctly gated B2B" with "would-be low consumer score." The ledger must make this legible per
  company. (This run's bg=None were all verified gate-floored, read_failures empty — no active bug, but the
  distinction should be exposed.)
- **The 40/60 ARR/growth PMF blend** is a documented OPEN DIAL. We considered and *rejected* shifting to 60-70%
  ARR: the ARR evidence is no more credible than growth (both estimate-dominated, ARR estimates conflict
  *more* across sources), and weighting ARR high reverses the A2 thesis (reward slope-to-$100M, not current
  level). Revisit only if motivated by a specific failure, not preemptively.

---

## Version map (quick reference)

| Version | Change | Why |
|---|---|---|
| v1.20 | N=5 stability detector | bg_fit run-to-run wobble flipping tiers |
| v1.21 | MAX → MODE resolution | MAX promoted off single lucky runs (top-heavy) |
| v1.22 | Caching (persisted reads); N=5 retired; tier_review flag | N=5 variance was a re-call artifact; temp-0 dead on gpt-5.4-mini |
| v1.23 | Built DOCUMENTED_RESET_OVERRIDES; review_set/floor_audit split; floored_bg_near_threshold | signed-but-unbuilt gap; honest autonomy metric; trustworthy floor |
| v1.24 | Growth BAND redesign; bg N=4-average; floored_on_bg widened; cap@7 removed | precise-thesis-on-ragged-data yo-yo; bg noise; dead code |
| v1.25 | Trajectory-magnitude banding (complementary-multi allowed); HARD fence in code | same-source gate wrong tool for banding; pomelo counts-scale leak |
