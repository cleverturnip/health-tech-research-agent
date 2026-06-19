# Slice 3.7 — Search-Layer Redesign (coverage + evidence quality)

Two read-only audits drove this slice:
- COVERAGE: the four existing searches (funding/payer/outcomes/commercial) are all
  market/financial-facing. The OPERATOR/ORGANIZATIONAL axis — leadership/restructuring
  events (reset) and operating characteristics (capability-fit) — has NO search behind it.
  Reset fires only on incidental mentions (why ZOE returned empty).
- QUALITY: the searches were built under a stale "return exactly 1 bullet / under N words"
  constraint (a ChatGPT-output-era workaround). The field set has ~doubled since (commercial
  alone went from one signal to 6 facts + 4 red-flags), so the high-demand searches are
  evidence-starved — the deterministic derivations run on inputs the LLM inferred from too
  little. The one-bullet cap is below even the current token ceiling, so the model is being
  told to under-deliver.

This slice fixes both as one coherent search-layer change, BEFORE Slice 4 and BEFORE the
run-once regeneration (Slice 4's capability-fit depends on the new operating-characteristics
search; the regeneration needs the whole layer right).

IMPORTANT — this slice AMENDS the capability-fit attribute definitions. See §"Amendment to
Slice 4" below; `specs/slice4_capability_fit_spec.md` should be updated to point here for the
A1/A2 framing (this doc is the source of truth for the reframe).

---

## Cross-cutting decisions

- **Retire the one-bullet constraint** where it doesn't fit. It was a stale workaround;
  gpt-5.4-mini via the responses API has a tunable `max_output_tokens`. Re-budget per
  field-demand, not the legacy cap.
- **Lift token ceilings** on the high-demand searches (commercial + the two operator
  searches) to ~600–900 tokens; keep funding/payer/outcomes leaner. Cost/latency tradeoffs
  are negligible for a run-once regeneration (gpt-5.4-mini is cheap; the batch bottleneck is
  the deliberate WAIT_BETWEEN_WEB_SEARCHES sleeps, not output size).
- **Output discipline for the richer searches:** structured / multi-item, EACH item sourced,
  and "say explicitly if not found" (never invent). Structure + mandatory per-item sourcing
  is the guard against longer output drifting into noise.
- All searches keep `use_web_search=True` (the new operator searches included — reset is a
  current-events signal). Only the fit-brief synthesis stays web-search OFF.

---

## The six searches

### 1. search_funding (re-budget: tighter fact-list)
Feeds maturity_evidence. Keep it compact but as an explicit FACT LIST, each sourced:
funding_stage, ipo_status, ipo_or_filing_date, last_raise_date, last_raise_amount,
total_funding, valuation — and ADD `founding_year` (coverage audit flagged it missing).
Drop the "1 bullet" language; allow a short structured list. Modest token bump if needed.

### 2. search_payer_signal (roughly as-is)
Feeds institutional_distribution_signal. One categorical signal + supporting evidence is
sufficient. Drop the artificial "exactly 1 bullet" language; otherwise unchanged.

### 3. search_outcomes (roughly as-is)
Feeds outcomes_signal. Same as payer — single categorical signal + evidence; drop the
one-bullet language.

### 4. search_commercial_scale (re-budget: the severe mismatch — A-refined)
Feeds revenue_or_arr, paying_customer_count, revenue_per_user, growth_signal,
business_model_type, funding_evidence, and the evidence behind q1–q4.

**A-refined design — the search GATHERS rich evidence; the fit-brief SYNTHESIS answers
q1–q4** (the synthesis has the full company picture, incl. funding, which q3 needs). The fix
for the starved-input problem is NOT moving where q1–q4 are answered — it is making the
search gather evidence rich in the dimensions the red-flags need:
- **Provenance for q4**: every figure tagged with its source TYPE (company-reported /
  third-party estimate w/ name+methodology, e.g. Sacra / promotional-or-unattributed). The
  synthesis can only judge evidence quality if the search recorded where each number came from.
- **Trend/time for q1**: not just a snapshot ("200k subscribers") but direction/history where
  available ("200k, up from 50k in 2023") so the synthesis can read growing/flat/declining.
- The 6 facts each sourced; revenue_per_user with the inputs it was derived from.
Structured multi-fact output, ~600–900 token ceiling. (Result: derive_commercial_signal runs
on q1–q4 answers the synthesis made from real evidence, not guesses.)

### 5. search_org_events (NEW — feeds reset / Slice 3.5)
**Owns: "reset event + opening."** A CURRENT-EVENTS search, recency-bounded to ~the last
12–18 months (reset is a present-moment high-agency opening; a 4-year-old change isn't).
Returns a MULTI-ITEM LIST — one item per distinct event — each with:
- event_type (the Slice 3.5 vocabulary: leadership-change / declared-transformation /
  founder-transition / post-failure-rebuild / restructuring-layoffs / strategic-pivot /
  ma-integration)
- what happened + date + source
- a sentence of context for the opening judgment (forward-build mandate vs. defensive)
"Say explicitly if no qualifying recent events." Multi-item is essential — a single bullet
would re-create the burying problem Slice 3.5 just fixed (ZOE: pivot AND restructuring).
~600–900 token ceiling. Feeds `reset_evidence.reset_events`.

### 6. search_operating_characteristics (NEW — feeds capability-fit A1/A2/A3)
**Owns: "strain evidence" + product-engagement structure.** Per-attribute structure (hunts
A1, A2, A3 evidence deliberately), each item sourced, "say if not found":

- **A1 + A3 — product-engagement structure (shared evidence).** The reframed inquiry: is this
  a digital product with a DAILY / high-frequency engagement loop, do USERS actually engage
  habitually (per app-store reviews / user discussion / retention signal — users reveal
  habituality; marketing claims it), and does the REVENUE MODEL DEPEND on that sustained
  engagement (subscription/usage that dies without retention) vs. one-time/transactional?
  Evidence sources: product + app-store reviews + user discussion (primary), product
  structure. This single line of evidence feeds both A1 and A3.

- **A2 — operational STRAIN (reframed).** NOT "is there operational complexity" (always true
  for any competitive company → no signal). The discriminating signal is EVIDENCE OF
  OPERATIONAL STRAIN: process breaking down under growth, scaling outrunning capacity —
  the sign they need a senior operator. Evidence sources: layoffs/restructuring framed as
  "grew too fast," employee reviews citing chaos / broken process / scaling pains / leadership
  churn, press on operational stumbles (missed launches, quality/service problems tied to
  growth), hiring scrambles. "Say explicitly if no strain evidence found" — absence of strain
  is itself the (low-A2) signal.

~600–900 token ceiling. Note the deliberate TWO-LENS OVERLAP with search_org_events: a
"grew too fast → restructured" fact may surface in both — org_events reads it as a reset
event+opening (→ agency), operating_characteristics reads it as strain (→ capability A2).
Different engine parts, not double-counting.

---

## Amendment to Slice 4 (capability-fit attribute reframe)

This slice supersedes the A1 and A2 framing in `specs/slice4_capability_fit_spec.md`. Update
that spec to point here. The SCORING MODEL is unchanged (equal-thirds average of A1/A2/A3,
0–100 each, bands, persist components for recalibration). Only the attribute DEFINITIONS change:

- **A1 (reframed) — product-engagement structure → data-driven by necessity.** A1 is NOT a
  "do they have a data culture" inquiry (unverifiable; companies self-describe). It is a
  PRODUCT-STRUCTURE question: a product with a daily/habitual engagement loop whose REVENUE
  DEPENDS on sustained engagement is data-driven BY NECESSITY — the economics force it,
  regardless of whether they do it well (doing it badly = the value-add, not a disqualifier,
  per the original spec's asymmetry). Score high when the product is habit-dependent AND
  revenue hangs on retention; low when engagement is periodic/optional or revenue doesn't
  depend on it. (Shares evidence with A3.)

- **A2 (reframed) — operational STRAIN, not complexity.** A2 is NOT "cross-domain complexity
  exists" (the LLM finds this for every competitive company → no discrimination). It is
  EVIDENCE OF OPERATIONAL STRAIN: scaling outrunning process, things breaking under growth —
  the signal that the company needs someone with this operator's skillset. INTENDED BEHAVIOR:
  a healthy, smoothly-scaling, well-run company scores LOW on A2 — the strain IS the
  opportunity, so its absence correctly lowers fit. (Evidence: see search #6.)

- **A3 — unchanged in intent** (digital consumer product where habit/retention is
  load-bearing); now explicitly shares the product-engagement evidence with reframed A1.

Consequence to note when reviewing regenerated data: under reframed A2, a "better" (coping)
company can score LOWER on capability-fit than a struggling one. That is correct and intended.

---

## Build notes
- This is a search-prompt redesign in `build_*`/`search_*` (research_runner.py) + the two new
  search functions, wired into the STEP 7 search sequence (the four findings become six).
- run_company_fit_brief's synthesis prompt may need light updates to consume the richer
  evidence (esp. commercial provenance/trend for q1/q4) and the two new finding inputs — but
  the q1–q4 answers stay in the synthesis (A-refined).
- Token ceilings raised for searches 4/5/6.
- The two new searches add ~2 more web calls per company (with the WAIT_BETWEEN sleeps) —
  note for refresh timing; negligible vs. the run-once cost.
- Tests: prompt-structure tests for each new/changed search (the new searches return the
  expected structured shape; the one-bullet language is gone; founding_year present in
  funding). The derivations (commercial, reset, capability) are already unit-tested; this
  slice changes their INPUT richness, verified live in Colab (ZOE should now surface its
  org event(s) and its strain; a habit-dependent company should show A1/A3 product evidence).
- Sequencing: build + Colab-verify this slice BEFORE Slice 4 (capability-fit consumes search
  #6) and before the regeneration.
