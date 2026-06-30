# Phase-3 Hardening — SCOPING / BUILD PLAN (read-only inventory; HOLD for approval)

> **STATUS: PLAN ONLY — no scorer code, no logic commits. HOLD for Katelynd's approval before Section-3 commit #1.**
> This doc is the inventory + spike→spec map + commit-by-commit build plan + spec-gap hunt for rebuilding the
> §B scorer as committed package code (clean-room from the SOT, logic-faithful to the disposable Phase-2 spike
> per `spike_pass1_notes.md` **R1**), then re-validating the §B7 thresholds against the hardened scorer.

## Provenance of this read (verify-the-input discipline)

- **Canonical docs read at SHA `3741f2d6d526bd5d20b937b2f891af82cec20897`** (`docs-scoring-sot` HEAD), via
  `git show docs-scoring-sot:specs/<path>` — not from memory or any re-uploaded copy.
- **Drift vs the bundle's cited `9f543d8`:** the ONLY delta is one later commit (`3741f2d`) that ADDED the 5
  disposable spike cells under `specs/spike_disposable/` (`README.md`, `bg_fit_scores.py`,
  `spike_assemble_full_table.py`, `spike_scoring_spine.py`, `spike_step_b5_bgfit.py`; +481 lines, all
  additions). **No spec file changed.** Expected/benign — not spec drift. Verified with
  `git diff --name-status 9f543d8 3741f2d`.
- **SOT read = FRAMEWORK_VERSION v1.11** (header line 3). Fixture = v1.3. Both current; no stale-copy
  contamination.
- **Current PACKAGE code read from `research-search-recovery @ 9b4c69ac11c0c9a34e6090c56d91e7262f8ae8b3`**
  (NOT from `docs-scoring-sot`, whose package is stale), via `git show research-search-recovery:src/...`.
- **Spike-header caveat honored:** `spike_scoring_spine.py:2` declares "clean-room from SOT v1.4 §B3–B7," but
  its body implements §B6 v1.8 (Scale A/B + geometric interp) and §B4 v1.10 (`STAGE_OVERRIDE`). Mapped below
  against SOT **v1.11**; where comment and code disagree, the **code** is the artifact of record for "what the
  spike did," the **SOT** for "what the hardened scorer must do."
- **54-company research CSV** (the scoring input, NOT scored this pass): `~/Downloads/v42_full_regen_clean_slate_20260622_full56_checkpoint_FINAL.csv`. The spine is **not self-contained** — it
  imports `funding_stage_from_rounds` (`research-search-recovery:src/health_tech_research_agent/structured_evidence.py:200`) and reads this CSV; offline-deterministic except the frozen `BG_FIT` dict.

**Branch hygiene:** this doc is committed on a NEW `phase3-scoping` branch off `docs-scoring-sot` — branch-only,
no self-merge, `main` untouched. **Section-3 BUILD commits will write PACKAGE code on the
`research-search-recovery` lineage (a code branch), NOT on `docs-scoring-sot`** (the docs branch) and NOT on
this scoping branch.

---

# Section 1 — Inventory of the spike (what the disposable spike implements)

All line ranges are in the committed spike cells under `specs/spike_disposable/` at `3741f2d`. **Det** =
deterministic; **LLM** = model-based; **Data** = frozen artifact.

## 1A. business_model (`spike_scoring_spine.py`)

| Item | File:lines | What it does | Kind |
|---|---|---|---|
| `FX_B2B` | spine:18 | The 6 human-locked floor companies, baked as a set | Det (fixture-as-truth) |
| `FX_B2C` | spine:19 | The 8 B2C companies, baked | Det (fixture-as-truth) |
| `FX_B2B2C` | spine:20 | The 41 B2B2C companies, baked (firefly present in the list; firefly+videahealth deferred at run-time → 40/54 scored) | Det (fixture-as-truth) |
| `BUSINESS_MODEL` | spine:21 | Dict merge `{co: label}` over the 3 sets | Det |
| `LOCKED_FLOOR` | spine:22 | `= FX_B2B`; forces B2B regardless of classifier (§B2 v1.4); covers medically home | Det |
| `STAGE_OVERRIDE` | spine:26 | `{"signos":"series-b","bicycle health":"series-b","9amhealth":"series-b"}` — §B4 v1.10 designated-series corrections; applied in `run` at spine:204 | Det (disposable stand-in) |

**The 3 documented classifier overrides** (noom→B2C, signos→B2C, counsel→B2B2C) are NOT separate code — they
are **baked into the `FX_*` sets**: `noom med` ∈ FX_B2C (spine:19), `signos` ∈ FX_B2C (spine:19),
`counsel health` ∈ FX_B2B2C (spine:20). The spike runs **no classifier at all** — it bakes the fixture labels
as truth (`README.md` and spine:6 say so explicitly). `business_model` for a row is resolved in `run` at
spine:202: `"B2B" if co in LOCKED_FLOOR else BUSINESS_MODEL.get(co,"UNMAPPED")`.

## 1B. PATH gate §B3 (`spike_scoring_spine.py:35–63`)

| Function | File:lines | What it does | Kind |
|---|---|---|---|
| `ABSENT` | spine:28 | Absence sentinels for `_has` | Det |
| `_has` | spine:29–31 | Robust non-empty/non-absent check (whitespace-normalized, prefix-against-sentinels) | Det |
| `_ce` / `_me` | spine:32–33 | Pull `commercial_evidence` / `maturity_evidence` sub-dicts from `fit_brief_json` | Det |
| `_figure` | spine:38–40 | **Robust** "$N / N M/B anywhere in the text" regex (presence ANYWHERE, not a prefix check — handles "No company ARR, but Sacra estimates $100M") | Det |
| `has_any_revenue` | spine:41 | `_figure` on `revenue_or_arr` | Det |
| `has_meaningful_scale` | spine:42 | `_figure` on `sponsored_user_scale` OR `paying_customer_count` | Det |
| `has_positive_growth` | spine:43–45 | "grow"/`N%`/"x over"/"tripl"/"doubl" AND not "declin" | Det |
| `has_real_institutional_channel` | spine:46–53 | Named-payer regex (aetna/bcbs/anthem/uhc/cigna/oscar/humana/medicaid/medicare/cms/commonspirit/essence/baptist) **OR** structural (covered-lives / in-network / N members; employer + partner/client/benefit/self-insured/for-work/sponsored/funds; health-plan + partner/contract/client; value-based; outcomes-based contract) | Det |
| `path_gate` | spine:54–63 | Test A: `bm=="B2B"`→FAIL. Test B: B2C → alive if rev OR scale OR growth (no-revenue fallback ^c10); B2B2C → PASS iff `has_real_institutional_channel`; else UNMAPPED FAIL | Det |

Note the **employer-direct scope** (the Function Health gap, §B3) is covered by the `employer + …` structural
branch at spine:50 — institutional channel is NOT payer-only.

## 1C. AGENCY gate §B4 (`spike_scoring_spine.py:65–98`)

| Function | File:lines | What it does | Kind |
|---|---|---|---|
| `RESET_FIRES` | spine:66 | The 5 fireable event types | Det |
| `_norm` | spine:67 | Normalize event_type to hyphenated lowercase | Det |
| `_PIVOT_SUBSTANCE` | spine:69 | basis-regex: pricing/business-model/product-strategy → pivot (NEVER fires) | Det (bridge) |
| `_IPO_PREP` | spine:70 | basis-regex: ipo/s-1/registration/public-market → non-qualifying | Det (bridge) |
| `_GROWTH_SUPPORT` | spine:71 | basis-regex: "to support …expansion"/"accelerate growth" → not a reopening | Det (bridge) |
| `_event_qualifies` | spine:72–80 | opening ∈ {yes,true} AND type ∈ RESET_FIRES AND none of the 3 basis-regexes match | Det |
| `reset_fired` | spine:81–83 | any qualifying event in `reset_evidence.reset_events` | Det |
| `agency_gate` | spine:84–98 | stage via `funding_stage_from_rounds`; public/series-d-plus → PASS iff reset else FAIL; seed/pre-seed → FAIL (no rescue); series-a/b/c → PASS; `late_c_flag = (stage=="series-c")` exposed as the open dial (clean PASS this run) | Det |

**The basis-regex bridge** (`_PIVOT_SUBSTANCE`/`_IPO_PREP`/`_GROWTH_SUPPORT`) exists because the regen's reset
EMITTER pre-dates SOT §B4 v1.5 — see Section 2, divergence D2.

## 1D. PMF §B6 (`spike_scoring_spine.py:100–182`)

| Item | File:lines | What it does | Kind |
|---|---|---|---|
| `ARR_SCALE` | spine:103–110 | Scale A: 6 stages × 10 ARR($M) anchors — matches SOT §B6 v1.8 table | Det |
| `GROWTH_SCALE` | spine:111–117 | Scale B: 5 rows × 10 %YoY anchors — matches SOT §B6 v1.8 table | Det |
| `_arr_stage` | spine:118–119 | Scale-A stage normalization (pre-seed→seed; unknown→series-b fallback) | Det |
| `_growth_stage` | spine:120–122 | Scale-B map: series-d-plus & public → public row; seed/a/b/c 1:1 | Det |
| `scale_interp` | spine:123–130 | Geometric interpolation, round-half-up, clamp 1–10 (`int(floor(s + ln(v/lo)/ln(hi/lo) + 0.5))`) | Det |
| `_money` | spine:131–135 | Max $ value parsed from text (m/b → ×1e6/1e9) | Det |
| `arr_level_score` | spine:136–139 | `_money(revenue_or_arr)` → Scale A interp; None if no figure | Det |
| `_FENCE` | spine:142 | §B6.1 fence regex: headcount/employee/staff/download/install/MAU/users/registered/active/partner/client-count/funding/valuation/utilization/**covered-lives**/**patients**/member-reach | Det |
| `growth_score` | spine:143–171 | derived-vs-company-reported `src`; **zero-baseline** branch (→ score magnitude via Scale A, arr=growth collapse); **fenced** %/multiple extraction (skip a figure within ±40 chars of a fenced term); tripl/doubl → multiple; multiple→%YoY; qualitative no-rate fallbacks (declin→1, flat→3, grow→5) | Det |
| `pmf` | spine:172–182 | `round(0.4·arr + 0.6·growth)`; missing→neutral 4 for the absent half; **cap@7 only when `g_final is None`** (genuine growth absence) | Det |

**Acceleration is REMOVED/PARKED — confirmed:** `growth_score` returns `accel=0` on every branch
(spine:154,166,168,169,170,171); `pmf` never reads it for scoring; the `accel` column is display-only. No +1/+2
fires anywhere. ✔

## 1E. STRAIN §B7 (`spike_scoring_spine.py:184–193`)

| Function | File:lines | What it does | Kind |
|---|---|---|---|
| `strain` | spine:185–193 | structured `a2_score` ≥70→(2,STRONG); ≥55 OR speed-of-scale text→(1,MODERATE); else (0,WEAK,"default-low"). Speed regex: `N0{1,3}→N` / "in ~6" / "doubled" in `operating_characteristics_finding` | Det |

## 1F. Assembly (`spike_scoring_spine.py:195–243` + `spike_assemble_full_table.py`)

| Item | File:lines | What it does | Kind |
|---|---|---|---|
| `run` | spine:195–220 | Per row: resolve bm → `agency_gate` → apply `STAGE_OVERRIDE` (spine:204) → `path_gate`; if either FAIL → floored (P3). Else `pmf`, `strain`, `bf=bg_fit_fn`; `final = bf + pmf + strain`; `floor_ok = bf>4 AND pmf>4`. Sort by (final, pmf) desc | Det |
| `print_report` | spine:222–243 | Renders table, floored list, zero-baseline list, residual-cap list, PMF distribution, coverage | Det |
| `bg_fit_fn` | assemble:19–24 | Looks up frozen `BG_FIT[co][0]`; None if absent | Det (reads frozen LLM) |
| `loop_of` | assemble:26–28 | `BG_FIT[co][1]` (data_feedback_loop) | Det |
| `FLAGS` | assemble:31–36 | Static spike-grade flags (outcomes4me/pomelo fence-leak; season under-extract; jasper data-gap) | Det |
| `OVERRIDE_CANDIDATE` | assemble:42 | `{"function health"}` — keep bg_fit=4, tag for Rule-6 review-time override | Det (overlay) |
| `LEAK_DISCOUNTED` | assemble:43 | `{"outcomes4me"}` — force floor=FAIL (the 485% fence-leak rides PASS) for calibration honesty | Det (overlay) |
| `eff_floor_ok` | assemble:44–45 | Applies LEAK_DISCOUNTED to floor_ok | Det |

## 1G. §B5 background-fit (`spike_step_b5_bgfit.py` + `bg_fit_scores.py`)

| Item | File:lines | What it does | Kind |
|---|---|---|---|
| `BG_PROMPT` | b5:26–43 | The LOCKED §B5 v1.7 gradient prompt (byte-identical to SOT §B5 lines 343–362) | LLM |
| `bg_fit` | b5:46–58 | Builds evidence from operating/commercial/outcomes findings; `call_openai(web_search=False)`; parses JSON → (bg_fit, loop, basis) | LLM (Colab) |
| `PASSED` | b5:15–22 | The 37 gate-passed companies the b5 cell scores | Det |
| `BG_FIT` | bg_fit_scores.py:2–40 | Frozen 37-company dict `{co:[score, loop, basis]}` from the validated Colab run — the ONLY LLM output, frozen for offline reproducibility | Data |

---

# Section 2 — Map spike → committed specs, and every divergence

For each piece: the SOT §/version it must honor, and where the spike diverged from a clean implementation.
**D1–D5** are the required divergences; **D6** is an additional finding.

| Spike piece | Honors (SOT/fixture) | Clean in spike? |
|---|---|---|
| FX_*/LOCKED_FLOOR baked as truth | §B2 v1.4 mapper + human-locked floor (6); fixture v1.3 (6/8/41, 7 asserts) | **No** — bakes fixture, runs no classifier → **D4** |
| STAGE_OVERRIDE | §B4 v1.10 designated-series rule | **No** — disposable stand-in → **D3** |
| `path_gate` / `has_real_institutional_channel` | §B3 Test A floor; Test B aliveness; employer-direct scope-fix | **Yes** (faithful; structural channel covers employer-direct) |
| `_event_qualifies` basis-regex bridge | §B4 v1.5 substance/IPO/confidence | **No** — bridge over a stale emitter → **D2** |
| `agency_gate` maturity buckets / reset-on-gate / late_c dial | §B4 (buckets, D+ fails-without-reset, seed no-rescue) | **Yes** (faithful) |
| ARR_SCALE / GROWTH_SCALE / scale_interp | §B6 v1.8 Scale A / Scale B / geometric round-half-up | **Yes** — **D5 = confirm parity (done below)** |
| `growth_score` regex extractor | §B6 v1.6 (zero-baseline+derived SCORE; cap genuine-absence only) + §B6.1 fence | **No (by design)** — regex must become LLM judgment → **D1** |
| `pmf` cap@7 / 40-60 / neutral-4 | §B6 v1.8 cap mechanism; §B7 v1.11 dials | **Yes** (faithful) |
| `strain` | §B7 (0..+2; B1-structural/B2-reported; default-low) | **Yes** (faithful; structured a2 + speed-of-scale only — see D6) |
| `run` floor + sort | §B7 v1.11 (`final=bf+pmf+strain`; `floor_ok = bf>4 AND pmf>4`) | **Yes** (faithful) |
| Step-A overlays (override-candidate / leak-discount) | §B7 v1.11 Rule-6 human decisions | **Yes** (review-time, not logic) |
| BG_PROMPT / BG_FIT | §B5 v1.7 locked prompt | **Yes** (prompt byte-identical; frozen output is the validation reference) |

## D1 — Growth extractor: regex → LLM growth-presence judgment (divergence by design)

- **Honors:** SOT §B6 v1.6 (zero-baseline + derived MUST score; cap only on genuine absence) and the **§B6.1
  FENCE** (revenue/$-growth only; member/patient/covered-lives/headcount/download/MAU/partner/funding counts
  are SCALE, never `growth_score`). `spike_pass1_notes.md` §3 + R2.
- **Spike divergence:** `growth_score` (spine:143–171) uses a ±40-char regex fence (spine:158,160). It is
  **spike-grade and leaks/misses** at the boundary. The hardened extractor MUST become an **LLM growth-presence
  judgment** (like the §B2 classifier) that reliably separates revenue/$ growth from count growth.
- **3 named regression fixtures (R2 — MUST pass):**
  - **pomelo care** — must NOT count **covered-lives +50%** as revenue growth (spike LEAKS → grw inflated;
    flagged in `SPIKE_FINAL_RANKING.md` row 9 and `FLAGS` assemble:33).
  - **outcomes4me** — must NOT count **patient +485%** as revenue growth (spike LEAKS → grw=10; spike
    compensates with the `LEAK_DISCOUNTED` overlay assemble:43 to force floor-FAIL).
  - **season health** — must FIND the buried **~53.7%** revenue growth (spike MISSES → qualitative grw=7,
    under-extracted; `SPIKE_FINAL_RANKING.md` row 10).
- **Risk if missed:** highest — these three sit at P1/P3 boundaries; an extractor that re-leaks/re-misses
  changes their grw → pmf → FINAL → tier, **invalidating the R1 threshold transfer**.

## D2 — Reset emitter: substance-classifying emitter is the permanent fix (not the basis-regex)

- **Honors:** SOT §B4 v1.5 (substance-over-label; IPO-prep non-qualifying; confidence bar — `opening` must be
  a clear `yes`, growth-support adds don't fire, N unclears don't sum). `spike_pass1_notes.md` §2.
- **Spike divergence:** the spike applies `_PIVOT_SUBSTANCE`/`_IPO_PREP`/`_GROWTH_SUPPORT` basis-regexes
  (spine:69–71) to the EMITTED events as a **bridge**, because the regen's emitter pre-dates v1.5.
- **SHARPENED FINDING (verified in current package code):** the **deterministic rule already exists, correct,
  in the package** — `derive_reset_signal()` at
  `research-search-recovery:src/health_tech_research_agent/structured_evidence.py:452` fires IFF
  `event_type ∈ RESET_FIREABLE_TYPES AND opening=="yes"`, **with no basis-regex** (plus `reset_needs_review`
  :471, `reset_basis_for` :488). So the permanent fix is **almost entirely an EMITTER (prompt) change** in
  `build_fit_brief_prompt` (`research-search-recovery:src/health_tech_research_agent/research_runner.py:933`,
  reset block ~:1050–1062, :1334–1339), so that `event_type` is classified by SUBSTANCE (pricing/business-
  model/product-strategy → `strategic-pivot`; IPO/S-1 → `ipo-prep`) and a growth-support add emits
  `opening="unclear"`. Once the emitter is v1.5-correct, the basis-regex bridge is **deleted** and
  `derive_reset_signal` is used as-is.
- **Process flag:** the emitter wording is **LLM-facing → joint-review before build, never self-merged**
  (B0 invariant; `spike_pass1_notes.md` §2). Final emitter wording is recorded in `spike_pass1_notes.md` §2.
- **Risk if missed:** medium-high — the 5 reset regression calls (foodsmart FIRE, grow FIRE, sword/oura/noom
  EXCLUDE; `spike_pass1_notes.md` §1) decide AGENCY pass/fail → whether a D+ company is scored at all.

## D3 — Stage assignment: STAGE_OVERRIDE is a stand-in for the v1.10 designated-series discriminator

- **Honors:** SOT §B4 v1.10 — the series advances ONLY on a round explicitly DESIGNATED the next series; a
  same-series closed priced venture round / extension / top-up / bridge / SAFE / convertible / debt keeps the
  last designated series; an undesignated later round → last confirmed series + `stage_confidence=low`.
- **Spike divergence:** `STAGE_OVERRIDE` (spine:26, applied spine:204) hardcodes the 3 Katelynd-approved
  corrections (signos→series-b, bicycle→series-b, 9amhealth→series-b no-op).
- **VERIFIED GAP in current package:** `funding_stage_from_rounds`
  (`research-search-recovery:src/health_tech_research_agent/structured_evidence.py:200`) currently selects
  **`max(priced, key=(date, stage_rank))`** — the latest-dated priced equity round, normalized by type
  (:213–216). It has **no designated-series concept**: a later same-series priced round that the LLM happens
  to type "series-c" WILL advance the stage. So the v1.10 rule is **NOT implemented** — the hardened mapper
  must (a) capture the round's **series designation explicitly** (not "a later priced round exists"), and
  (b) the **9amhealth case** shows the audit can MISREAD a correctly-captured label, so the designated-series
  signal must be explicit in the evidence, not inferred. Until built, the 3 corrections live as the override.
- **Risk if missed:** high — `spike_pass1_notes.md` §7/§8 note the corrected v1.8 scales are strongly
  stage-driven (a B↔C mislabel swings arr_level 2–5 pts); bicycle and signos are top-of-ranking (bicycle P0,
  signos P3) and both depend on the series-c→series-b correction.

## D4 — business_model: spike bakes fixture-as-truth; the hardened scorer RUNS the classifier

- **Honors:** SOT §B2 v1.4 — LLM extracts who_uses/who_pays → **locked deterministic mapper** emits the label;
  the **human-locked B2B floor (6)** is authoritative OVER the classifier; the 3 documented overrides
  (noom→B2C, signos→B2C minor-employer who_pays over-read, counsel→B2B2C evidence-thin). Fixture v1.3
  regression target: **B2B 6 / B2C 8 / B2B2C 41 = 55** (re-run target 6/8/40 = 54 with firefly deferred),
  7 canonical asserts, `needs_review` expected 0.
- **Spike divergence:** the spine runs **no classifier** — `BUSINESS_MODEL` (spine:21) is the fixture labels
  baked as truth; the README and spine:6 say so. The hardened build **runs the committed classifier** (LLM
  who_uses/who_pays → locked mapper) WITH the human-locked floor authoritative over it.
- **Accepted exceptions (Rule 8 — evidence gap, NOT logic error):** `counsel`/`diana` are **evidence-thin**
  (the regen output under-surfaced their institutional channel; fixture v1.3 Correction log + §B2 v1.4). A
  residual `counsel=B2C` from a live classifier run is an **accepted, explained discrepancy**, not a failure.
- **Build note:** there is currently **NO who_uses/who_pays classifier in the package** — only the OLD
  `business_model_type` (revenue-mechanism axis) in `research_runner.py:1349` and `business_model_classification`
  read by `priority.py`/`taxonomy.py`/`dashboard.py`. The §B2 classifier is a **clean build**, not a re-point.
- **Risk if missed:** medium — the classifier is the PATH Test A linchpin; a floor-miss on a listed company is
  a NON-FAILURE by design (the locked floor catches it), but a wrong consumer/professional read on a
  NON-floored company mis-gates it.

## D5 — PMF scales: confirm parity, not improvisation (CONFIRMED in this pass)

- **Honors:** SOT §B6 v1.8 Scale A / Scale B / geometric round-half-up interp.
- **Spike status: PARITY CONFIRMED.** I diffed the spike tables against the SOT tables:
  - `ARR_SCALE` (spine:103–110) == SOT §B6 Scale A (SOT:385–392), all 6 rows, every cell.
  - `GROWTH_SCALE` (spine:111–117) == SOT §B6 Scale B (SOT:401–407), all 5 rows, every cell.
  - `scale_interp` (spine:123–130) implements the SOT INTERPOLATION RULE (SOT:418–422): geometric
    `s + ln(v/lo)/ln(hi/lo)`, round-half-up via `floor(...+0.5)`, clamp 1–10.
  - `_growth_stage` (spine:120–122) implements the SOT map (series-d-plus → public row).
  The spike's **earlier** improvised `round(10·√(mag/ARR_BEST))` ARR curve and stage-blind % bands
  (`spike_pass1_notes.md` §7) are **gone** — the committed spike already carries the v1.8 scales. The hardened
  scorer carries these tables verbatim; re-confirm the two SOT asserts (SerA $24M→7, $50M→10, $4M→1,
  $39.3M→9; Function +450%/SerB→10, Hinge +51%/public→7) as red tests.

## D6 — (Additional) Strain reads `a2_score`, NOT the full §B7 B1/B2 evidence split

- **Honors:** SOT §B7 (strain 0..+2; B1-structural vs B2-reported with a strict B2 bar; default-low).
- **Spike behavior:** `strain` (spine:185–193) reads only the structured `capability_evidence.a2_score` plus a
  speed-of-scale text regex on `operating_characteristics_finding`. It does **not** implement the full B1/B2
  reported-strain bar (multiple-independent-sources, Reddit-over-Glassdoor, routine-griping-excluded). This is
  a **simplification, not a contradiction** — the SOT B7 strain split is "WORDING-LOCKED," and the spike's
  structured-signal path is a faithful subset. **Hardened decision needed:** does the hardened strain stay
  a2-driven (matching the calibrated thresholds) or implement the full B1/B2 reported bar? Per R1, **changing
  it invalidates the calibrated +2 dial** — so the hardened scorer should stay a2/speed-driven for the
  re-validation run, and any B2-reported expansion is a SEPARATE, post-revalidation change. (Listed as a
  spec-silent item in Section 4, G3.)

---

# Section 3 — Commit-by-commit BUILD PLAN (the thing to approve)

**Where this builds:** all commits below write PACKAGE code on the **`research-search-recovery` lineage** (a
code branch off `research-search-recovery @ 9b4c69a`), NOT on `docs-scoring-sot` and NOT on `phase3-scoping`.
Red→green, one commit per §B stage (split only where noted). New scorer functions live in
`src/health_tech_research_agent/` (proposed new module `scoring.py`, plus the classifier prompt + the §B4
emitter change in `research_runner.py` and the stage-rule change in `structured_evidence.py`).

**Pre-commit-#1 PREREQUISITE (hard, separate from this scoping deliverable):** before commit #1, paste the FULL
text of SOT v1.11 (`git show docs-scoring-sot:specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`) and fixture v1.3
(`git show docs-scoring-sot:specs/business_model_classifier_fixture.md`) back into chat, so the chat-side
reviewing layer has the SOT text in context (it currently has only the fixture, spike code, deliverable, and
notes). SOT-based review ("strain maps to §B7, which says X") cannot be verified blind. A read-only inventory
tolerates that; the build phase does not.

### Commit 1 — Classifier + human-locked floor + overrides (§B2 v1.4, fixture v1.3)
- **Ports:** the locked floor set + the 3 documented overrides (spine:18–22) — as DATA, not as the scoring
  path. The mapper is built clean from SOT §B2:183–186 (`who_uses==professional`→B2B; `who_pays==consumer`→
  B2C; else B2B2C).
- **Build clean:** the who_uses/who_pays LLM extraction prompt (STAGED — live Colab test vs the fixture FIRST,
  per §B9.1) + the deterministic mapper + `business_model_needs_review` on `who_uses_confidence==low` + the
  human-locked-floor OVERRIDE layer (forces B2B for the 6). **No classifier exists in the package today** —
  this is new (the old `business_model_type` is a different axis; do not reuse).
- **Red test:** regression vs `business_model_classifier_fixture.md` — counts **B2B 6 / B2C 8 / B2B2C 40**
  (firefly deferred) ; the **7 canonical asserts** (openevidence→B2B, nourish→B2B2C, zoe→B2C,
  medically-home→B2B, headway→B2B2C, rula→B2B2C, grow-therapy→B2B2C); `needs_review` ≤ 1–2; **counsel
  evidence-thin accepted** (a residual counsel=B2C does not fail the test).
- **Cites:** SOT §B2 v1.4 (SOT:178–231); fixture v1.3.
- **Process:** classifier PROMPT is LLM-facing → joint-review before merge (B0). Mapper + fixture are LOCKED.

### Commit 2 — PATH gate (§B3)
- **Ports:** `path_gate`, `_figure`, `has_any_revenue`, `has_meaningful_scale`, `has_positive_growth`,
  `has_real_institutional_channel`, `_has`, `ABSENT` (spine:28–63) — the logic is faithful; carry intact.
- **Build clean / re-validate:** keep the ROBUST presence-anywhere checks (not prefix); keep the
  employer-direct structural branch (the Function Health §B3 scope-fix); confirm the no-revenue fallback
  (^c10). Wire to the Commit-1 classifier output (not the baked label).
- **Red test:** Test A floors all 6 B2B-floor companies; Test B B2C aliveness (rev|scale|growth); B2B2C
  channel; the no-revenue B2C fallback passes a scale/growth-only company. Reproduce the 17 gate-floored set
  (6 B2B-floor + 11 AGENCY) once Commit 3 lands.
- **Cites:** SOT §B3 (SOT:233–268), §B6.1 fence context.

### Commit 3 — AGENCY gate + reset v1.5 + stage rule v1.10
*(Split into 3a/3b/3c — each is independently testable and 3a is LLM-facing.)*
- **3a — substance-classifying reset EMITTER** (the permanent fix for D2). Change `build_fit_brief_prompt`'s
  reset block (`research_runner.py` ~:1050–1062, :1334–1339) so `event_type` is classified by SUBSTANCE and a
  growth-support add emits `opening="unclear"` (final wording in `spike_pass1_notes.md` §2). Then **delete the
  basis-regex bridge** (spine:69–71 are NOT ported) and use the **existing** `derive_reset_signal`
  (`structured_evidence.py:452`) as the deterministic rule. **LLM-facing → joint-review, not self-merged.**
- **3b — stage rule v1.10 designated-series discriminator** (the permanent fix for D3). Modify
  `funding_stage_from_rounds` (`structured_evidence.py:200`) to advance the series ONLY on a round designated
  the next series; capture `stage_designation` explicitly; same-series/extension/bridge/SAFE/debt keep the
  last designated series; undesignated later round → last confirmed + `stage_confidence=low`. Retire
  `STAGE_OVERRIDE` once this passes signos/bicycle/9amhealth.
- **3c — AGENCY gate** maturity buckets (port `agency_gate` spine:84–98, faithful): public/series-d-plus →
  PASS iff reset else FAIL; seed/pre-seed → FAIL no-rescue; series-a/b/c → PASS; expose the late-C dial flag
  (clean PASS).
- **Red tests:** reset regressions (`spike_pass1_notes.md` §1) — foodsmart FIRE, grow FIRE, sword EXCLUDE
  (pivot-substance), oura EXCLUDE (IPO-prep), noom EXCLUDE (growth-support add); stage corrections —
  signos→series-b, bicycle→series-b, 9amhealth=series-b; D+/public fail-without-reset; seed no-rescue.
- **Cites:** SOT §B4 v1.5 (reset, SOT:301–324) + v1.10 (stage, SOT:279–300); `spike_pass1_notes.md` §1/§2/§8.

### Commit 4 — bg_fit gradient (§B5 v1.7)
- **Ports:** the LOCKED prompt `BG_PROMPT` (b5:26–43, byte-identical to SOT §B5:343–362) + the Colab runner
  shape (b5:46–58). Emits `background_fit` (1–10) + `data_feedback_loop` ("yes"/"no").
- **Build clean:** wire as a package function with the `who_uses==consumer` precondition (SOT §B5:328–329);
  errors recoverable (re-runnable per company).
- **Red test:** the **Nourish "periodic" regression** → bg_fit ≥ 6 (frozen value 8); the data-feedback-loop
  flag fires only on the metabolic/tracking loops (levels/signos/oova/9amhealth per `bg_fit_scores.py`). The
  frozen `BG_FIT` dict (bg_fit_scores.py) is the **validation reference**, NOT a shortcut to skip building the
  step — the hardened step re-runs the prompt and should reproduce the frozen scores within tolerance.
- **Cites:** SOT §B5 v1.7 (SOT:328–374).
- **Process:** prompt is LLM-facing but already LOCKED/validated; confirm parity, joint-review any change.

### Commit 5 — PMF (§B6 v1.8) + LLM growth extractor (R2)
*(The largest commit; split into 5a/5b if review wants.)*
- **5a — scales + interp + assembly** (port verbatim, parity confirmed in D5): `ARR_SCALE`, `GROWTH_SCALE`,
  `scale_interp`, `_arr_stage`, `_growth_stage`, `_money`, `arr_level_score`, `pmf`, the **zero-baseline**
  branch, **derived** scoring, **cap@7 on genuine absence only**, the 40/60 split, neutral-4 for an absent
  half. NO acceleration (confirm `accel=0` everywhere). (spine:100–182.)
- **5b — LLM growth extractor (D1/R2 — build clean, replaces the regex):** an LLM growth-presence judgment
  that separates revenue/$ growth from count growth, enforcing the **§B6.1 fence**. Replaces
  `growth_score`'s regex fence (spine:155–166).
- **Red tests (R2 named fixtures):** **pomelo** must NOT count covered-lives +50%; **outcomes4me** must NOT
  count patient +485%; **season** must FIND ~53.7%. Plus the SOT §B6 scale asserts (SerA $24M→7, $50M→10,
  $4M→1, $39.3M→9; Function +450%/SerB→10, Fay +200%/SerB→10, Hinge +51%/public→7, Omada +53%/public→7, Maven
  +26%/D+→4). Plus: derived figures (Sacra/Latka/Growjo) SCORE; zero-baseline scores via Scale A; cap@7 fires
  only on genuine absence.
- **Cites:** SOT §B6 v1.8 (SOT:376–452) + §B6.1 (SOT:454–497); `spike_pass1_notes.md` §3/§6(R2)/§7.

### Commit 6 — STRAIN (§B7)
- **Ports:** `strain` (spine:185–193) — structured `a2_score` (≥70→2, ≥55→1) + speed-of-scale → 1; default 0.
- **Build/decide:** keep a2/speed-driven for the re-validation run (D6); any full B1/B2 reported-strain bar is
  a SEPARATE post-revalidation change (changing strain invalidates the +2 dial — R1).
- **Red test:** a2≥70→2; a2≥55 OR speed-of-scale→1; absence→0 (default-low). No double-count with reset (B1).
- **Cites:** SOT §B7 (SOT:526–531); B1 no-double-count (SOT:165–176).

### Commit 7 — Assembly + floor rule + thresholds + the 3 human/exception layers (§B7 v1.11)
- **Ports:** `run`'s assembly (`final = bf + pmf + strain`; sort) + `floor_ok = bf>4 AND pmf>4` (spine:214–219);
  the Step-A overlays (assemble:42–45). **Floor gates FIRST:** floor-FAIL = NOT(bf>4 AND pmf>4) → P3 regardless
  of FINAL; tiers apply ONLY to floor-PASS.
- **Build:** thresholds **P0 ≥18 / P1 15–17 / P2 13–14 / P3 <13**; LOCKED dials (40/60, strain +2,
  no-quantified-rate=5, no small-base dampener). The **3 human/exception layers (Rule 6):** Function Health
  P1-override (floor-FAIL by rule, manual P1, flagged); Angle+Oula P3-by-floor (FINAL=14 but floor-FAIL,
  intended episodic/habitual split); counsel/diana evidence-thin (accepted classifier exceptions).
- **Red test:** floor-rule-gates-first (a floor-FAIL with FINAL≥18 is still P3); the threshold boundaries;
  the human-decision overlays produce the deliverable's tier flags.
- **Cites:** SOT §B7 v1.11 (SOT:499–534); `SPIKE_FINAL_RANKING.md` (the target).

### Commit 8 (FINAL) — Threshold RE-VALIDATION (R1)
- **Action:** run the hardened scorer over the 54 and confirm the tiering matches the spike's locked
  deliverable — **P0=4 / P1=6 / P2=6 / P3=38** with the documented exceptions (Function P1-override; Angle/Oula
  P3-by-floor; counsel/diana evidence-thin; the 3 stage corrections; the R2 cases).
- **Bar (R1):** ANY drift in extraction or gate logic from the spike **invalidates the calibrated thresholds**
  → surface EVERY divergence as a calibration-invalidating change requiring re-fit, **not a silent ship**.
  Per R1, drift in the R2 extractor or the stage discriminator is the most likely source — a changed
  pomelo/outcomes4me/season grw, or a different signos/bicycle stage, moves a tier.
- **Output:** a re-validation report (matches / divergences table) handed to chat + Katelynd. If it matches →
  thresholds promoted from SPIKE-PROVISIONAL. If it drifts → re-calibrate, doc-first SOT §B7 bump.
- **Cites:** SOT §B7 v1.11 CALIBRATION CAVEAT R1 (SOT:522–524); `spike_pass1_notes.md` §6(R1)/§9.

---

# Section 4 — Spec gaps & contradictions (hunted explicitly)

### G1 — Spike-beyond-spec
- **`scale_interp` unknown-stage fallback → series-b (spine:119,122).** SOT §B6 maps Series-D/E→series-d-plus
  and Pre-IPO/Public→public but is **silent on what an `unknown`/undeterminable stage scores in PMF**. The
  spike silently defaults to the series-b row. On the 54 every scored company has a clean stage, so it never
  fires — but the hardened scorer will hit it (the stage mapper can now emit `unknown` +
  `stage_confidence=low`). **Resolution (doc-first):** SOT §B6 should state the unknown-stage PMF policy —
  recommend **route to human review / cap, do NOT silently score on a guessed row** (Rule 8). **Blocks
  Commit 5.**
- **`strain` speed-of-scale text regex (spine:190).** The "N0→N / in ~6 / doubled" trigger for +1 is a spike
  heuristic with no exact SOT sentence (SOT §B7 says "speed-of-scale … is a strong STRUCTURAL signal" but
  gives no parser). **Resolution:** acceptable as a faithful subset for re-validation (D6); note it as
  spike-provenance in the SOT if kept. **Blocks nothing** (Commit 6 keeps it for R1 parity).
- **`has_positive_growth` qualitative tokens (spine:44–45) and the no-rate fallbacks (declin→1/flat→3/grow→5,
  spine:168–170).** The grow→5 maps to the SOT "no-quantified-rate growth KEPT 5" dial (SOT:510–511), so it is
  spec-backed; declin→1 and flat→3 have **no explicit SOT anchor**. **Resolution:** add the declining/flat
  no-rate values to SOT §B6/§B7 dial list (low-risk; они only affect already-floored companies). **Blocks
  nothing.**

### G2 — SOT-silent (decisions the hardened scorer is forced to make)
- **Empty-evidence / `None` PMF half (spine:178: missing half → neutral 4).** SOT §B6 specifies the cap@7 for
  genuine absence but is **silent on the neutral value for a SINGLE absent half** (only ARR present, or only
  growth present). The spike uses 4. **Resolution (doc-first):** SOT §B6 should state the single-half-absent
  neutral. **Blocks Commit 5** (it changes pmf for data-gap companies like jasper).
- **Tie-breaking / sort key (spine:219: sort by `(final, pmf)` desc).** SOT §B7 defines tiers but is silent on
  intra-tier ordering. The master spec (`MASTER_REDESIGN_SPEC.md` §3.1) says `final_priority_rank` = sort by
  FINAL — silent on the pmf tiebreak. **Resolution:** harmless; document the (FINAL, pmf) tiebreak in SOT §B7.
  **Blocks nothing.**
- **Strain a2 vs full B1/B2 (D6).** SOT §B7 strain split is "WORDING-LOCKED" but the spike implements only the
  structured a2 path. **Resolution:** SOT §B7 should state that the hardened re-validation strain is a2/speed-
  driven and the full B2-reported bar is deferred. **Blocks nothing** (keep a2 for R1).

### G3 — Three-way (SOT vs fixture vs spike) disagreement
- **None found that is an error.** Checked:
  - **41-vs-40 (fixture vs deliverable/spike):** **NOT a contradiction** (as flagged in the task) — fixture 41
    = full B2B2C roster; deliverable/re-run 40 = same roster with `firefly health` deferred (the lone JSON-bug
    casualty). Internally consistent. Not flagged as an error.
  - **counsel/diana:** fixture v1.3 labels them B2B2C; the spike bakes B2B2C; a live classifier may read B2C
    from thin evidence — this is the **accepted evidence-thin exception (Rule 8)**, documented in fixture v1.3
    Correction log + SOT §B2:226. Not a contradiction.
  - **Rula +100%/SerC base 8 vs anchor 10; Cohere +20%/SerC base 2 vs anchor 3** (SOT §B6:414–416): SOT itself
    flags these as "TWO RESIDUAL ANCHORS UNDER INVESTIGATION — report, don't override"; `spike_pass1_notes.md`
    §7 resolves both as stage-label/stale-input artifacts (Rula pmf=9 stable; Cohere B2B-floored, ranking-moot).
    **Surfaced, already adjudicated "no change" — not an open contradiction.**
  - **Classifier counts vs the spike's baked 50/54 self-classify** (SOT §B2:225–226): the spike self-classifies
    50/54 and scores 4 from locked truth — this is the documented override set, consistent. Not a contradiction.

### G4 — The single highest-leverage doc-first item
**G2's single-absent-half neutral (4) and G1's unknown-stage PMF policy are the two SOT-silent decisions that
the hardened LLM extractor will actually trip** (the spike never did, because its baked stages were all clean
and its regex rarely returned exactly one half). Both **block Commit 5** and should be landed in SOT §B6
**doc-first** before the PMF commit.

---

# HIGHEST-RISK ITEMS (decide doc-first before approving the plan)

Ranked by likelihood of invalidating the R1 threshold transfer if mishandled:

1. **D1 / R2 — the LLM growth extractor (pomelo / outcomes4me / season).** Highest. These three sit on P1/P3
   boundaries; the spike compensates outcomes4me with a `LEAK_DISCOUNTED` overlay. An extractor that
   re-leaks/re-misses changes grw→pmf→FINAL→tier and breaks the deliverable match. The hardened extractor is a
   **clean LLM build**, the biggest new surface, and the most likely drift source. **Doc-first:** confirm the
   §B6.1 fence boundary list is complete before building.
2. **D3 — the v1.10 designated-series stage discriminator.** High. NOT implemented in the current package
   (`funding_stage_from_rounds` just takes the latest-dated priced round). bicycle (P0) and signos (P3) both
   ride the series-c→series-b correction; the v1.8 scales swing 2–5 pts on a B↔C mislabel. The mapper change
   must capture the series DESIGNATION explicitly (9amhealth proves the audit can misread a clean label).
3. **D2 — the substance-classifying reset emitter.** Medium-high. The deterministic rule already exists
   correct in the package (`derive_reset_signal`); the work is an LLM-facing EMITTER prompt change (→
   joint-review). If the emitter doesn't classify substance, sword/oura/noom wrongly fire and 3 D+ companies
   get scored instead of floored.
4. **G2 single-absent-half neutral + G1 unknown-stage PMF policy.** ✅ **RESOLVED doc-first in SOT v1.12**
   (`docs-scoring-sot`, 2026-06-30): §B6 now states the single-absent-half neutral = 4 (RATIFIED, with the
   cap@7 interaction made explicit — the cap never binds in the growth-absent path, so neutral-4 and cap@7 do
   NOT double-penalize) and the unknown-stage policy (RATIFY series-b for R1; route-to-review/cap improvement
   DEFERRED post-R1). Both gate Commit 5; landed before it.
5. **D6 — strain a2 vs full B1/B2.** Low-medium. Keep a2/speed-driven for R1 (changing it invalidates the +2
   dial); defer any B2-reported expansion. Flag so it isn't "improved" mid-build.

**Build-phase prerequisite (restated):** paste FULL **SOT v1.12** (not v1.11 — the three pre-build edits are
in it) + fixture v1.3 text back into chat before Commit 1 — the chat-side reviewer needs the SOT in context to
verify §-based reasoning.

---

# Section 5 — Gate-2 review surface (PHASE-4 CONTEXT — doc-only durability capture)

> **Scope: this section gates NOTHING in Phase-3.** The review surface is built AFTER hardening + the master
> (Phase-4, per `MASTER_REDESIGN_SPEC.md`). It is recorded here only so the Gate-2 review design — the
> thinnest-documented piece of the system, worked out in chat 2026-06-30 — survives the chat boundary. It
> **EXTENDS / SUPERSEDES** the earlier review-experience notes in `MASTER_REDESIGN_SPEC.md` §4: two
> corrections below take precedence over that section's phrasing. No scorer code; no build commit.

## 5.1 The structural principle (state it once, explicitly)
**The ledger is UNIFORM; the review packet is DIFFERENTIATED.** Every company in the batch is a full scored
entry in the scoring-review ledger — gate-floored or not, same schema, same scoring. What differs is the
**review packet**: cards for the companies needing judgment, summary rows for everyone, one-line floor
reasons for the gate-floored. **Same underlying data, three altitudes of attention.** The front end renders
all of it as a VIEW over the structured per-company ledger entry the scoring pipeline emits — **cards are not
hand-built**; card-eligibility is a render-time predicate over stored data, never a filter on what gets
scored.

## 5.2 Correction 1 — floor governs the REVIEW SURFACE, not whether a company is scored
- **Every company gets a full scored + stored ledger entry — including gate-floored ones.** Floor status
  changes only HOW a company is surfaced at Gate 2, never WHETHER it is scored or stored. The hardened ledger
  scores and stores all 54.
- **The spike's "floor before scoring → em-dash the components" was an LLM-CALL OPTIMIZATION, NOT the ledger
  spec.** In the spike, the 17 floored companies are short-circuited before bg_fit/pmf/strain run (to save
  ~17 LLM calls) and rendered with `—` components in `SPIKE_FINAL_RANKING.md`. **Do NOT carry that
  floor-before-scoring shortcut into the hardened ledger as if it were the design.** Card-eligibility is a
  render-time predicate over the FULL stored entry. (Same tiers either way; different LEDGER CONTENTS — and
  the ledger is the thing that has to be right.)
- **Build/R1 implication:** R1 re-validation and the eventual master build must NOT em-dash floored
  components in the ledger. The floored set's components may be computed lazily for cost, but the ledger
  schema and any persisted entry must hold the full scored entry for all 54.

## 5.3 Correction 2 — card-eligibility predicate (supersedes "all floor-eligible scored companies")
```
card  ⟺  model_tier ∈ {P0, P1, P2}   OR   override_candidate == true
```
- **NOT** "all floor-eligible scored companies." A floor-PASS company whose FINAL lands it at model-tier P3
  (e.g. bf=5, pmf=5, strain=0 → FINAL 10, floor-PASS but P3) gets **no card** — it is a summary row like any
  other P3. The card surface is "everything that needs human judgment" = the three real tiers PLUS the
  model's flagged override candidates.
- **Override candidates ALWAYS get a card, even at model-tier P3.** Live example: **Function Health** is
  P3-by-rule (floor-FAIL, bg_fit=4, 2×/yr lab cadence) but a **P1-override candidate** → it gets a card. The
  card is where the accept-vs-override judgment happens, so a flagged override candidate must surface there
  regardless of model-tier.
- This **sharpens** `MASTER_REDESIGN_SPEC.md` §4's "Cards — floor-eligible scored companies + override
  candidates": the precise predicate is model-tier-based (P0/P1/P2), not floor-eligibility-based.

## 5.4 The three altitudes of attention (over the one uniform ledger)
- **Cards** — the eligibility predicate above (P0/P1/P2 ∪ override candidates). The deliberate accept-or-
  override surface. Each card carries:
  - the model's **recommended tier** and where it **diverges from the rule** (e.g. Function: rule P3,
    recommended override → P1);
  - the **four scores** (`bg_fit` / `pmf` / `strain` / `FINAL`), each with a **one-line rationale pulled from
    the research** — the "why" travels with the number;
  - the **flags / caveats surfaced-not-buried, with a severity** (`fence_leak` / `under_extract` / `data_gap`
    / `evidence_thin` / `override_candidate` / `leak_discounted` — the §3.5 controlled vocabulary);
  - the **decision controls** `[accept]` / `[override → reason]`.
- **Summary table** — EVERY company in the batch, one row each: `company · model · stage · tier · FINAL ·
  key flags`. The triage layer: scannable on one screen, sortable / filterable by tier.
- **One-line floor reasons** — the gate-floored P3s appear ONLY on the summary table, as a one-line floor
  reason (e.g. "medically home — B2B floor"; "hinge — agency floor, public"), **no card**. Surfaced
  specifically so a WRONG floor is catchable (glance-and-confirm), not a black hole. **The floor is
  reviewable, not hidden.**

## 5.5 Review routing — `recommended_action` makes a full batch reviewable in one sitting
Per-company pre-sort of attention:
- **`accept`** — clear-cut (strong P0, clean P3-floor) → bulk-approvable.
- **`review_override`** — override candidates + borderline cases → where real judgment time goes.
- **`normal`** — confirm.

So a 54-company batch is reviewable in one sitting: bulk-accept the obvious, spend judgment where it matters.

## 5.6 How input is captured (decision rules)
- **Override reason is strongly prompted, NOT blocked** — saves without one (the user's rigor, not system
  enforcement).
- **The decision changes PRIORITY / TIER only; scores are write-once and never touched** (Rule 8). **Taxonomy**
  (B2B/B2C/B2B2C) is overridable the same way (the counsel/diana-type human corrections, Rule 6).
- **Provenance is OVERRIDE-ONLY, leaning on the GATE INVARIANT** (dashboard presence ⟹ gate-reviewed): "no
  override" automatically means "reviewed and accepted." The user can scan the master and instantly see what
  they changed vs. what the model produced.
- **Every change is append-only HISTORY with dates + reasons** — a later move (e.g. P2→P1 three weeks on) is
  recorded alongside the original call, never overwriting it.

## 5.7 Build-time note (Phase-4, not now) + ledger reconciliation
- Card-eligibility (`model_tier ∈ {P0,P1,P2} OR override_candidate`) is a **render-time predicate**; the
  ledger stores the **full scored entry for all 54** regardless (Correction 1).
- **Cross-reference to `MASTER_REDESIGN_SPEC.md` §3.1 ledger columns** so the review surface and the ledger
  schema stay reconciled when the master is built: `model_priority` (= model_tier) · `decision.human_override`
  · `decision.override_reason` · `final_priority` (derived: override else model) · `provenance` (derived,
  OVERRIDE-ONLY) · `decision.history` (append-only) · `framework_version` (per-entry staleness) ·
  `decision.taxonomy_override` (+ reason). The card renders `model_priority` + the divergence + scores +
  flags; the decision controls write `human_override` / `override_reason` / `taxonomy_override` and append to
  `history`; `final_priority` / `provenance` derive on read.

---

*Phase-3 scoping deliverable (Sections 1–4 + Highest-risk) — read-only; no scorer code, no logic commits.
Section 5 is appended Phase-4 context (the Gate-2 review surface), doc-only, gating nothing in Phase-3.
Branch `phase3-scoping` off `docs-scoring-sot`; `main` untouched; nothing self-merged. HOLD for Katelynd's
approval before Section-3 commit #1. The spike is not the system.*
