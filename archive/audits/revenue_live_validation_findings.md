# Findings — Revenue Retry-and-Union LIVE Validation (4 ground-truth companies)

**Date:** 2026-06-26 · **Branch:** research-search-recovery · **Type:** live, read-only validation
(no master/checkpoint/Drive writes; `scripts/revenue_live_validation.py`).
**Config:** revenue config, N=5, `wait_between_passes=45s`, model `gpt-5.4-mini`. ~28 calls.
**Headline:** mechanism works (Midi unioned both figures); **45s cadence ACCEPTED** (independence
demonstrated); and **Pelago falsifies our "genuine absence" label (Rule 8, live)**.

---

## 1. Cadence: 45s VALIDATED — per-pass independence demonstrated. Decision: ACCEPT.

The point of logging raw passes was to *see* independence, not infer it from a recovered figure.
Across all four, different passes surfaced different sources/figures — genuinely independent rolls:

- **Midi:** Latka $115.9M (with the $0→$115.9M series) surfaced **only on pass 4**; TIME "fivefold
  revenue jump" **only on pass 5**; Forbes $7M (2023) **only on pass 1**. CB Insights $150M + Growjo
  $115.9M stable across most. The union's recovery of $115.9M *depended* on pass 4 specifically.
- **Pelago:** maximal variance — pass 1 (general) found **no** estimate (reproduced the old blind
  0/5); pass 2 found **$27.5M Latka**; pass 3 found a junk **$435k Growjo** (6-employee wrong entry);
  pass 4 found none; pass 5 found **$27.5M Latka + $25.3M Growjo**.
- **ZOE:** Growjo **$82.3M only on pass 1**; Companies House £1.8M/£5.9M on passes 2/4; CB Insights
  $36.95M stable; 100k+ paying members on pass 3.
- **Solace:** the $10M CB Insights figure was stable across all 5 (correct — Solace was the 5/5
  stable case), with varied periphery (2,000 advocates on pass 2; 200k patients on pass 4).

**Decision: ACCEPT 45s.** Independence is occurring; do not bump for independence reasons. (Re-running
at a higher interval would spend credits to confirm what is already visible.)

## 2. Recovery results

| Company | Ground truth (predates run) | Result | `revenue_or_arr` (synthesis) | q4 | conf |
|---|---|---|---|---|---|
| **Midi** | $115.9M (Latka) / $150M (CB Insights) | **both unioned ✅** | CB Insights $150M + Latka $115.9M + Growjo $115.9M | credible-estimate | 63 |
| **Solace** | ~$10M (CB Insights) | **$10M single-source ✅** | CB Insights $10M (2025) | credible-estimate | 58 |
| **Pelago** | "genuine absence" (0/5 blind) | **RECOVERED — see §3** | $27.5M Latka + $25.3M Growjo + 287%/10x growth | company-reported | 66 |
| **ZOE** | ~$80M ARR / 88k paying (Crowdcube) | **partial — see §5** | Companies House £1.8M/£5.9M + CB Insights $36.95M; 100k+ paying | company-reported | 66 |

## 3. HEADLINE FINDING — Pelago falsifies "genuine absence" (Rule 8, live)

Pelago was our **canonical genuine-absence case** (0/5 in the original blind repeat-A probe; cited
that way in `research_revenue_cause_isolation_findings.md` and the kickoff). This run recovered
**Latka $27.5M (2024, page dated Apr 2025)** and **Growjo $25.3M** — figures that **predate the
original probe**. Pelago was **never absent**; the blind general search just never reached those pages.
The source-directed passes (2–5) did.

**Consequence (stated explicitly):** **every prior "genuine absence" label in this project was
assigned by the BLIND probe and is now SUSPECT.** The genuinely-absent set is probably smaller than
we thought. **Any recoverability measurement — the all-fields blink probe, the roster-wide #6
re-research scoping — MUST use SOURCE-DIRECTED retries, not the blind probe.** This is the same
lesson as the earlier "78% Mode C" falsification: *absence in our output ≠ absence in the world*
(COLLABORATION_CONTEXT Rule 8). It is also a direct vindication of the source-directed retry design
(it earned its keep by recovering a case the general search structurally missed).

## 4. Designed behaviors — confirmed against real output

- **Carry-and-rate: working.** Midi unioned all 3 estimates; Pelago kept the 2 credible estimates and
  **correctly dropped** the obvious junk ($435k / 6-employee Growjo entry). *One exception:* ZOE (§5).
- **Corroboration → confidence: sensible gradient.** Solace (1 thin estimate) **58** < Midi (3
  corroborating estimates, none company-reported) **63** < Pelago / ZOE (carry **company-reported**
  elements) **66**. Company-reported beats estimate-only; more sources nudge it up.
- **q4 = strongest source type: correct in all 4.** Midi/Solace `credible-estimate`; Pelago
  (company-reported growth) / ZOE (Companies House filings) `company-reported`. The multiple-weak
  guard never mis-fired. (Nuance: Pelago's q4=company-reported reflects the *growth* disclosures; the
  *absolute* revenue is estimated.)
- **Mode-B:** no false-empty flags fired (all four populated). But the check is **too coarse** — it
  did not catch ZOE's *partial* drop (§5). Sharpening tracked in B2.

## 5. Open issues (flagged here; investigated/resolved in the B work)

- **B1 — Pelago per-pass hit rate, NOT just "more passes".** Recovery came from the source-directed
  passes (2–5), which hit only ~2 of 4; pass 1 (general) reproduced the blind miss. The lever is
  raising the **per-pass hit rate** of the source-directed passes (cheaper than a 6th pass on every
  company, every run). Do **not** default to N=6. N is per-field config.
- **B2 — ZOE silent entity-drop.** Pass 1 surfaced **Growjo $82.3M** (≈ the ground-truth ~$80M). The
  synthesis **silently excluded it** as a "different 'Join ZOE' entity" — but **joinzoe.com is ZOE's
  own domain**, so the call was likely wrong. The deeper problem: it was a **silent LLM entity-
  conflation judgment**, the exact call we've said the LLM is unreliable at and that has no
  deterministic guard. Decision (designed in B2): **plausible-but-uncertain entity doubt → CARRY the
  figure + entity-uncertainty flag + route to manual review; never silently drop. Clear mismatch
  (wrong industry / absurd scale, e.g. the $435k Pelago junk or Solace→"Solace Healthcare" home
  health) → still drop.**

## 6. Method note (carry forward)

The validation harness prints raw per-pass findings precisely so independence is *observed*, not
inferred. This run's most important result (Pelago) came from reading the per-pass text — pass 1's
blind miss vs passes 2/5's source-directed hits — not from the final field alone. Keep logging passes
on any future live recovery validation.
