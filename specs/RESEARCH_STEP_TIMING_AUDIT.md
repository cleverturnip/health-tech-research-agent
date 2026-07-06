# Research-step timing audit (2026-07-05)

**Scope:** the per-company research step (`research_runner.run_research_batch`), which was taking
30–40 min/company. Goal: cut per-company time **without** losing the research quality that feeds §B
scoring. **Status: investigation + live A/B probes complete; NO production code changed.** This doc is
the findings + recommendation. All probes ran read-only against a **separate OpenAI key**, wrote only to
a session scratchpad, and called the **unmodified** package (never the webapp orchestrator / live
checkpoint / Drive / ledger), so they could not perturb an active research run.

---

## 1. Headline: ~70% of each company's time is `time.sleep`, not research

Per company, with shipped defaults (`DEFAULT_WAIT_BETWEEN_SEARCHES=120`, `DEFAULT_WAIT_BETWEEN_PASSES=45`):

| Bucket | Amount |
|---|---|
| Inter-**search** sleeps — 120s × 8 (after funding, payer, outcomes, revenue, growth, paying, org-events, + trailing) | **~16 min** |
| Inter-**pass** sleeps — 45s × 13 gaps across the 4 recovery unions (funding 2-pass, revenue/growth/paying 5-pass) | **~10 min** |
| Actual LLM/web-search work — 21 web searches + 4 presence checks + 1 fit-brief ≈ 26 calls | **~10 min** |
| **Total** | **~36 min** |

So **~26 of every ~36 minutes is the process sleeping.** The levers are the waits, not the research.

## 2. Where the 120s came from — its premise is falsified

`DEFAULT_WAIT_BETWEEN_SEARCHES=120` traces to the Colab source, labeled a **"rate-limit safety margin for
a long, multi-company run"** (`phase2_refresh_runbook.md:12-14`), deliberately restored to 120 after being
dropped to 5 in testing. But:

- The project's **own** diagnostics concluded the real failure mode (thin/empty findings) was
  token-budget/empty-output + web-search execution variance, **NOT rate-limiting**:
  *"WAIT=120 runs were inconsistent … proving the thinness is this token-budget / empty-output mechanism
  (variable per run), NOT rate-limiting (which WAIT=120 would fix consistently)"* (`phase2_refresh_runbook.md:140-144`).
  The fixes that actually worked were the budget raise, the empty-output guard, and the always-N recovery union.
- Katelynd confirms **throttling was never the constraint** (one out-of-credits incident, since prevented).
- The Colab STEP 21 batch runner even *defaulted* this to **30**, not 120 (`colab_workflow.py:7458`).

The genuine web-search-variance concern is handled by the **45s inter-pass** wait inside each recovery
union (near-identical retry passes), which is a *different* mechanism from the 120s between *distinct*
searches. The 120s guards a premise the evidence contradicts.

## 3. Lever 1 — cut the inter-search wait (120s → 10s). VALIDATED.

Sequential, one number changed via the existing `wait_between_searches` param. Probed **9 companies**
(Function Health, ZOE, Oova, Oura, Signos, Levels, InsideTracker, Noom Med, Outcomes4Me — exact baseline
queries reused), diffed against the trusted WAIT=120 baseline (`v42_full_regen…FINAL.csv`, ~1 wk old).

- **Timing:** ~35 → **~15 min/company (~57% faster).**
- **Quality:** **0 new `SEARCH_FAILED` markers; 0 priority-tier changes** (all P2→P2 inline). 2 "thin"
  findings, both `org_events` (the single-pass search — see §6). 1 empty primary (`paying_customer_count`
  on Outcomes4Me — synthesis placement; the underlying `paying_finding` was *richer*). Funding-round
  recall varied both directions (no bias).
- **Verdict:** no wait-attributable degradation; every difference is within the run-to-run variance the
  runbook documents at fixed 120s. Because quality holds at 10s, any larger shipped value is safe by
  monotonicity (only 10s was empirically validated — don't extrapolate below it).

## 4. Lever 2 — parallelize the independent searches. VALIDATED (bigger win, subsumes Lever 1).

The 8 searches only converge at the fit-brief synthesis; they're otherwise independent. Run them as
concurrent tracks (thread pool), **each recovery union still pacing its own passes 45s apart internally**
(variance mechanism preserved). This isolates parallelism (inter-pass wait held at 45). Companies still
run one at a time; parallelism is *within* a company. Probe replicated `run_research_batch`'s exact calls
without touching package code.

- **Timing:** steady **~4.0–4.2 min/company (~9× baseline, ~3.5× Lever 1).** The remaining ~4 min is
  almost entirely the 5-pass unions' 4×45s inter-pass waits.
- **Quality (8 of 9 completed):** **0 new markers.** The parallelism-specific risk — firing the three
  commercial-based unions (revenue/growth/paying) simultaneously → cache-correlated/thinned results —
  **did not materialize** (none of commercial/growth/paying came back thin; several were richer). All 4
  "thin" findings were again `org_events` (single-pass, config-independent; one company came back richer).
- **1 failure:** Noom Med, the known ~1-per-run fit-brief `JSONDecodeError` — config-independent (the
  fit-brief call is identical post-join), handled exactly like the real runner (recorded failed, auto-retry
  on resume). Watch-item: parallel gathering can produce *richer* findings → larger fit-brief input, a
  marginal nudge to that truncation bug (already tracked; runbook verified output budget is independent of
  input size).

## 5. §B scoring validation — parallelism does NOT degrade scoring beyond normal fresh-run variance

Compared against the **real deterministic scorer** (`run_r1`), not just the inline scores. Scored the
parallel rows AND the 120s-baseline rows through `run_r1`, vs the trusted `ledger.jsonl` (fresh copy
confirmed via the "Suno" entry; `model_priority` is write-once §B, unaffected by overrides/finalize).

**Three-way per-company (tier / bg_fit / pmf / final):**

| company | LEDGER (120s) | 120s-research re-score | parallel re-score |
|---|---|---|---|
| function health | P3 · 4 · 9 · 15 | P3 · 4 · 9 · 15 | **P1** · 6 · 9 · 17 |
| zoe | P0 · 8 · 9 · 19 | P0 · 8 · 9 · 19 | P0 · 7 · 9 · 18 |
| oova | P3 · 8 · 4 · 13 | P3 · 7 · 4 · 12 | P3 · 5 · 3 · 9 |
| oura | P3 · 9 · 9 · 20 | P3 · 9 · 9 · 20 | P3 · 9 · 9 · 19 |
| signos | P3 · 9 · 3 · 12 | P3 · 10 · 3 · 13 | P3 · 10 · 3 · 13 |
| levels health | P1 · 9 · 8 · 17 | **P0** · 10 · 8 · 18 | P1 · 8 · 8 · 16 |
| insidetracker | P3 · 4 · 4 · 8 | P3 · 4 · 4 · 8 | P3 · 7 · 3 · 10 |
| outcomes4me | P3 · 5 · 3 · 10 | P3 · 5 · 3 · 10 | P3 · 5 · 4 · 10 |

- **LEDGER → 120s-research re-score = 1/8 tier moves** (Levels P1→P0). This is the **read-variance noise
  floor**: re-scoring *identical* research still moves ~1/8 tiers because of the noisy reads.
- **120s-research re-score → parallel re-score = 2/8** (Function Health, Levels) — barely above the floor.

### The Function Health deep-dive (P3→P1)
A repeat-variance probe on the `background_fit` read (the framework's one deliberately-4×-averaged noisy
read) settled it. The engagement **evidence is identical** across all three research sets ("episodic 2×/year
lab testing, not a daily habit, STRONG"), yet the read maps it unstably:

- 120s baseline row: bg reads `[3,4,4,4,4,4,4,4,4,4,4,5]` → mode **4**
- Lever 1 **sequential** row: bg reads `[4,4,4,4,4,5,7,8]` → **spans 4→8**
- Lever 2 parallel row: bg reads `[4,7,7,7,7,7,7,7]` → mode **7**

The instability appears in **Lever 1 sequential too** → it is **not parallelism-specific** and **not a
research-quality difference.** Function Health sits *exactly* on the floor threshold (bg>4), so the wobble
flips P3↔P1. It was always fragile: the ledger scored it bg=4→P3 and Katelynd overrode to P1 (the canonical
"correctly floored but actually strong" override case). Cross-company bg shifts go **both directions**
(Oova 8→5, InsideTracker 4→7), no bias; only the boundary company crossed a tier.

**Conclusion:** parallelism (and Lever 1) do not degrade §B scoring beyond what *any* fresh re-research
already does.

## 6. Separate findings (not about the speed levers)

- **`background_fit` read robustness on floor/tier-boundary companies.** With N=4 averaging and a company at
  the exact threshold, the tier is a coin-flip on any re-research (sequential or parallel, 120s or 10s).
  This is a **scoring-framework (SOT) item, doc-first** — candidates: raise `BG_FIT_N_READS` from 4, or
  auto-flag floor-boundary companies for review. Independent of this audit.
- **`org_events` is the one search with no recovery union** → the most recall-noisy finding (drove every
  "thin" flag in both levers, in both directions). A candidate for its own recovery union later; unrelated
  to the wait levers.
- **The 4 presence-check calls are logging-only** — `figure_present` is written to a log line and never
  persisted or used in scoring. Deferrable/removable, or persist the provenance.

## 7. Recommendation & build notes (no code changed yet)

- **Ship Lever 2** (intra-company parallelism) as the target — ~9× faster, quality-validated, and it
  **subsumes Lever 1** (parallel tracks have no inter-search wait). If a smaller change is preferred first,
  **Lever 1** (lower `DEFAULT_WAIT_BETWEEN_SEARCHES` to 10s) is a one-line, independently-validated win.
- **Build discipline:** the change is to `research_runner.run_research_batch` — the **live file the active
  research runs use.** Build in an **isolated worktree**, keep search prompts/functions byte-identical
  (orchestration-only, per the runner spec's "prompts unchanged"), and **coordinate the merge** so it does
  not land mid-run. The webapp orchestrator uses the package default, so it picks up the change automatically.
- **Honest limits:** n=9 (Lever 1) / n=8 completed (Lever 2), single run per arm, one ~1-week-old baseline.
  Strong corroboration (tier stability at/near the read-variance noise floor; 0 markers; commercial
  parallelism risk cleared), not a formal repeat-variance study.

## 8. Artifacts

Probe scripts + raw outputs live in this session's scratchpad (session-local, not committed): the Lever 1 /
Lever 2 probes, the three-way `run_r1` scoring comparison, and the `background_fit` repeat-variance probes.
Baseline research: `~/Downloads/v42_full_regen_clean_slate_20260622_full56_checkpoint_FINAL.csv`. Trusted
scoring: `~/Downloads/ledger (3).jsonl` (Drive "HTRA Dashboard Data" export).
