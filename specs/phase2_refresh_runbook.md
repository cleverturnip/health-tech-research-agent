# Phase 2 — Operational notes / pre-refresh runbook

Operational reminders that don't belong in the roadmap (`COLLABORATION_CONTEXT.md` § Status & roadmap) but must not be
lost. **Read this before running any full research refresh.**

> **Execution script:** the cell-by-cell Colab runsheet for the run-once clean-slate regeneration
> lives in `regen_execution_runsheet.md`. This file is the *gate* (what must be true before the
> run); that file is the *steps* (which cells to run/skip/edit, in order). Keep them in sync.

## Before ANY full research refresh

1. **Restore the rate-limit wait.** Set `WAIT_BETWEEN_WEB_SEARCHES = 120` in STEP 2 of the
   Colab notebook. It was dropped to `5` during Slice 1 testing; 120 s between web searches is
   the rate-limit safety margin for a long, multi-company run.

2. **Delete the throwaway test checkpoints** so the Slice 1 smoke-test records (Clair Health,
   Oura) are not picked up as real evidence by the resume / evidence-resolution logic:
   ```python
   import glob, os
   patterns = [
       "research_batches/slice1_rewire_smoketest_*",
       "research_batches/clair_health_test_*",
       "/content/drive/MyDrive/Job Search/Health Tech Research/research_batches/slice1_rewire_smoketest_*",
       "/content/drive/MyDrive/Job Search/Health Tech Research/research_batches/clair_health_test_*",
   ]
   for p in patterns:
       for f in glob.glob(p):
           os.remove(f); print("removed", f)
   ```

3. **Verify the STEP 26 rescore path with the new derived maturity.** *(Superseded for the
   clean-slate regen — see gate item 6: re-research everything via Step 7, so STEP 26 is OFF the
   regen-critical path. Applies only to a later incremental rescore-from-archive run.)* Run ONE STEP 26 rescore
   (`STEP_26_DRY_RUN = False`) on a single company that has archived evidence; confirm it
   completes and that `cap_info["company_maturity_read"]` equals `derive_maturity(...)` for that
   company. *Why:* Slice 2's Colab run verified the STEP 7 → 10 → 10A path live but **skipped
   STEP 26**. STEP 26 calls the same `derive_maturity` (so the derivation itself is proven), but
   its wiring to it was not live-checked — and STEP 26 is the path that brings the 8 older-round
   companies up to current standard during regeneration, so confirm it works before relying on it.

4. **Verify multi-event reset on a known multi-event company.** Research one company doing more
   than one reset-type event at once (e.g. ZOE: a strategic-pivot AND a restructuring-toward-
   expansion). EXPECT `reset_or_restructure_signal` fires on the restructuring event even
   alongside the pivot (Slice 3.5 per-event evaluation). Under the single-value Slice 3, the
   louder pivot buried the restructuring and reset wrongly came back False — that live finding is
   what motivated 3.5. Also scan for `reset_needs_review == TRUE` rows (unrecognized event types
   surfaced for review).
   - **Update (Slice 3.7 merged, PR #36):** under 3.5 alone ZOE returned an EMPTY events list —
     neither event surfaced, because reset was synthesized only from the four market/financial
     searches. Slice 3.7 added the dedicated **`search_org_events`** (recency-bounded, multi-item),
     so this verification now runs on the six-search pipeline: EXPECT ZOE to surface BOTH events
     (strategic-pivot AND restructuring-toward-expansion) and `reset_or_restructure_signal` to fire
     on the restructuring. This is the **headline live check for Slice 3.7** (still pending — it
     runs here, at the regeneration / next Colab run; the per-event firing logic is already proven
     by the offline red→green test, so this confirms the live research now surfaces the events).

## Regen-path wiring — "is a regen path wired right?" items

5. **Inline-path master-landing (STEP 10/12) reconciled to the package + dry-run verified.** ⛔ TOP
   — CORRECTNESS, not quality. The regen researches on the inline-list → `run_research_batch` path
   (STEP 7), but its master-landing is the old-flow STEP 10 → 10A → 12 (fed by the shared `df`
   global), which is at PRE-Slice-2 state: STEP 10 derives no maturity/commercial/reset/capability
   (STEP 10A still uses an old inline commercial signal), and STEP 12's `optional_model_cols` does
   not carry them. A regen today would write the master with NO error while dropping every
   Slice 2/3/3.5/3.7/4 column — silently voiding the run-once. Fix (option a): add a STEP 10C derive
   block calling the tested `structured_evidence` functions → `summary_df`, and widen STEP 12
   `optional_model_cols` to carry the slice + engine-input columns. **The reconciled STEP 10/12 have
   never written the real master with slice columns — so the sequence MUST dry-run to a THROWAWAY
   master copy first, confirm every slice column lands with correct ZOE/Function values, and only
   then write the real master. The run-once must not be the first real-master write.**
   - **Dry-run validation outcome (2026-06-21):** the landing pipeline lands correctly (verified on
     the exact updated row). The dry run surfaced — and a series of fixes resolved — these: the
     dry-run isolation had to override ALL of STEP 12's write paths *after* its internal path block
     (it redefines `local_master_path`/`drive_master_path` itself) and skip its pre-flight
     `drive_master_path.exists()` check; and STEP 12's per-cell update needed the target columns cast
     to object so string/empty values persist on old all-NaN float64 columns.
   - **Master data-integrity (case-variant duplicates) — DONE on the notebook side.** The master had
     duplicate rows `zoe`/`ZOE` and `function health`/`Function Health`: the verify batch used
     proper-case names, and STEP 12 matched company names **case-sensitively**, so it *appended* new
     rows instead of updating the human-reviewed lowercase originals. Fixes: (a) de-duped the master
     (dropped the proper-case verify appends, kept the human-reviewed originals, backup taken);
     (b) added case-insensitive matching (`normalize_company_key` → lowercases) + a case-variant
     duplicate-guard to the notebook's STEP 12. **TODO before regen:** port the same case-insensitive
     matching into the package mirror's STEP 12 — it canonicalizes aliases via `canonical_company_name`
     but does NOT lowercase, so it shares the same append-a-duplicate vulnerability.
   - **✅ DRY-RUN VALIDATED (2026-06-21) — master-landing milestone CLOSED.** With the master de-duped
     and STEP 12 rebuilt (DRY_RUN write-isolation + read-from-real + object-cast so values persist +
     case-insensitive matching + key-based validation/count/prints), the dry run lands every slice
     column on the single human-reviewed row: **ZOE → 1 row** (early-growth / strong / capability 83 /
     founding 2017), **Function Health → 1 row** (early-growth / moderate / capability 23). Real master
     untouched (writes went to `/content` throwaways).
   - **⚠️ DRY_RUN flip safety — read before setting `DRY_RUN=False`.** The real-master write
     (`DRY_RUN=False`) happens ONLY during the actual run-once regeneration, with rich data and the
     full company set — **NEVER with the verify batch** (ZOE / Function Health). Function's `23` was a
     thin-findings artifact (the good WAIT=120 run scored it 32). Do not flip True→False by reflex
     after a dry run.
   - **Prerequisite (operational):** STEP 12 case-insensitive matching + object-cast are ported to the package
     (`master_update.py` regression tests + `colab_workflow.py` STEP 12), and the outcomes/payer empty-output fix
     is in place. (Whether the regeneration has run — and any other run-status — lives ONLY in
     `COLLABORATION_CONTEXT.md` § Status & roadmap.)

6. **Regenerated master is engine-ready — engine-input signals carried to the master.** ✅ CLOSED.
   The candidate engine (`compute_candidate_priority`, held Commit 5) reads its inputs off the row
   it scores; wired against the regenerated master it needs the derived SIGNALS on the master, not
   just the labels. STEP 12 only persists `model_cols_to_update` (← `optional_model_cols`), so the
   engine inputs are now folded into `optional_model_cols`: `reset_or_restructure_signal` / `_basis`
   / `_needs_review`, `reset_events_json`, `reset_event_types`, `commercial_scale_signal`
   (+ `_inferred`), `institutional_distribution_signal`, `outcomes_signal`,
   `plausible_near_term_scale_path`, plus the Slice 2 components + `maturity_needs_review` and the
   Slice 4 capability columns. *Why it mattered:* without it, when held-Commit-5 wires the engine
   against the master, every reset company would silently lose its cap-lift and the
   commercial/institutional/outcomes signals would collapse to 0 → broad mis-tiering baked into the
   run-once data. NOT a bug at the regen itself — the engine is not wired into any notebook path
   today (priorities come from the one-time audit snapshot; STEP 20 only splits the string) — but
   the run-once is the one cheap moment to make the durable master engine-ready. **Closed by the
   "pre-regen master-completeness" commit.**

7. **STEP 21 / STEP 23 scope.** ✅ RESOLVED — STEP 21/23 are the old-flow Google-Sheet-queue path,
   NOT the regen path. The regeneration runs on the inline-list → `run_research_batch` path (STEP 7),
   confirmed from Katelynd's notebook; the sheet queue is superseded by that path and ultimately by
   the future front end. Decision: not live for the regen — do NOT revive them or move their
   `required_runtime_items` validation lists 4→6; they fall to the post-migration cleanup pass.

## Research-layer robustness (before the run-once)

8. **Empty-output guard + outcomes/payer/funding search budgets.** ✅ DONE — code + **Colab-verified
   (2026-06-22)**. Was the **CORRECTNESS PREREQUISITE for the run-once**.
   - **Colab validation (2026-06-22):** fresh WAIT=120 ZOE/Function re-run → all SIX findings
     POPULATED for both, **zero SEARCH_FAILED markers** — the budget raise fills the holes that were
     empty/thin before (ZOE outcomes, ZOE/Function funding+payer). Guard live-proved (Tier A): a
     direct `call_openai` at a 16-token budget blanked → bumped retry (24) → still blank →
     `SEARCH_FAILED_MARKER` (logs confirmed the path; `is_search_failure` True). Failure≠absence held
     live: Function's outcomes came back as the "No strong public outcomes evidence" SENTINEL (a
     POPULATED real result), correctly NOT a marker. **One rider deferred:** the synthesis-as-absence
     check (Tier B skipped) → regen-time spot-check when a marker naturally appears.
   - **Problem:** `call_openai` returns `output_text` with no empty-guard; `search_outcomes` and
     `search_payer_signal` run at the tightest budget (350 vs commercial/org/operating at 700–800).
     On evidence-rich topics, a reasoning model can burn the 350-token output budget on web_search
     + reasoning before emitting summary text → `output_text == ""` → silently stored as a blank
     finding. Confirmed: consistent across both Colab runs, ZOE-specific (rich outcomes topic —
     PREDICT, the ZOE METHOD RCT), while thin-topic searches at 350 returned fine. **WAIT=120 runs
     were inconsistent — one came back 11/12 rich, a LATER WAIT=120 run came back thin for
     funding/payer for BOTH companies — proving the thinness is this token-budget / empty-output
     mechanism (variable per run), NOT rate-limiting (which WAIT=120 would fix consistently). So
     WAIT=120 alone does not close it; the budget raise + empty-output guard are required.** The
     empty-output is therefore NOT confined to ZOE's outcomes or to one search — it can silently hit
     ANY finding type (funding / payer / outcomes / any rich-topic search) for ANY company on ANY
     run, unpredictably.
   - **Two-part fix — DONE:** (1) raised `search_outcomes` + `search_payer_signal` + `search_funding`
     budgets to 700 (ALL rich-topic searches now 700; org/operating at 800 — no tight budget remains).
     (2) Empty-output guard in `call_openai`: if `output_text` is blank (empty/whitespace), retry ONCE
     at a bumped budget (×1.5, to counter the budget-exhaustion cause, not re-roll); if STILL blank,
     return `SEARCH_FAILED_MARKER` — never a silent `""`, never the false "No strong public … found."
     sentinel. `_row_is_complete` treats a marker as INCOMPLETE (a holed finding is re-researched on
     resume, not baked in as complete) and `is_search_failure()` makes it detectable downstream.
     Red→green tests cover all of it (budgets all-700, retry/marker, marker ≠ sentinel ≠ blank,
     marker-row-incomplete).
   - **Why this is a CORRECTNESS PREREQUISITE (not polish):** in the unattended run-once, a
     rich-topic search that blows its budget silently produces an empty finding for that company —
     degrading its scores in data that is expensive to regenerate, with NO ONE WATCHING (the North
     Star silent-failure mode). The empty-output guard converts a silent evidence hole into a
     VISIBLE FAILURE marker, so the gap is caught and re-run rather than baked into the "trusted"
     master. Without it, the run-once can ship silently-degraded rows. **Hard pre-regen gate.**
   - **Verification riders — run AT the regen (the code is in; these confirm the seams):**
     1. **Synthesis must not read a marker as absence.** The marker's inline "evidence UNAVAILABLE,
        not absent" wording steers the fit-brief LLM, but that's the one consumer where silent
        absence-inference could still happen via the LLM, not code. On the regen run, confirm a
        marker-bearing finding does NOT make the synthesis score a company as if the evidence were
        absent (spot-check a company that got a marker); add a one-line synthesis-prompt note only if
        it does.
     2. **Bigger findings don't starve the synthesis.** ✅ Confirmed by inspection: findings are
        f-string-assembled (`_build_latest_status_findings`, no truncation) and the fit brief's 6500
        is its OUTPUT budget, independent of input size; worst-case findings (6 × ~1050 after a bumped
        retry ≈ 6k tokens) + the rubric stay well within the model context.
     - **V6 notebook tweak (before the regen verification):** the findings-present check must treat
       `is_search_failure(...)` as a FAILURE, not "populated" — else it re-hides the hole. (Updated
       cell handed to Katelynd; imports `is_search_failure` from the package.)

## Notebook cell at a pre-slice state — STEP 10A schema drop (CORRECTNESS, fix before the run)

9. **STEP 10A drops the two Slice 3.7 findings + truncates the checkpoint.** ⛔ Fix in the notebook
   before the run. The `## 10A` cell defines a **stale HARDCODED** `required_current_schema_cols`
   (no `org_events_finding`, no `operating_characteristics_finding`) and then does
   `df = df[required_current_schema_cols]` — which (a) drops those two columns from `df`, so 10C
   lands them **BLANK** on every regenerated row (scoring is unaffected — capability/reset/maturity
   derive from `fit_brief_json`, which 10A preserves — but the master loses the Slice 3.7
   operator-evidence text the master-completeness commit deliberately carried), and (b) overwrites
   the local + Drive **checkpoints with 7 columns**, so any disconnect after 10A makes
   `run_research_batch` see "incomplete" rows and **re-research the whole set**. *Why it was hidden:*
   the item-8 ZOE/Function verification only checked the derived signals, not these two raw columns.
   **Fix (drift-proof — the list has now gone stale twice):** the recovery work added
   `growth_finding` + `paying_finding`, so the package schema is **11 columns** and a hardcoded 10A
   would drop *those* next. Replace 10A's `required_current_schema_cols = [...]` with the package
   import so it can never drift again — `from health_tech_research_agent.review import
   REQUIRED_RESEARCH_COLUMNS; required_current_schema_cols = list(REQUIRED_RESEARCH_COLUMNS)` — and
   apply the same one-line import in Step 7 (see `regen_execution_runsheet.md`). The dry-run
   verification cell also hard-stops on blank findings as a backstop. *(Classic "old-flow cell never
   wired for a later slice" — anticipated per COLLABORATION_CONTEXT; the import ends the whole class.)*

## The full data regeneration is RUN-ONCE — clear the gate first

> **✅ REGEN COMPLETE (2026-06-24).** The run-once ran: clean-slate **55-company V4.2 master**, landed +
> read-back verified, all rows `New batch - needs review`, `videahealth` excluded (transient fit-brief
> JSONDecodeError). The gate below is now **historical** (fully passed). **All "deferred until after
> the run-once" items are now ACTIONABLE:** ROOT fix #1 (inline STEP 12 → package call), ROOT fix #2
> (10A import-schema port to the `colab_workflow.py` mirror), and the fit-brief JSON-retry hardening. Next
> track: Commit 5 → Commit 6 / remediation → calibration → dashboard (LAST — it needs real
> `final_priority_level`, blank until Commit 5). See `COLLABORATION_CONTEXT.md` → Immediate next action.

Do **not** run the full master regeneration until the gate below is fully clear. The slice gaps
that motivated waiting are all now fixed in the package:

- maturity mislabel (Function Health read "late-stage" despite Series-B / hypergrowth) — fixed by **Slice 2**
- funding scored as commercial strength (Solace) — fixed by **Slice 2**
- reset signal is a dead input (no automated producer; manual-only) — fixed by **Slice 3** (+ **Slice 3.5**: multi-event, so a coexisting restructuring isn't buried by a louder pivot)
- **operator/organizational evidence had NO search behind it** — reset fired only on incidental mentions in the four market/financial searches (ZOE's restructuring never surfaced → it returned an empty events list), and capability-fit A1/A2 likewise had no targeting search; the high-demand searches were also evidence-starved by the stale one-bullet constraint — **fixed by Slice 3.7** (merged, PR #36: `search_org_events` + `search_operating_characteristics` + commercial/funding re-budget; the live ZOE-surfacing confirmation is the pending check in item 4 above)
- capability-fit is the interim `role_fit` bridge — fixed by **Slice 4** (which consumes Slice 3.7's `search_operating_characteristics`)

**Slice 4 is COMPLETE and Colab-verified on `slice4-capability-fit`** — so "wait for Slice 4 to be
built" is no longer the gate. The real remaining gate is the explicit checklist below; regenerate
**only when ALL of these are clear:**

1. **Flag A resolved** — ✅ CONFIRMED (WAIT=120 gave 11/12 rich findings; the thinness was
   rate-limiting; the one holdout — ZOE `outcomes_finding` empty — is the item-8 issue).
2. **STEP 10/12 master-landing dry-run verified** to a throwaway master — ✅ CONFIRMED (commit
   709f93e; every slice value landed on the correct human-reviewed rows, 1 row per company).
3. **STEP 12 corrected logic (case-insensitive matching + object-cast) ported to the package** —
   ✅ DONE: regression tests in `test_master_update_transaction.py` (case-insensitive match +
   object-cast land) + `colab_workflow.py` STEP 12 ported to key-based matching + `astype(object)`,
   closing the mirror's case-sensitivity gap. (Remaining fidelity sliver, not a correctness gate:
   port the DRY_RUN write-isolation toggle into the mirror's STEP 12 too — the notebook has it.)
4. **Outcomes/payer/funding empty-output fix** (item 8) — ✅ DONE + **Colab-verified** (2026-06-22:
   fresh WAIT=120 run → all findings populated, zero markers; guard live-fired via Tier A). One
   deferred rider: synthesis-as-absence regen-time spot-check (Tier B skipped). Was the CORRECTNESS PREREQUISITE.
5. **`slice4-capability-fit` merged to main** — ✅ DONE (merged 2026-06-22).
6. **Standing run-once reminders still hold** (items 1–4 at the top of this runbook):
   WAIT_BETWEEN_WEB_SEARCHES=120 restored, **ALL** research checkpoints cleared (regen decision:
   full clear, not just throwaways, so nothing pre-item-8 is reused), STEP 26 off the regen path
   (decision: re-research all via Step 7), multi-event reset verified (✅ Function Health).
7. **STEP 10A schema-drop fix applied in the notebook** — ⬜ DO BEFORE THE RUN (see item 9 above):
   replace 10A's `required_current_schema_cols` with the package import
   (`list(REQUIRED_RESEARCH_COLUMNS)`, 11 cols), else the regen drops `growth_finding` /
   `paying_finding` (and `org_events_finding` / `operating_characteristics_finding`) and truncates the
   checkpoint. Same import in Step 7.

Regenerating before the gate is clear would bake gaps into the "trusted" data and force a second
expensive full refresh. Regenerate **once**, only when every checklist item above is green.
(Tracked as a held item under Phase 3 → Candidate Priority Engine in `archive/PROJECT_TRACKER.md`.)

## Field-landing remediation (post-regen, DONE — PR #41)

⚠️ **A live instance of the inline-vs-mirror trap below.** After the run-once, an audit found the
regen master had two LLM-JSON clusters **present-but-blank** on all 55 rows — **role/timing**
(`stage_timing_fit`, `likely_agency_level`, `why_now_or_why_not`) and **taxonomy-LLM**
(`primary_market_segment`, the four tag columns, `taxonomy_assignment_method/_basis`) — though the
saved checkpoint's `fit_brief_json` had them populated 55/55. Root cause: the **live notebook's inline
STEP 10** summary build had been stripped of both clusters' landing (the `colab_workflow.py` mirror
still has them — exactly the drift ROOT-CAUSE fix #2 warns about), and the regen read-back checked
column *presence*, not *population*, so it passed.

**Fix (done, the recoverable patch — not the cure):** a standalone, idempotent re-land — `reland.py`
(`reland_llm_clusters`) — reads the existing master + the saved checkpoint and **blank-only**-fills the
10 dropped columns, with **no re-research and no STEP 10/12 re-run**. Guards: 1:1 checkpoint↔master
completeness (fail-loud, write nothing on any unmatched row), per-field read-back vs the checkpoint's
**own** populated counts (not "column exists" — that's the check that missed this originally), backup +
rollback. `primary_market_segment_code` deferred to STEP 14 (classifier-owned, Rule 7); the 4
role/timing siblings + 5 deterministic-taxonomy fields deferred to the dashboard milestone.
Colab-verified: role/timing 55/55, `subsegment_tags` 54, and `final_priority_level` +
`primary_market_segment_code` stayed blank. Caller snippet: `specs/snippets/reland_caller_cell.py`.

**The durable cure is still the two ROOT-CAUSE fixes below** — collapse the inline STEP 10/12 into the
package so a stripped live cell can't silently diverge from the mirror again. Re-landing was the
recoverable patch; single-source is the prevention.

## ROOT-CAUSE fix — collapse the inline STEP 12 into the package call (deferred, LOAD-BEARING)

⚠️ This is the **cure for the duplication that caused this session's marathon debugging** — record
it at that weight, NOT as a minor post-regen cleanup.

**What the session established:** the case-sensitivity / dtype-no-op bug was **never in the
package** — `master_update.py` already had casefold matching (`normalize_company`) + the object-cast,
with tests. It lived ONLY in the **inline STEP 12** that the notebook and the `colab_workflow.py`
mirror re-implement as a parallel copy. Commit `985f072` is a **PORT**: it copies the corrected logic
into the inline path and locks it with regression tests, which makes the run-once SAFE — but it
**preserves the duplication** (the correct logic now lives in TWO places, kept in sync by tests
rather than by a single source).

**The root fix:** have STEP 12 *call* the package (`master_update.build_proposed_master` /
`execute_master_update_transaction`) so there is ONE implementation. This is the thing that prevents
this class of drift bug from recurring — load-bearing, not cleanup. (Architecture Rule 1: production
behavior as importable package functions, not re-implemented in cells.)

**Deliberately deferred until AFTER the run-once.** The port + regression tests make the regen safe;
collapsing the inline cell into the package call is too invasive to do safely right before a
run-once. Do it first in the post-regen cleanup pass.

## ROOT-CAUSE fix #2 — make the STEP 10A schema DRIFT-PROOF in the mirror (deferred, same weight)

⚠️ Same trap-class as the inline STEP 12 above — record at that weight. STEP 10A's hardcoded
`required_current_schema_cols` has now gone stale TWICE (first the Slice 3.7 cols, then the recovery
cols `growth_finding` / `paying_finding`); each time a hand-typed list drops the new columns from `df`
and truncates the checkpoint. The notebook cell is being moved to the package import; `colab_workflow.py`'s
mirror STILL carries a stale HARDCODED list, so the repo copy is a TRAP: a future session that reads,
ports, or runs the mirror's 10A would silently reintroduce the column-drop + checkpoint-truncation bug.

**The fix (drift-proof, not another count bump):** replace the hardcoded list in `colab_workflow.py`'s
STEP 10A with `from health_tech_research_agent.review import REQUIRED_RESEARCH_COLUMNS;
required_current_schema_cols = list(REQUIRED_RESEARCH_COLUMNS)`. This ends the whole bug-class — the
mirror then tracks whatever the package writes. **Deferred to the post-regen cleanup pass**, alongside
the inline-STEP-12 collapse above. Until ported, do NOT trust `colab_workflow.py`'s 10A. (A
`specs/snippets/step_10A_fixed.py` was referenced historically but does not exist — use the import line
above, not a byte-exact snippet.)

## Deferred / optional (not scheduled)

- **Fit-brief JSON-decode retry/repair (research robustness).** ⬜ OPEN / DEFERRED (post-regen).
  The fit-brief synthesis (`run_company_fit_brief` → `call_openai`, web search off, 6500 tokens)
  returns raw text parsed strictly by `parse_first_json_object` (no repair). `call_openai` retries
  only `RateLimitError`, **not `JSONDecodeError`** — so one malformed generation (a trailing comma /
  unquoted key — NOT truncation; both seen well under budget) fails the whole company, recoverable
  only by re-researching on a later resume. Cost two companies in the V4.2 regen: `hinge health`
  (recovered on a re-run) and `videahealth` (stayed missing → excluded from the 55-company master).
  Fix: retry the fit brief ONCE on `JSONDecodeError` (re-roll), and/or a `json_repair` fallback; add
  a red→green test. Don't touch the `RateLimitError` retry semantics. (Tracked as a session task.)

- **APIError retry-narrowing.** `call_openai` currently retries only `RateLimitError` and
  re-raises `APIError` immediately (faithful to the original notebook). Optional follow-up:
  retry the *transient* API errors (`APIConnectionError`, `APITimeoutError`, 5xx
  `InternalServerError`) but **not** 4xx (auth / bad request). Small, separate, reviewable
  commit if/when we want it. Not urgent — the per-company recovery wrapper already prevents a
  single `APIError` from aborting a batch, so this is a refinement, not a fix.

- **Taxonomy audit + generalization for cross-industry use.** ⬜ OPEN / DEFERRED — sequence AFTER
  the health-tech regeneration + calibration, so the validated health-tech baseline isn't perturbed.
  *Context:* the scoring layer is already largely domain-agnostic — the commercial-OR-institutional
  dual path means a strong non-health D2C company passes on the commercial path (empty
  payer/outcomes findings are a valid state the engine handles), and the capability rubric is
  calibrated to D2C-with-a-live-business-model, not to health specifically. Katelynd intends to use
  the researcher for opportunities in other industries. The one identified blocker is the taxonomy:
  a non-health company matches no segment, which currently flags it for manual review — a halt that
  breaks the autonomous flow.
  - **Investigate first (read-only; report before any change):** the taxonomy structure, how
    keyword matching assigns a segment, and precisely what no-match does in code — a hard
    halt-for-review or a soft empty-tag-and-continue. This determines the fix shape.
  - **Likely two-part fix (design after the investigation):** (1) a general catch-all / "other tech
    startup" category as the no-match FLOOR, so the flow never halts on an unrecognized segment
    (autonomous-safe — no human is watching mid-segment to clear a manual-review flag); (2)
    optionally expand the taxonomy with the specific cross-industry segments Katelynd expects to
    evaluate, so categorization stays meaningful rather than dumping everything into "other."
  - **Constraints:** the taxonomy was deliberately kept narrow (market-segment keyword matching;
    org/operating evidence kept OUT to avoid noise) — expanding it must not reintroduce that noise;
    and the no-match-safety change should affect ONLY companies that currently miss (health-tech
    already matches, so the regen baseline stays untouched). **Priority half:** the no-match path
    must CONTINUE (tagged catch-all), not HALT — that's the actual blocker; added segments are
    enrichment.
