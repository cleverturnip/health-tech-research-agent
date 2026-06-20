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

## Source-of-truth files (in the repo — I can paste these into chat, or hand them to Claude Code)
1. `PROJECT_TRACKER.md` — current state, done, next.
2. `specs/phase2_refresh_runbook.md` — pre-regeneration checklist/reminders.
3. Slice specs: `specs/slice2_structured_evidence_spec.md`,
   `specs/slice3_reset_researched_spec.md`, `specs/slice3_addendum_multi_event_reset.md`,
   `specs/slice3_7_search_layer_redesign_spec.md`, `specs/slice4_capability_fit_spec.md`.
4. Engine: `specs/candidate_priority_reference_spec.md` and
   `src/health_tech_research_agent/candidate_priority.py`.

If a new chat needs full detail, I'll paste the relevant spec.

## Where things stand
The **back-half rebuild** is in progress. Flow goal: research → score → prioritize →
dashboard, all in the package, on trustworthy regenerated data. (The front-half — LLM company
discovery, dedup, triage, first approval gate, UI — is a separate, later, unstarted track.)

**Done / merged to main:**
- Phase 1 dashboard rebuild (live-validated).
- Candidate-priority engine — logic complete and correct (reset reads a researched field; P0
  accepts strong commercial OR institutional; thresholds pinned; vocabulary reconciled).
  Currently INTERIM (capability-fit = role_fit bridge) and INERT (does not yet write
  final_priority_level — Commit 5 is held).
- Slice 1: research runner extracted into the package (faithful + per-company error
  recovery), Colab-verified.
- Slice 2: structured maturity + commercial evidence (deterministic derivation; the Function
  maturity-mislabel fix and the Solace funding-as-commercial fix), Colab-verified.
- Slice 3 + 3.5: reset as a researched field, multi-event (per-event opening evaluation so a
  pivot can't bury a coexisting restructuring), Colab-verified.

**Specced, not yet built (in build order):**
1. **Search-layer redesign (slice 3.7)** — `slice3_7_search_layer_redesign_spec.md`. Fixes two
   audit findings: (a) coverage — the four existing searches are all market/financial; the
   operator/organizational axis had NO search (why reset/ZOE came back empty); (b) quality — a
   stale "one-bullet" constraint starved the high-demand searches. Adds two new searches
   (search_org_events → reset; search_operating_characteristics → capability-fit), re-budgets
   commercial (A-refined: search gathers provenance+trend evidence, synthesis answers q1–q4)
   and funding (+founding_year), retires the one-bullet cap, raises token ceilings. **This spec
   also AMENDS Slice 4's A1/A2 definitions:** A1 reframed = product-engagement structure
   (habit-dependent + revenue-dependent → data-driven by necessity); A2 reframed = operational
   STRAIN (process breaking under growth), NOT "complexity exists" (which is always true → no
   signal). A healthy coping company correctly scores LOW on A2.
   **STATUS: this is the task in flight.** Claude Code was asked to commit the spec (+ amend
   the Slice 4 spec), then plan the build (plan-first, no code), stopping for my review of the
   two new search prompts' wording.
2. **Slice 4** — real capability-fit (three-attribute rubric, reframed A1/A2 per above),
   replacing the role_fit bridge, built against the new operating-characteristics search.
   Completing it flips the engine interim→real and unblocks Commit 5.
3. **Full data regeneration** — run-once, only after Slices 3.7 + 4. Runbook reminders:
   restore WAIT_BETWEEN_WEB_SEARCHES=120 (dropped to 5 for testing); delete throwaway test
   checkpoints (Clair/Oura); STEP 26 rescore spot-check; verify multi-event reset fires on a
   known-reset company (ZOE).
4. **Commit 5** — wire candidate→final_priority_level authority + fix false "Human Reviewed"
   labeling + sticky reviewed_priority_level auto-seed. Held until real capability-fit exists.
5. **Commit 6 / master remediation**, then **calibration** (judge too-strict/too-loose only
   against trusted regenerated data — NOT before).
6. **Post-migration cleanup pass** on colab_workflow.py (prune superseded steps/dead code;
   tag residual reset-flavored text-scans like `_rt_has_high_agency_exception`). Deferred
   until the back-half migration completes.

## Verification pattern
Code logic is proven offline (red→green unit tests). Notebook wiring and real-LLM-output
behavior can only be proven by a live Colab run — so each pipeline slice has a "diff looks
right here, Colab is the real proof" step, and I run the Colab checklist before merging.
**ZOE** is the canonical reset test case; **Function Health** is the canonical
maturity/commercial test case.

## Immediate next action (update this line each time I start a new chat)
**Slice 3.7 (search-layer redesign) is COMPLETE** — Commits 1-4 built, reviewed, and pushed on
branch `slice3.7-search-layer`, merging to main as a full slice (this doc + the hook spec are
committed into that same merge). Summary of the four commits:
- Commit 1 — two new operator searches (search_org_events, search_operating_characteristics) +
  structure tests. Wording for BOTH locked (see Decisions below).
- Commit 2 — re-budget the four existing searches (funding fact-list + founding_year + ceiling
  300->400; commercial provenance/trend + ceiling 450->700; drop one-bullet language from
  payer/outcomes).
- Commit 3 — wire 4 searches -> 6: run_research_batch calls both new searches (with inter-search
  sleeps), _build_latest_status_findings emits SIX labeled sections, REQUIRED_RESEARCH_COLUMNS
  grew 7->9 (org_events_finding + operating_characteristics_finding), synthesis got light nudges
  (reset points at org-events section + emits canonical reset_events without re-judging;
  commercial reads SOURCE TYPE->q4, TREND->q1). 214 green.
- Commit 4 — notebook mirror: STEP 7 delegates to the package (6-search sequence inherited); the
  notebook work was making its own machinery 9-column-consistent. **Key bug caught: STEP 10
  re-saves the checkpoint by selecting required_current_schema_cols (~line 2491); at 7 columns it
  would have STRIPPED the two new findings STEP 7 just wrote.** Widened all three
  required_current_schema_cols defs (STEP 6B/7/10) + STEP 8A required_raw_cols to 9 (KeyError-safe
  via prepare_source_df). Added STEP 4 shims, STEP 26 six-section findings rebuild, embedded Colab
  checklist. compile OK (magics stripped), 214 green.

**NEXT: Slice 4 — real capability-fit.** Three-attribute rubric scoring A1/A2/A3 off the
operating-characteristics evidence that Slice 3.7 now gathers, replacing the role_fit bridge.
Completing it flips the engine interim->real and unblocks Commit 5. The A1/A2 definitions are
ALREADY reframed in specs/slice4_capability_fit_spec.md (per the 3.7 amendment): A1 =
product-engagement structure (habit-dependent + revenue-dependent -> data-driven by necessity);
A2 = operational STRAIN (process breaking under growth), NOT "complexity exists"; a healthy
company scores LOW on A2. A3 unchanged, now shares product-engagement evidence with A1.

After Slice 4: **full data regeneration** (run-once; runbook reminders: restore
WAIT_BETWEEN_WEB_SEARCHES=120 [it was dropped to 5 for testing], delete throwaway test
checkpoints [Clair/Oura], STEP 26 rescore spot-check, verify multi-event reset fires on ZOE) ->
**Commit 5** (wire candidate->final_priority_level; fix false "Human Reviewed" labeling; sticky
reviewed_priority_level auto-seed) -> Commit 6 / master remediation -> calibration ->
colab_workflow.py cleanup.

### TWO items to handle BEFORE the run-once regeneration (from the Commit 4 review)
1. **Verify on FRESH research, not an old checkpoint.** Because REQUIRED grew to 9, the STEP
   8A / STEP 10 missing-column gates now require the 9-column schema (STEP 8A error literally says
   "rerun under the new Step 7 schema"). A pre-3.7 checkpoint pushed through those steps will
   correctly STOP. So the Colab verification run must research a company FRESH via STEP 7 — not
   resume an old checkpoint. (This is the columns-grew-by-2 decision working as intended.)
2. **STEP 21 / STEP 23 scope check (OPEN).** These are other research entry points (supervised
   runner / sheet queue). Commit 4 left them alone (correctly, per the STEP 7 + STEP 26 scope) —
   they carry no inline 4-search loop, only a "required globals exist" validation list still
   naming four searches. DECISION NEEDED: are STEP 21/23 live paths I'll use in the regeneration?
   If yes, have Claude Code move their validation lists (+ any research logic) to six BEFORE the
   run-once regen. If they're dead paths, leave them. (Cheap insurance either way; not a blocker
   for the 3.7 merge.)

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
