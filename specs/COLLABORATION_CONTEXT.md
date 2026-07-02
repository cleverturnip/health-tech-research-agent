# Collaboration Context — Health-Tech Research Agent

> **How to use this file:** When starting a NEW chat with Claude, either upload this file
> to your first message or paste its full contents, and say: *"I'm continuing a project —
> please read this context doc, and confirm you understand where we are before we continue."*
> A new chat cannot access my GitHub repo or local files directly, so it relies on this
> pasted/uploaded text. (Claude Code, separately, CAN access the repo — the file paths below
> are for handing work to Claude Code and for my own reference.)

## Who I am / how we work
I'm Katelynd (GitHub: cleverturnip), a non-coder building a health-tech company
research-and-prioritization agent. Repo: github.com/cleverturnip/health-tech-research-agent

Working model that works for me: **design and strategize with Claude in chat; hand finished
specs/prompts to Claude Code** (which has live repo access) to execute. I run live research in
a **Colab notebook** and keep master data in Google Drive. Please keep this division: Claude
helps me think, design, and review; Claude Code builds.

## North Star — the end-state flow (every decision moves toward this)
The destination is a research agent that runs as a mostly-autonomous flow bounded by exactly
TWO human-in-the-loop gates:

1. User defines the parameters for the kinds of companies to research → LLM offers candidate
   suggestions → **[GATE 1]** user approves/edits the suggestions.
2. From that approval, a FULLY AUTONOMOUS segment runs with NO user input: it researches,
   outputs documentation, reviews its own documentation, and produces recommended adjustments →
   **[GATE 2]** user reviews the recommendations and edits/approves.
3. From that approval, a second FULLY AUTONOMOUS segment runs with NO user input: it outputs the
   dashboard.

**The load-bearing design fact: between GATE 1 and GATE 2, and between GATE 2 and the dashboard,
there is ZERO user input.** Those segments must be architected to run unattended end-to-end — a
problem inside a segment cannot rely on a human noticing it mid-flow. It must be handled
autonomously or surfaced AT THE NEXT GATE for review. When architecting any change that lives
inside an autonomous segment, design for "no one is watching this run" — the flag-for-review
pattern (e.g. capability_needs_review routing a row to human attention) is how an autonomous
segment defers a judgment to a gate instead of stalling or guessing.

**Disciplines to maintain:**
- Investigate (read-only) → plan (no code) → implement red→green, in small reviewable commits.
- Never weaken a validation gate to make something pass.
- Capture every decision durably in the repo (specs/tracker/runbook) — nothing important
  lives only in chat.
- The single full data regeneration is **run-once** — everything must be right before it,
  because re-running is expensive.
- Prompt wording for any LLM-facing change is the highest-stakes review — design it together
  before Claude Code builds it.
- Architecture principle ("Rule 7"): the LLM gathers EVIDENCE; deterministic rules DECIDE.
  Persist evidence components as columns so labels/signals are recomputable without re-research.
- Absence is an upper bound, not a measurement ("Rule 8"): a blank or "not found" in our OWN
  output means the data isn't IN our output — it does NOT establish the data doesn't exist.
  "Truly absent" and "present but our search/pass missed it" produce an IDENTICAL blank. So never
  attribute a cause to an empty field from the output alone; that's a ceiling on non-existence, not
  a count of it. Convert the bound to a measurement with a live test that actually goes looking
  (e.g. a repeat-N variance probe) BEFORE building on the attribution. This caught three wrong
  calls in the research-layer work (revenue "non-disclosure", "weak prompt", "token starvation" —
  all falsified by live re-runs; the real cause was web-search execution variance).
- Every temporary measure is built toward the North Star end state. Testing scaffolding and
  partial builds (e.g. temporary Colab cells to define a batch before the front end exists) must
  minimize friction for the eventual autonomous flow — solve the immediate step in the shape the
  end state will reuse, not in a throwaway shape that has to be undone later.
- The scoring + priority framework has ONE source of truth:
  `specs/SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md` (FRAMEWORK_VERSION-stamped). Any scoring-logic
  decision changes the DOC FIRST (the version bumps), and Claude Code commits the doc-update as
  its own commit BEFORE building anything that depends on it. The doc-commit IS the sync; the
  build references the committed doc. If a locked decision isn't in the doc, it isn't locked.
- Both the research-layer and scoring work cite the framework version they were built against
  ("built against FRAMEWORK_VERSION vN"). Output citing a superseded version is an instant
  staleness flag — a mismatch becomes VISIBLE instead of relying on someone remembering it.

## Source-of-truth files (in the repo — I can paste these into chat, or hand them to Claude Code)
1. `PROJECT_TRACKER.md` — current state, done, next.
2. `specs/phase2_refresh_runbook.md` — pre-regeneration checklist/reminders.
3. Slice specs: `specs/slice2_structured_evidence_spec.md`,
   `specs/slice3_reset_researched_spec.md`, `specs/slice3_addendum_multi_event_reset.md`,
   `specs/slice3_7_search_layer_redesign_spec.md`, `specs/slice4_capability_fit_spec.md`.
4. Engine: `specs/candidate_priority_reference_spec.md` and
   `src/health_tech_research_agent/candidate_priority.py`.
5. Research-layer (branch `research-search-recovery`): `specs/search_recovery_retry_union_spec.md`,
   `specs/all_fields_blink_probe_spec.md`, `specs/claude_code_growthrate_derive.md`; findings in
   `audits/` (`research_prompt_audit.md`, `research_revenue_cause_isolation_findings.md`,
   `revenue_live_validation_findings.md`, `all_fields_probe_findings.md`).

If a new chat needs full detail, I'll paste the relevant spec.

## Where things stand
The **back-half rebuild** is in progress. Flow goal: research → score → prioritize →
dashboard, all in the package, on trustworthy regenerated data. (The front-half — LLM company
discovery, dedup, triage, first approval gate, UI — is a separate, later, unstarted track.)

**How this project got here (why old-flow cells are stale):** This began as a legacy Colab flow
built with ChatGPT, where the real logic lived only in the ChatGPT conversation and in many
(often temporary) Colab cells — causing version-control problems and large inefficiencies. The
move to Git + Claude Code is the cleanup of that working flow. We have fixed a lot of it, but
EXPECT TO KEEP FINDING old-flow issues as each step touches a new part of the notebook (e.g. an
old-flow cell still at a pre-slice state that never received later wiring). Finding such gaps is
normal and anticipated — investigate, don't assume the notebook matches the package.

**Done / merged to main:**
- Phase 1 dashboard rebuild (live-validated).
- Candidate-priority engine — logic complete and correct (reset reads a researched field; P0
  accepts strong commercial OR institutional; thresholds pinned; vocabulary reconciled). On main
  this is still the INTERIM capability bridge (`CANDIDATE_FRAMEWORK_VERSION = "V4.2-interim"`,
  capability-fit == katelynd_role_fit_score) and INERT (does not write final_priority_level —
  Commit 5 held). **Slice 4 (below) makes it real.**
- Slice 1: research runner extracted into the package (faithful + per-company error
  recovery), Colab-verified.
- Slice 2: structured maturity + commercial evidence (deterministic derivation; the Function
  maturity-mislabel fix and the Solace funding-as-commercial fix), Colab-verified.
- Slice 3 + 3.5: reset as a researched field, multi-event (per-event opening evaluation so a
  pivot can't bury a coexisting restructuring), Colab-verified.
- Slice 3.7: search-layer redesign — two operator searches (`search_org_events`,
  `search_operating_characteristics`) + commercial/funding re-budget + REQUIRED_RESEARCH_COLUMNS
  7→9. Merged via PR #36.

**Slice 4 — MERGED to main (PR #38); the V4.2 regen ran on it** (the pre-regen STEP 10/12
master-landing reconciliation that had gated the merge is complete):
- Slice 4 — real capability-fit: three-attribute A1/A2/A3 rubric replacing the role_fit bridge,
  built on Slice 3.7's operating-characteristics search; gate-time A1/A3 no-double-count recompute
  for reset-lifted scale-ups; engine repoint to REAL (`CANDIDATE_FRAMEWORK_VERSION = "V4.2"`,
  `capability_fit_score` → `katelynd_capability_fit_score`) + suppression guard. Six commits,
  Colab-verified (ZOE 83 / Function Health 32; live multi-event reset fire on Function Health).
- Pre-regen master-completeness — engine-input signals (reset, scale signals, Slice 2 components,
  capability) carried to the master via `optional_model_cols`, so the regenerated master is
  engine-ready.
- Net engine state: REAL (V4.2) merged; **Commit 5** (write `final_priority_level`) is now
  **RE-GATED behind the SECOND (recovery-enabled) regen** (see the 2026-06-26 correction) — the
  engine stays INERT until Commit 5, which now waits on trustworthy data.

**Build order (⚠️ PARTLY SUPERSEDED 2026-06-26 — regen #1 is done; Commit 5 is now re-gated behind
the SECOND, recovery-enabled regen per *Immediate next action*. Kept for history):**
1. ✅ **Full data regeneration** — DONE (run-once, 2026-06-24). Canonical 55-company V4.2 master.
2. ✅ **Field-landing remediation** — DONE (PR #41). Re-landed the role/timing + taxonomy-LLM clusters
   the inline STEP 10 build dropped from the summary→master landing (blank-only, completeness +
   per-field read-back guards, via `reland.py`); cleared the Commit 5 engine-input gate.
3. **Commit 5** — wire candidate→final_priority_level authority + fix false "Human Reviewed"
   labeling + sticky reviewed_priority_level auto-seed. **NEXT** (unblocked). Locked design:
   `candidate_priority_reference_spec.md` §10.
4. **Commit 6 / master remediation**, then **calibration** (judge too-strict/too-loose only
   against trusted regenerated data — NOT before).
5. **Post-migration cleanup pass** — colab_workflow.py AND the notebook old-flow cells (prune
   superseded steps/dead code incl. the sheet-queue STEP 21–25; tag residual reset-flavored
   text-scans like `_rt_has_high_agency_exception`). Deferred until the back-half migration
   completes.

**Per-slice Colab reconciliation (standing step):** After a slice's package work merges, mirror
its changes into the live-region notebook (the inline-list → run_research_batch path; NOT the
old-flow sheet-queue cells, which are superseded) and Colab-verify before the slice counts as
complete. Scope reconciliation to the live region; old-flow cells are touched only where the live
path actually depends on them (e.g. the shared STEP 10/12 master-landing pipeline).

## Verification pattern
Code logic is proven offline (red→green unit tests). Notebook wiring and real-LLM-output
behavior can only be proven by a live Colab run — so each pipeline slice has a "diff looks
right here, Colab is the real proof" step, and I run the Colab checklist before merging.

**A slice is not "done" at package-green.** "Done" = package logic green (red→green unit tests)
PLUS the package changes mirrored into the live-region notebook cells (reconciliation) PLUS a
live Colab run proving the notebook wiring (the "Colab is the real proof" step). All three.
Package-green alone is necessary, not sufficient — the notebook can be a full slice or more
behind the package, and that gap is invisible until reconciliation + a live run surface it.

**ZOE** is the canonical reset test case; **Function Health** is the canonical
maturity/commercial test case.

**Intent-to-action confirmation (process rule).** When a recorded design intent is not directly,
unambiguously actionable — i.e. turning it into a concrete rule, threshold, or mechanism requires choosing
among interpretations — STOP and confirm the exact translation before building or documenting it. Do NOT
fill the gap with the most plausible reading, even when one seems obvious: the plausible-but-wrong
interpretation is the recurring failure mode — it passes review because it reads reasonably, and only a live
run or a deterministic check later exposes the substitution. This applies with extra force when a number or
term could attach to more than one quantity — name which quantity explicitly (e.g. the boundary-detector
"±2" meant score-MOVEMENT run-to-run, but was mis-encoded as distance-from-BOUNDARY; two different rules
sharing the same number — the mis-encoding collapsed P2 and was caught only by a deterministic pre-build
check). **Test:** if you cannot state the rule in a way the human would recognize as EXACTLY what they
meant, you are interpreting, not implementing — surface it. (Sits alongside the project's other working-
discipline rules: doc-first, byte-level sign-off, test-then-ratify.)

## Immediate next action (update this line each time I start a new chat)

> **PHASE-3 HARDENING COMPLETE + MERGED TO MAIN (2026-07-02).** The §B scorer is committed package code at
> framework **v1.25**, R1 re-validated by name (tag `v1.25-phase3-complete`; SOT v1.25 +
> `PHASE3_PROCESS_HISTORY.md` on `main`; spike deleted). **NEXT = the Phase-4 scoring-review LEDGER / Gate-2
> review surface — DOC-FIRST, in a fresh chat.** Design it against `MASTER_REDESIGN_SPEC.md` §4 + §3.1 (the
> ledger columns) and `PHASE3_HARDENING_PLAN.md` **Section 5** (the Gate-2 review-surface scoping: uniform
> ledger, differentiated review packet, floor governs the review SURFACE not whether a company is scored). Do
> NOT scaffold by guess — spec it first, byte-level sign-off, then build.
>
> **OWNED FIRST TASKS for that chat (not just gaps):**
> 1. **Write a "how it works" entry-point doc.** There is NO single narrative that walks a fresh reader through
>    the scoring pipeline end-to-end — classifier → PATH → AGENCY → bg (N=4 avg) → growth-BAND → PMF blend →
>    strain → floor → override → threshold → flags — plus how to run R1. Write it (a top-level overview / README
>    or a `§0` in the SOT) so the system is legible without any chat history. Division of labor: the SOT holds
>    the *rules*, `PHASE3_PROCESS_HISTORY.md` holds the *why*, this new doc holds the *walkthrough*.
> 2. **Make FLOORED-vs-LOW-SCORE legible in the ledger.** `bg=None` currently CONFLATES "correctly gated
>    B2B/non-consumer → FLOORED (gated)" with "consumer-but-weak-habit → LOW bg score (3–4, capped not gated)."
>    The ledger must expose this distinction per company (Katelynd's explicit, carried requirement).
>
> **WATCH-ITEM (document in the ledger review, NOT a scoring fix):** several HIGH bands rest on GetLatka
> `$0→$N` single-source series where "$0 in year one" may reflect the estimator having no early-year data
> rather than a genuine zero — a data-credibility item (`fay`/`foodsmart`/`nourish`/`berry street`/`summer`/
> `visana`). See `PHASE3_PROCESS_HISTORY.md` "Known watch-items."

> **MASTER REDESIGN RECONCILED + COMMITTED (2026-06-30).** `MASTER_REDESIGN_SPEC.md` (RECONCILED v1) is the
> committed target: the master becomes the **GATE-2 scoring-review ledger** (Option 2), with a clean
> from-scratch priority model (`model_priority`/`human_override`/`final_priority`/override-only `provenance`/
> `history`/`framework_version`/`taxonomy_override`), the GATE INVARIANT + Rule-6/8 clause, §B-supersedes-
> candidate_priority, and the cards+summary review packet (extends `build_review_packet`, honors Rule 3).
> **NEXT = Phase-3 hardening** builds the §B scorer (per `spike_pass1_notes.md` R1/§9) → then the ledger →
> then the dashboard, all against this spec. (Cross-branch: this annotation + the Commit-5/6 supersession +
> the CLAUDE.md status update live on `docs-scoring-sot`; sync to `research-search-recovery` when adopted.)

> **PASS-2 COMPLETE — Phase-2 spike retired (2026-06-29).** The SECOND (recovery-enabled) regen CSV
> (`v42_full_regen…full56_checkpoint_FINAL`, 54 of 55; `firefly health` + `videahealth` deferred) was scored
> by the disposable Phase-2 SPIKE; the framework is now fully pressure-tested, calibrated, and committed to
> the SOT (**v1.11**): classifier TRUSTED (human-locked B2B floor §B2 v1.4 + 3 overrides); RESET §B4 v1.5;
> bg_fit §B5 v1.7 LOCKED (Nourish regression passed); PMF Scale A + Scale B + geometric interp §B6 v1.8
> (acceleration removed); stage rule §B4 v1.10 (designated-series); THRESHOLDS + dials §B7 v1.11 LOCKED
> (P0 ≥18 / P1 15-17 / P2 13-14 / P3 <13, floor-rule-gates-first). Final tiered deliverable:
> `SPIKE_FINAL_RANKING.md` (P0=4 / P1=6 / P2=6 / P3=38 = 54; SPIKE OUTPUT — disposable). 2 human decisions
> recorded (Function P1-override; Angle/Oula P3-by-floor). **NEXT = Phase-3 hardening:** build the scorer as
> committed package code per R1 + `spike_pass1_notes.md §9` (carry the spike's logic intact, then RE-VALIDATE
> thresholds against the hardened scorer). The spike is NOT the system. Non-normative records:
> `spike_pass1_notes.md` (on `docs-scoring-sot`).

> ⚠️ **STATUS CORRECTED 2026-06-26 — there are TWO run-once regens; do not conflate them.**
> The 2026-06-24 V4.2 regen (below) is the FIRST. A subsequent **research-layer thread** discovered that
> the V4.2 master's DATA is not trustworthy (~42% empty revenue, plus recoverable figures missing across
> other fields — root cause: web-search EXECUTION VARIANCE, not non-disclosure; the canonical Pelago
> "genuine absence" was falsified live, Rule 8). That discovery **supersedes** the old "Commit 5 →
> calibrate" next-step: calibration must NOT run against the V4.2 master. A **SECOND run-once regen** —
> on recovery-enabled data (the `search_with_recovery` mechanism) — is now the gate before calibration.
> See "## RESEARCH-LAYER THREAD (in flight)" below for the live state and the exact open decision.

**FIRST regen — COMPLETE (2026-06-24).** The master is a clean-slate **55-company V4.2 regeneration** —
landed + read-back verified (55 inserts / 0 updates; change log all `new_company_added`). ⚠️ A follow-up
audit caught that that read-back checked column *presence*, not *population* — two LLM-JSON clusters
(role/timing + taxonomy-LLM) had landed BLANK; **re-landed 2026-06-24 via `reland.py` / PR #41**. Every
row is staged **`New batch - needs review`**. **`videahealth` is deliberately absent** — a transient
fit-brief `JSONDecodeError` dropped it; excluded, JSON-retry hardening scheduled.

How it landed (gate all ✅): `slice4-capability-fit` merged to main (PR #38); STEP 10A schema-drop fixed
(9-col); research via inline-list → `run_research_batch` (WAIT=120 + item-8 guard); STEP 12 dry-run HARD
GATE passed; one-way `DRY_RUN` flip → single real write → read-back. Full play-by-play in
`regen_execution_runsheet.md`.

> ⚠️ **COMMIT 5 / COMMIT 6 SUPERSEDED by the ledger (`MASTER_REDESIGN_SPEC.md`, RECONCILED v1, 2026-06-30).**
> The master is now the **GATE-2 scoring-review ledger** (Option 2 — the ONE master, superseding the V4.2/V1
> data master; raw research data lives durably in the research output). The **§B scoring system** (not
> `candidate_priority`) is the master's priority source → `model_priority`; **Commit 5's "wire candidate →
> `final_priority_level`" is OBSOLETE**, and the old six priority columns retire in favor of a clean
> from-scratch model (`model_priority` / `human_override` / `final_priority` / override-only `provenance` /
> `history` / `framework_version` / `taxonomy_override`). **GATE 2 = the ledger review.** Two hard rules now
> stated in the redesign spec: **(Rule-6/8 clause)** the decision block edits PRIORITY + TAXONOMY only (Rule
> 6); scores + research data are write-once, never hand-edited (Rule 8, fix via upstream regen). **(GATE
> INVARIANT)** presence in the dashboard ⟹ the entry passed GATE-2 review — nothing reaches the dashboard
> un-gated (this is what makes override-only provenance unambiguous). The blocks below are HISTORICAL.

**Immediate next is NO LONGER "Commit 5 → calibrate" — it is the research-layer thread, THEN a second
regen, THEN Commit 5/calibration.** The engine/calibration track below is still the eventual path, but it
is GATED behind the second regen (calibrating on untrustworthy data would bake in wrong thresholds — the
exact `^c10` / "calibrate only against trusted data" rule).
- **Commit 5** — wire the candidate engine → `final_priority_level` (+ fix false "Human Reviewed"
  labeling + sticky reviewed_priority auto-seed). Was marked unblocked on 2026-06-24, but is now
  **re-gated behind the second (recovery-enabled) regen** — the landed V4.2 master's data is the thing
  the research thread is fixing. `final_priority_level` is currently BLANK; Commit 5 populates it AFTER
  trustworthy data exists.
- → **Commit 6 / master remediation** → **calibration** (calibrate the logic against the *second-regen*
  master, do NOT hand-edit the master, per Rule 8).
- **Dashboard is LAST** — built around `final_priority_level/_code/_rank`, all blank until Commit 5 +
  calibration on trustworthy data.

## RESEARCH-LAYER THREAD (in flight — the current work; gates the second regen)
**Why it exists:** ~42% of the V4.2 master had empty revenue. Root cause PROVEN via live probes:
web-search execution variance (searches coin-flip on reaching the page holding a figure; byte-identical
runs blink). **Fix built + live-validated:** `search_with_recovery` — a field-agnostic always-run-N +
union + provenance mechanism; per-field config (presence check + source-directed retry prompt + N). On
branch `research-search-recovery`, **pushed to origin for the Colab runs (NOT merged to main)**,
~268 tests green; the Group-1 configs (growth-rate, paying-count) + the re-measure harness are committed.

**Per-field scoping status (toward knowing the COMPLETE field set before the second regen):**
- revenue — enabled, N=5 (kept high for the run-once regen's corroboration).
- paying-customer-count — re-measured clean → enable N=5 (Tightening 2 validated: paying employer-clients
  kept distinct from non-paying covered-lives).
- growth-rate — the hard one (worst-case 20% at the usable bar; rates exist as RAW dated points more than
  as stated rates). **OPEN DECISION:** stop-on-hit REJECTED (growth = 60% of PMF; first-hit luck must not
  pick a weak rate). Fix = refine-to-derive (compute the rate from dated endpoints, mandatory
  show-the-inputs + period), re-measure, then size N via ALWAYS-RUN-N (never stop-on-hit). Drafted prompt:
  `specs/claude_code_growthrate_derive.md` — **committed to the repo + received by Claude Code 2026-06-26;
  the refine-to-derive WORDING is NOT yet built (awaiting the joint review the doc asks for).**
- valuation, revenue-per-user (Group 2) — flagged LOWER-STAKES; not yet designed; match rigor to stakes.
- diffuse fields (payer/outcomes/org-events/strain) + capability_fit — single-pass (diffuse "robust" from
  BLIND measurement is PROVISIONAL, not final — Pelago lesson).

**Sequence:** enable paying-count → growth-rate derive (joint wording) → re-measure → set growth N →
Group 2 → enable all + set permanent per-field N → **SECOND run-once regen on recovery-enabled data** →
THEN Commit 5 → Commit 6 → calibration → dashboard.

**Verified finding parked for the PATH-gate (scoring) work:** `payer_institutional` is too narrowly
scoped — it detects PAYER-reimbursement only, but PATH Test B needs "ANY real institutional/B2B2C
channel." Function Health proves the gap (real EMPLOYER-DIRECT channel "Function for Work", but
insurance-free). When building PATH Test B, cover employer-direct, not just payer-reimbursed.

**Deferred cleanup — NOW ACTIONABLE (run-once done, so unblocked):**
- **ROOT fix #1** — collapse the inline STEP 12 into a call to the package `master_update` function
  (ONE implementation; the cure for the duplication behind this session's debugging marathon).
- **ROOT fix #2** — port the 10A 9-column schema fix to the `colab_workflow.py` mirror (still
  notebook-only — the repo copy is a trap until ported).
- **Fit-brief JSON-retry hardening** — retry/repair the fit brief on `JSONDecodeError` (the
  videahealth-class failure; cost hinge + videahealth this run). Task chip queued.

Runbook cross-reference: **STEP 21/23 are RESOLVED as not-live** — old-flow sheet queue, superseded
by the inline-list → run_research_batch path; deferred to the post-migration cleanup pass.

### Decisions locked during the Slice 3.7 work (carry these forward)
- **Both new search prompts are WORDING-LOCKED** (highest-stakes review, done jointly in chat):
  - search_operating_characteristics: engagement-vs-revenue evidence weighting; hybrid-revenue
    handling (e.g. Oura = one-time hardware + recurring membership reported as components, NOT
    collapsed to "has a subscription" — the one-time portion dilutes retention-dependence, which
    matters for A1); B1 structural / B2 reported strain split with a STRICT bar on B2 (multiple
    independent sources on the SAME breakdown; prefer Reddit/forums over Glassdoor; routine
    griping does NOT count; speed-of-scale e.g. 100->500 staff in 6mo is a strong structural
    signal, reported as evidence not verdict); absence-is-a-finding default (default LOW unless
    strain clearly demonstrated); strength-tagged (STRONG/MODERATE/WEAK) three-heading output.
  - search_org_events: recency-bounded (~12-18mo, prompt-only); multi-item list (each distinct
    event separately, so a loud pivot can't bury a co-occurring restructuring — the ZOE case);
    per-event high-agency-opening judgment (yes/no/unclear); + a weighting bullet preferring
    COSTLY, REVEALED actions (real CEO change, actual reorg) over the company's own PR framing.
- **Reset = search GATHERS, synthesis EMITS** the canonical reset_events (single emitter). The
  synthesis must NOT re-derive/override the opening; the deterministic rule decides firing.
- **Scope: 3.7 only GATHERS operating-characteristics evidence; Slice 4 SCORES A1/A2/A3.** 3.7
  adds no capability output fields.
- **REQUIRED_RESEARCH_COLUMNS grew by exactly 2** -> pre-3.7 checkpoint rows are now "incomplete"
  and get re-researched on resume. Accepted (no incremental passes before the run-once regen).
- **Recency (~12-18mo) stays PROMPT-ONLY** for 3.7; do NOT touch the frozen Slice 3.5 derivation.
  If a Colab run later shows stale events leaking, add a targeted code date-filter THEN, with its
  own test.
- **Two-lens overlap** (a "grew too fast -> restructured" fact can surface in both org_events ->
  reset/agency and operating_characteristics -> A2 strain) is intentional, not double-counting.
  **Note forward for Slice 4:** ensure that same event isn't effectively double-weighted when A2
  strain and reset both feed a combined priority signal.
- **Commit 3/4 scope decision (open for revisit):** the two new findings are persisted in the
  checkpoint/archive but NOT propagated into the review-summary builder, the taxonomy haystack
  (deliberately — market-segment keyword matching; org/operating evidence would add noise), the
  dashboard, or the summary->master parse loop. They're available for Slice 4. PARKED QUESTION:
  surface the two findings in the HUMAN REVIEW PACKET? Decision: leave out until Slice 4 makes the
  evidence mean something; revisit then.
- **A-refined commercial boundary:** the commercial search gathers richer evidence (provenance +
  trend); q1-q4 judging stays in the fit-brief synthesis (which also sees funding, for q3).

### Verification anchors (unchanged)
ZOE = canonical reset test case; Function Health = canonical maturity/commercial test case.
Code logic proven offline (red->green); notebook wiring + real-LLM behavior proven only by a
live Colab run.

### Side task PARKED (not started): Claude Code approval-prompt hook
Constant approval prompts during Claude Code runs. The naive command allowlist won't work because
Claude Code's diagnostic commands are chained/piped (cd && echo && python3 ... | tail, with
2>&1), which the simple allow-pattern matcher doesn't reliably match. Solution designed: a
PreToolUse hook that auto-approves a bash command ONLY IF every clause is read-only, and forces
ASK if ANY clause is state-changing (load-bearing case: a pytest bundled with git commit --amend
must ASK), plus an independent settings.json deny list (rm / git push / git reset --hard / git
clean / curl / wget / .env reads) as a backstop the hook can't weaken.
**Full spec: `spec_pretooluse_autoapprove_hook.md`** (committed to the repo alongside this file;
upload it to the chat too when picking this up). Includes the 9-example real command corpus as
regression fixtures, the read-only verb allowlist, the sharp edges (2>&1 vs real-file redirects,
sed -i, find -delete, command substitution, the pytest/python3-c judgment call), the build plan,
acceptance criteria, and 4 open questions. Re-verify the hook schema against live Claude Code docs
before building. (acceptEdits mode is currently ON as the interim measure — covers edit prompts,
not bash prompts.)
