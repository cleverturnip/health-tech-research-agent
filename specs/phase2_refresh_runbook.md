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

## The full data regeneration is RUN-ONCE — wait for Slices 2–4

Do **not** run the full master regeneration until Slices 2, 3, 3.5, 3.7, and 4 are all merged.
Slices 2 – 3.7 are merged; **Slice 4 (capability-fit) is the last one remaining.** The interim
pipeline still has the known audit gaps:

- maturity mislabel (Function Health read "late-stage" despite Series-B / hypergrowth) — fixed by **Slice 2**
- funding scored as commercial strength (Solace) — fixed by **Slice 2**
- reset signal is a dead input (no automated producer; manual-only) — fixed by **Slice 3** (+ **Slice 3.5**: multi-event, so a coexisting restructuring isn't buried by a louder pivot)
- **operator/organizational evidence had NO search behind it** — reset fired only on incidental mentions in the four market/financial searches (ZOE's restructuring never surfaced → it returned an empty events list), and capability-fit A1/A2 likewise had no targeting search; the high-demand searches were also evidence-starved by the stale one-bullet constraint — **fixed by Slice 3.7** (merged, PR #36: `search_org_events` + `search_operating_characteristics` + commercial/funding re-budget; the live ZOE-surfacing confirmation is the pending check in item 4 above)
- capability-fit is the interim `role_fit` bridge — fixed by **Slice 4** (which consumes Slice 3.7's `search_operating_characteristics`)

Regenerating on the interim pipeline would bake those gaps into the "trusted" data and force a
second expensive full refresh. Regenerate **once**, after Slice 4 lands (Slices 2 – 3.7 done).
(Tracked as a held item under Phase 3 → Candidate Priority Engine in `PROJECT_TRACKER.md`.)

## Deferred / optional (not scheduled)

- **APIError retry-narrowing.** `call_openai` currently retries only `RateLimitError` and
  re-raises `APIError` immediately (faithful to the original notebook). Optional follow-up:
  retry the *transient* API errors (`APIConnectionError`, `APITimeoutError`, 5xx
  `InternalServerError`) but **not** 4xx (auth / bad request). Small, separate, reviewable
  commit if/when we want it. Not urgent — the per-company recovery wrapper already prevents a
  single `APIError` from aborting a batch, so this is a refinement, not a fix.
