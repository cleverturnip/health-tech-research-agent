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

## The full data regeneration is RUN-ONCE — wait for Slices 2–4

Do **not** run the full master regeneration until Slices 2, 3, and 4 are all merged. The
interim pipeline still has the known audit gaps:

- maturity mislabel (Function Health read "late-stage" despite Series-B / hypergrowth) — fixed by **Slice 2**
- funding scored as commercial strength (Solace) — fixed by **Slice 2**
- reset signal is a dead input (no automated producer; manual-only) — fixed by **Slice 3**
- capability-fit is the interim `role_fit` bridge — fixed by **Slice 4**

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
