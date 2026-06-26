# All-Fields Blink Probe — Spec (scoping which fields get retry-and-union)

**Status:** DRAFT for the repo — design-level. Read-only diagnostic; costs API credits (separate
explicit go). Scopes WHERE to apply the field-agnostic retry mechanism; does NOT block its build.
**Owner of decisions:** Katelynd. **Implementation owner:** Claude Code (has the notebook/harness
context this spec deliberately does NOT assume).

## Why this exists
The retry-and-union mechanism (revenue, N=5) fixes web-search execution variance — the confirmed
cause of missing revenue (figures that existed and predated the run blinked across byte-identical
calls; Midi F T T F F). That variance is CONTENT-AGNOSTIC: it doesn't care which field's figure a
search misses. Revenue is only where we NOTICED it (we had external ground truth + glaring absence).
So other fields are probably affected too — but we have NOT measured which. This probe measures it,
so we apply retry only where the data says it's needed, instead of guessing.

**Rule 8 applies to our own plan:** the per-field expectations below are PREDICTIONS FROM THE
MECHANISM, not measurements. The whole point of the probe is to falsify or confirm them. Do not treat
the predictions as conclusions.

## The two axes that decide whether a field needs retry
1. **Concentrated vs diffuse source.** A figure that lives on ONE specific page (revenue → CB
   Insights/Latka/Growjo) is near-binary: you reach the page or you don't → blinks hard. A signal
   drawn from MANY pages (news, forums, press) is variance-robust: any one surfacing gives a finding.
2. **Recoverable vs genuinely-absent.** Retry only helps if the data EXISTS and is being missed.
   Never-published data (e.g. a growth RATE that was never disclosed) doesn't benefit from retry.

A field earns retry only if it's BOTH concentrated-source AND its misses are recoverable.

## Per-field PREDICTIONS (to be measured, NOT assumed)
| Field | Prediction | Reasoning (a hypothesis to test) |
|---|---|---|
| growth rate | likely HURT | same aggregator/disclosure pages as revenue; Midi's growth blinked ALONGSIDE its revenue |
| paying-customer count | likely HURT | concentrated, lives on similar pages |
| valuation | likely HURT | concentrated (funding/aggregator pages) |
| org-events | likely ROBUST | diffuse — many news sources; any one surfacing suffices |
| operational-strain | likely ROBUST | diffuse — forums/reviews/press across many pages |
| payer/institutional signal | likely ROBUST | diffuse — partnership news spread across sources |
| outcomes/clinical | likely ROBUST | diffuse — studies/press across many pages |
| capability/fit evidence | MIDDLE | partly diffuse (engagement reviews), partly concentrated datapoints |

These are starting hypotheses. The probe's job is to replace this table with a measured blink-rate
per field.

## Method (the locked design; implementation left to Claude Code)
- Reuse the SAME instrument that proved the revenue case: the repeat-A variance probe — run a
  byte-identical config N times per company and watch whether each target figure appears or not.
- Run it 5× per company (matching the revenue probe), on a small company sample.
- KEY DIFFERENCE from the revenue probe: score EVERY field on each run, not just revenue — produce a
  per-field blink map.
- Score per FIELD, per company, per repeat: did this run surface the field's target value? (Y/N)
- **Detection must read meaning, not match tokens.** The keyword/regex approach is contaminated (it
  matched "revenue" inside "no revenue found" and counted funding as revenue). Use the same kind of
  cheap-LLM presence judgment the revenue work landed on — per field. (Implementation/model choice:
  Claude Code, consistent with the absence-check it already built.)
- READ FROM THE TEXT, not auto-marks, when calling close cases — the revenue probe proved auto-marks
  give false positives.

## Company sample (decision: Claude Code to propose final list; constraints here)
- Small (cost-bounded). Span field types: include companies likely to exercise the diffuse fields
  (an org-events/reset case, a strain case) AND the concentrated fields (revenue/growth cases).
- Reuse known reference points where they help: ZOE (reset/org-events canonical), Function Health
  (maturity/commercial canonical), plus a few from the revenue-probe set (Midi/Solace/Pelago) so
  revenue/growth blink is cross-checkable against what we already measured.
- The sample only needs to be big enough to see per-field blink rates clearly, not the whole roster.

## How to read the result (decision rules, set in advance)
For each field, compute its blink rate across the repeats:
- **High blink rate + recoverable** (figure appears some runs, not others, and IS findable) → ENABLE
  retry-and-union for that field (add its config: absence-check + source-directed retry prompt + N).
  N is per-field — re-derive from that field's measured single-pass hit rate, don't copy revenue's 5.
- **Stable-present (≈always found)** → no retry needed; the single pass is reliable.
- **Stable-absent (≈never found)** → likely genuinely-absent / not-published; retry won't help.
  Distinguish this from high-blink by the PATTERN across repeats (genuine-absent = consistent F;
  blink = mixed F/T), exactly as the revenue probe distinguished Pelago (0/5 stable) from Midi
  (2/5 blink).
- **Diffuse fields that turn out robust** (predicted org-events/strain/payer/outcomes) → confirm
  robust, leave on single pass. If any predicted-robust field shows a high blink rate, that's a
  surprise worth heeding — Rule 8, the prediction was wrong, follow the data.

## Growth has a SECOND, separate problem (do not conflate)
Growth is hit by TWO distinct issues that need TWO distinct fixes:
1. **Variance (this probe's scope):** the growth figure blinks like revenue → fixed by retry-and-union.
2. **Coverage (a prompt-wording fix, NOT this probe):** even when growth IS found, the current prompt
   accepts a qualitative "growing" instead of requiring a quantified RATE — so all 55 came back
   "growing." That's a required-output wording change to the growth field, separate from variance.
   The CEO-disclosed rates exist (Pelago 287%, Midi 60→150), so the rate is recoverable once required.
Handle both when growth is enabled; the probe measures #1, the wording change addresses #2. Both are
LLM-facing → design wording jointly before Claude Code builds.

## Scope / non-goals / guardrails
- READ-ONLY. No master/checkpoint/Drive writes. Scratch output only (the revenue probe's pattern).
- Costs real API credits → SEPARATE EXPLICIT GO. (A sustained "rate limit" here usually means out of
  credits, not throttling — check billing first.)
- Does NOT block the revenue mechanism build; it scopes which fields come NEXT.
- The mechanism is already field-agnostic, so enabling a field = supplying its config, not a rewrite.
- Implementation specifics (notebook wiring, harness reuse, exact scoring code, model string, the
  Colab cell structure) are LEFT TO CLAUDE CODE — this spec is design-level and intentionally does
  not assume the codebase or the Colab flow.

## Sequence
1. Build + LIVE-VALIDATE the revenue mechanism first (the proven case end-to-end).
2. THEN run this probe (explicit credit-spending go) → per-field blink map.
3. Enable retry for the fields the map flags (config + per-field N), designing any LLM-facing
   wording (esp. growth's required-rate) jointly.
4. Leave robust fields on single-pass.
