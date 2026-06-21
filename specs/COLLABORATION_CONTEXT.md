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
- Every temporary measure is built toward the North Star end state. Testing scaffolding and
  partial builds (e.g. temporary Colab cells to define a batch before the front end exists) must
  minimize friction for the eventual autonomous flow — solve the immediate step in the shape the
  end state will reuse, not in a throwaway shape that has to be undone later.

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

**Complete + Colab-verified — on branch `slice4-capability-fit`, NOT yet merged to main**
(merge gated on the pre-regen STEP 10/12 master-landing reconciliation — see *Immediate next
action*):
- Slice 4 — real capability-fit: three-attribute A1/A2/A3 rubric replacing the role_fit bridge,
  built on Slice 3.7's operating-characteristics search; gate-time A1/A3 no-double-count recompute
  for reset-lifted scale-ups; engine repoint to REAL (`CANDIDATE_FRAMEWORK_VERSION = "V4.2"`,
  `capability_fit_score` → `katelynd_capability_fit_score`) + suppression guard. Six commits,
  Colab-verified (ZOE 83 / Function Health 32; live multi-event reset fire on Function Health).
- Pre-regen master-completeness — engine-input signals (reset, scale signals, Slice 2 components,
  capability) carried to the master via `optional_model_cols`, so the regenerated master is
  engine-ready.
- Net engine state: REAL (V4.2) on this branch; **Commit 5** (write `final_priority_level`) is now
  **UNBLOCKED** but not yet built — so the engine remains INERT until Commit 5 lands.

**Specced, not yet built (in build order):**
1. **Full data regeneration** — run-once. GATED on the two pre-regen items in *Immediate next
   action*: the STEP 10/12 master-landing reconciliation (TOP) and the Flag A WAIT=120 re-run.
   Other runbook reminders: restore WAIT_BETWEEN_WEB_SEARCHES=120 (dropped to 5/30 for testing);
   delete throwaway test checkpoints (Clair/Oura); STEP 26 rescore spot-check.
2. **Commit 5** — wire candidate→final_priority_level authority + fix false "Human Reviewed"
   labeling + sticky reviewed_priority_level auto-seed. **Unblocked** (real capability-fit now
   exists); not yet built.
3. **Commit 6 / master remediation**, then **calibration** (judge too-strict/too-loose only
   against trusted regenerated data — NOT before).
4. **Post-migration cleanup pass** — colab_workflow.py AND the notebook old-flow cells (prune
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

## Immediate next action (update this line each time I start a new chat)
**Slice 4 (real capability-fit) is COMPLETE and Colab-verified** — six commits on
`slice4-capability-fit` (rubric → averaging/null policy → gate double-count fix → engine repoint
to V4.2 → notebook mirror → reference spec §4), plus a separate pre-regen master-completeness
commit (engine-input signals carried to the master via optional_model_cols). The live Colab run
passed: the capability rubric discriminates correctly (ZOE 83 / Function Health 32 on the A1
daily-habit-vs-episodic reframe), and Function Health gave the live multi-event reset fire (the
fireable leadership-change fires, the never-fire M&A correctly doesn't, engine reset_signal
matches). The engine is now **V4.2 — real, no longer the role_fit interim**.

**Remaining before the run-once regeneration:**
- **Flag A — thin-findings re-run.** The first Colab run had several findings come back empty
  (likely WAIT=30 + six searches → variance / rate-limiting). Re-run at WAIT=120 with a tightened
  V6 check (nan / len < ~10 counts as EMPTY) to confirm rich findings before trusting the regen.
- **STEP 10/12 master-landing reconciliation (TOP pre-regen item).** The inline path writes the
  real master through old-flow STEP 10→10A→12, which are at PRE-Slice-2 state and would silently
  land NONE of the slice columns (a regen would succeed with no error while dropping every slice
  column). Reconcile in place from the package mirror (option a), then DRY-RUN to a throwaway
  master to confirm every slice column lands before any real-master write — the run-once must not
  be the first real-master write.
- **Then:** full data regeneration (run-once) → Commit 5 (final_priority_level authority; held
  until capability-fit was real — now unblocked) → Commit 6 / master remediation → calibration →
  colab_workflow.py cleanup.

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
