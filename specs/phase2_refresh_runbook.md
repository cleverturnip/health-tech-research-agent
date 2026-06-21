# Phase 2 — Operational notes / pre-refresh runbook

Operational reminders that don't belong in the roadmap (`PROJECT_TRACKER.md`) but must not be
lost. **Read this before running any full research refresh.**

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

3. **Verify the STEP 26 rescore path with the new derived maturity.** Run ONE STEP 26 rescore
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
     untouched (writes went to `/content` throwaways). Remaining before the run-once: (1) port the
     rebuilt STEP 12 (case-insensitive matching + object-cast) into the package mirror; (2) item 8
     outcomes/payer empty-output fix; (3) the regeneration itself (the real master write happens then,
     not from this verify batch).

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

8. **Empty-output guard + outcomes/payer search budgets.** ⬜ OPEN — do before the run-once
   regeneration; NOT a blocker for the master-landing dry-run. (Its own small pre-regen mini-slice.)
   - **Problem:** `call_openai` returns `output_text` with no empty-guard; `search_outcomes` and
     `search_payer_signal` run at the tightest budget (350 vs commercial/org/operating at 700–800).
     On evidence-rich topics, a reasoning model can burn the 350-token output budget on web_search
     + reasoning before emitting summary text → `output_text == ""` → silently stored as a blank
     finding. Confirmed: consistent across both Colab runs, ZOE-specific (rich outcomes topic —
     PREDICT, the ZOE METHOD RCT), while thin-topic searches at 350 returned fine.
   - **Two-part fix:** (1) raise `search_outcomes` + `search_payer_signal` budgets to ~700 (match
     commercial); (2) add an empty-output guard in `call_openai` — if `output_text` is blank,
     retry; if still blank, return an explicit FAILURE marker, never a silent `""` and never the
     false "No strong public … found." sentinel (a silent empty asserts "no evidence" when the
     search actually FAILED — exactly the unattended-segment silent-failure the North Star
     principle warns against). Red→green test for the guard.
   - **Why it matters at scale:** in the unattended run-once, any rich-topic search that blows its
     budget would silently punch an evidence hole into the master with no one watching. A
     CORRECTNESS item for the regen, not just a quality nicety.

## The full data regeneration is RUN-ONCE — clear the gate first

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

1. **Flag A resolved** — ✅ CONFIRMED: WAIT=120 gave 11/12 rich findings; the earlier thinness was
   rate-limiting. (One narrow holdout, ZOE `outcomes_finding` empty, is covered by item 8.)
2. **STEP 10/12 master-landing reconciled + dry-run verified** to a THROWAWAY master before any
   real-master write (item 5). ⏳ IN PROGRESS — the dry-run surfaced a real landing bug (new slice
   values are not overwriting existing master rows; reads `summary_df` but the saved master keeps
   the old audit values). NOT yet passing.
3. **Outcomes/payer empty-output fix done** (item 8 — budget raise + empty-output guard).
4. **`slice4-capability-fit` merged to main.**
5. **Standing run-once reminders still hold** (items 1–4 at the top of this runbook):
   WAIT_BETWEEN_WEB_SEARCHES=120 restored, throwaway test checkpoints deleted, STEP 26 rescore
   spot-check, multi-event reset verified (✅ Function Health gave the live multi-event fire).

Regenerating before the gate is clear would bake gaps into the "trusted" data and force a second
expensive full refresh. Regenerate **once**, only when every checklist item above is green.
(Tracked as a held item under Phase 3 → Candidate Priority Engine in `PROJECT_TRACKER.md`.)

## Deferred / optional (not scheduled)

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
