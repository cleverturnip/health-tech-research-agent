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
   - **Update (Slice 3.5 live run):** ZOE returned an EMPTY events list — neither event surfaced,
     because reset was synthesized only from the four market/financial searches. So the live
     multi-event FIRE could not be reproduced under 3.5 alone. **Slice 3.7's `search_org_events`
     is the fix** — re-run this verification AFTER 3.7, when ZOE's org events should actually
     surface. (The per-event firing logic itself is already proven by the offline red→green test.)

## The full data regeneration is RUN-ONCE — wait for Slices 2–4

Do **not** run the full master regeneration until Slices 2, 3, 3.5, **3.7**, and 4 are all
merged. The interim pipeline still has the known audit gaps:

- maturity mislabel (Function Health read "late-stage" despite Series-B / hypergrowth) — fixed by **Slice 2**
- funding scored as commercial strength (Solace) — fixed by **Slice 2**
- reset signal is a dead input (no automated producer; manual-only) — fixed by **Slice 3** (+ **Slice 3.5**: multi-event, so a coexisting restructuring isn't buried by a louder pivot)
- **operator/organizational evidence has NO search behind it** — reset fires only on incidental mentions in the four market/financial searches (ZOE's restructuring never surfaced → it returned an empty events list), and capability-fit A1/A2 likewise have no targeting search; the high-demand searches are also evidence-starved by the stale one-bullet constraint — all fixed by **Slice 3.7** (search-layer redesign: `search_org_events` + `search_operating_characteristics` + commercial/funding re-budget)
- capability-fit is the interim `role_fit` bridge — fixed by **Slice 4** (which consumes Slice 3.7's `search_operating_characteristics`)

Regenerating on the interim pipeline would bake those gaps into the "trusted" data and force a
second expensive full refresh. Regenerate **once**, after all three slices land. (Tracked as a
held item under Phase 3 → Candidate Priority Engine in `PROJECT_TRACKER.md`.)

## Deferred / optional (not scheduled)

- **APIError retry-narrowing.** `call_openai` currently retries only `RateLimitError` and
  re-raises `APIError` immediately (faithful to the original notebook). Optional follow-up:
  retry the *transient* API errors (`APIConnectionError`, `APITimeoutError`, 5xx
  `InternalServerError`) but **not** 4xx (auth / bad request). Small, separate, reviewable
  commit if/when we want it. Not urgent — the per-company recovery wrapper already prevents a
  single `APIError` from aborting a batch, so this is a refinement, not a fix.
