# Search Recovery — Always-Run-N + Union on Web-Search Variance (field-agnostic)

**Status:** APPROVED for build steps 1–2 (Katelynd, 2026-06-25). The **Option-A synthesis
wording** (multi-figure surface-all) is **pending joint review before step 3** — drafted below for
sign-off, NOT yet written into the synthesis. Build red→green, small reviewable commits, nothing
self-merged.
**Owner of decisions:** Katelynd (cleverturnip) · built by Claude Code.

## TL;DR (plain language)

Web searches are a coin-flip on whether they reach the page that holds a figure (Midi revenue 2/5
identical tries; Solace 5/5; Pelago 0/5, genuinely absent). The prompt is good; the cap is fine; the
entity resolves. The fix: **run a fixed N=5 search passes on every company and union everything** —
pass 1 is the proven general search, passes 2–5 lead with the known financial-data sources, all
results merged for the synthesis to judge. One reusable mechanism, revenue first. The retry layer
makes **no quality judgment at all** — quality stays with the verified downstream evidence-confidence
chain.

## What's already settled (don't re-litigate — see the audits)

- `audits/research_revenue_cause_isolation_findings.md` — the spine: hypotheses, matrix, repeat-A.
- `audits/research_prompt_audit.md` — prompt inventory + the two corrections (Mode-A; H3).

H1 (token starvation) and H2 (disambiguation) **falsified**; H3 (web-search execution variance)
**confirmed**. Mechanism is **content-agnostic** → the fix is generic. Detection of "is a figure
present" must read meaning, not match tokens (regex was contaminated).

## The locked decisions

1. **Retry style = HYBRID.** Pass 1 = the existing general search, **verbatim/unchanged**. Passes
   2–5 are **source-directed** (lead with the known financial-data sources). Union means a
   source-directed pass can only *add*, never lose, pass 1's figures.
2. **Execution = ALWAYS-RUN-N + UNION. No conditional stop.** Run a fixed N passes on **every**
   company regardless of pass 1; union all results. Stop-on-hit could quit on a thin single-source
   hit and never reach the corroborating source that would justly raise confidence — a **silent
   recall/confidence miss**, the worst failure for a high-recall surfacing tool. Always-N removes the
   stop decision, so the retry layer makes **no quality judgment** (no "is this thin enough to keep
   going?" verdict that could be wrong). Cost is acceptable at our scale (one-time 55-company regen;
   later research in groups of 5, max 10).
3. **No per-pass absence-check.** With always-N nothing stops early → the per-pass absence-check has
   no gating job and is **removed**. Its only descendant is a **single end-of-union presence check**,
   **observability-only** (§Observability) — it gates nothing, judges no quality.
4. **Pass count N = 5 for revenue** (LOCKED; per-field config). Worst-case recovery floor >90% (Midi
   p=.40 → 92%), higher in practice since passes 2–5 are source-directed.

## Architecture — a new wrapper layer (and why NOT inside `call_openai`)

`call_openai` (research_runner.py:70) is deliberately **content-agnostic**; its blank-guard knows
nothing about "revenue," and that's worth keeping. So we add a **new thin layer that wraps the
`search_*` functions**, leaving `call_openai` and its blank→`SEARCH_FAILED_MARKER` guard untouched.
Each pass still calls `call_openai`, whose inner blank-guard still protects that pass.

```
search_with_recovery(search_fn, research_query, *, client, model,
                     retry_prompt_builder, presence_check, field, n_passes=5):

    findings = [("pass1 (general)", search_fn(research_query, client, model))]
    for p in 2..n_passes:                      # ALWAYS run all (no stop)
        findings.append(("passP (source-directed)",
                         call_openai(retry_prompt_builder(query), web_search=True)))

    real = [f for f in findings if it is not a SEARCH_FAILED_MARKER and not blank]
    if not real:
        return SEARCH_FAILED_MARKER, provenance(n_passes, figure_present=False)  # all failed
    union_text = concat_labeled(real)          # preserve everything; markers excluded
    figure_present = presence_check(union_text)  # OBSERVABILITY ONLY — gates nothing
    return union_text, provenance(n_passes, figure_present)
```

- `retry_prompt_builder` and `presence_check` are **per-field config** — what makes it reusable.
- The unioned finding flows into the **existing fit-brief synthesis** — see §Multi-figure.

## Union merge (preserve everything; the synthesis adjudicates)

Concatenate passes' findings, labeled, into the free-text `commercial_scale_finding`. **Do not
collapse conflicting figures** (Midi's $115.9M Latka and $150M CB Insights are both kept). The full
union is preserved in the free-text column **regardless of the structured field.** Rule 7: evidence
persists; deterministic rules decide.

## Multi-figure structured surfacing — Option A APPROVED, with the carry-and-rate precision fix

**Verified current behavior (Rule 8 — read, not assumed).** The schema field is
`"revenue_or_arr": "figure + source/date, or empty if none found"` (research_runner.py:864) —
singular, **no credibility qualifier**, empty only "if none found." `q4_evidence_quality` has an
explicit **`unverified-promotional`** bucket (research_runner.py:572–575). So the design intent is
**carry-and-rate** — capture a figure and rate its quality via q4/evidence_confidence — **not** drop
weak figures. **But that behavior is IMPLICIT** (there is no instruction "include even a weak/single-
source figure"), so it is not guaranteed; `:508` ("do not overvalue … vague growth claims") could
nudge the LLM to omit. Verdict: **it carries today (by design), but unguaranteed → make it explicit.**
Not a clear pre-existing bug; an under-specified behavior we harden.

**Residual (prompt-vs-runtime) — captured, not assumed closed:** this verdict was verified at the
PROMPT level only, not at runtime. Option A makes it moot by *forcing* carry-and-rate. But if a
company known to have a thin/single-source figure ever returns an empty `revenue_or_arr` post-build,
this prompt-vs-runtime gap is the first place to look (a cheap live spot-check would settle it).

**The rule to encode (the precision fix): credibility RATES, it does not FILTER.** The failure to
avoid: one thin/low-credibility figure is the only thing found; if only "credible" figures are
carried, that real-but-weak figure is dropped → `revenue_or_arr` empty → `_has_real_evidence`
(presence-only, structured_evidence.py:145) reads "no revenue at all" → WEAK collapses into NO, and
the figure **escapes the entire evidence-confidence safety chain** (which can only rate a figure that
is PRESENT). WEAK and NO must route differently:
- WEAK → figure PRESENT, rated low by evidence_confidence/q4 → gated/flagged, visible for review.
- NO → genuinely empty.

**Draft schema/instruction wording for your joint review (NOT yet written into the synthesis):**
- Schema field: `"revenue_or_arr": "List ALL revenue/ARR/run-rate figures found, each with source,
  date, and type (company-reported / credible-estimate / implied-from-pricing / weak-single-source).
  Empty ONLY if NO real figure was found in any pass."`
- Instruction line: *"List every revenue/ARR/run-rate figure a source actually stated or credibly
  implied — including weak or single-source figures. Do NOT omit a real figure for being low-quality;
  quality is captured by evidence_confidence_score and q4, never by exclusion here. Leave the field
  empty only if no real figure was found at all."*

**Discipline:** LLM-facing + calibration-pending → highest-stakes. Wording is finalized **with
Katelynd** before it is written. It lands as its **own commit** (build step 4). The **core mechanism
does NOT depend on it** — the mechanism works on the free-text union regardless; this only improves
the structured surface. Forward requirement recorded: Part-C numeric calibration MUST handle multiple
figures.

## Recovery math under always-run-N

Each pass ~ Bernoulli(p), p = per-pass probability the search surfaces ≥1 revenue figure (grounded by
the repeat-A experiment: 5 independent identical calls). Midi blind p ≈ 0.40.
- **Recovery — P(≥1 figure in N) = 1 − (1−p)ⁿ.** Same as stop-on-hit at the same N (both recover iff
  any pass hits). Always-N's recall gain comes from being free to set N higher (cost is fine).
- **Corroboration — E[figure-bearing passes] = N·p.** What always-N adds: multiple sources → the
  synthesis's corroboration→confidence logic engages; no early-stop confidence loss.

| N | Midi recovery (p=.40) | Midi E[hits] |
|---|---|---|
| 3 | 78% | 1.2 |
| 4 | 87% | 1.6 |
| **5** | **92%** | **2.0** |

**N = 5 (locked).** 92% on the worst observed recoverable case + ~2.0 expected figures. Conservative
floor — table uses *blind* p; passes 2–5 are source-directed → real p higher → recovery ≥ table.

## Revenue config (the first instance)

- `search_fn` = `search_commercial_scale` (research_runner.py:252), pass 1 verbatim.
- `retry_prompt_builder` = a NEW source-directed prompt (passes 2–5) that **leads with** CB Insights /
  Latka / Growjo / PitchBook / Sacra financials — as a **LEAD, not a filter** (§Gate-2). Web search on.
- `presence_check` = a cheap `gpt-5.4-mini` call (no web search), **observability only**: "does the
  union contain a revenue/ARR/run-rate/GMV figure — company-reported, credible third-party estimate,
  OR implied from paying-customers × pricing — vs funding, valuation, or list price alone?"
  Implied-from-pricing **counts as present**. Makes no quality call.
- `n_passes` = 5.

## Boundary discipline (load-bearing)

- **The retry layer GATHERS; it makes NO downstream-confidence or quality judgment.** No stop logic,
  no thin-vs-solid verdict, no figure selection. It runs N passes and unions.
- **The synthesis remains the SOLE authority** on `evidence_confidence_score`, `q4_evidence_quality`,
  and final figure representation.
- **Quality (thin vs solid) is handled ONLY by the verified downstream chain** (§Gate-1). That is the
  whole reason we chose always-N over a corroboration-aware stop.

## Gate-1 boundary line (verified — presence ≠ quality)

The presence check judges **presence, not quality.** Revenue-quality routing is the **verified**
downstream chain, load-bearing in tiering: `evidence_confidence_score` keeps confidence moderate for
single-source/estimated revenue (research_runner.py:752) and **gates tiers** (P0 ≥60, P1 ≥55; <50 &
pmf<70 → P3 — :690,:708), enforced deterministically (candidate_priority.py:226,:315);
`q4_evidence_quality` `unverified-promotional` is a **hard gate** out of "strong"
(structured_evidence.py:208–219); calibration flag `"REVIEW: D2C scale claim with moderate/weak
evidence confidence"` fires at pmf≥75 & evidence<60 (priority.py:402).

## Gate-2 — source hints are a LEAD, never a FILTER (verified house pattern; hardened here)

The retry prompt MUST (a) lead with the named aggregators, **and** (b) still ask for **company-
disclosed figures wherever they live — press releases, crowdfunding disclosures, founder
interviews** (our recoveries prove it: **ZOE → Crowdcube; Pelago → press release** — neither an
aggregator), and (c) never restrict to the five. Mandatory in the retry-prompt design.

## Edge cases

- **`SEARCH_FAILED_MARKER` in a pass** (total blank after `call_openai`'s own retry): excluded from
  the union (contributes nothing); other passes still ran. If **all** passes are markers/blank, the
  marker is returned so downstream `is_search_failure()` distinguishes *failed search* from *no-revenue*.
- **Genuine absence (Pelago):** all N find real text but no figure; union has no figure; synthesis
  emits empty `revenue_or_arr` (correct). Cost = N passes; acceptable.
- **Conflicting figures:** kept side-by-side (§Union, §Multi-figure).

## Observability / provenance (log-only — confirmed redline)

Per company, log `{field, n_passes, figure_present}` (and, cheaply, the **Mode-B cross-check**:
`figure_present` True but synthesis `revenue_or_arr` empty ⇒ the synthesis dropped a figure the union
had). Neither gates anything. No master column in this change.

## Scope / non-goals

- **Launch = revenue ONLY.** Mechanism generic; only revenue wired on first.
- **Do NOT** modify `call_openai`'s blank-guard or content-agnostic nature.
- **Do NOT** change any **pass-1** search prompt wording.
- **No** master/checkpoint/Drive writes from this mechanism → resume/idempotency unaffected.
- **Core mechanism does NOT depend on the §Multi-figure synthesis change** (separate commit / sign-off).
- Not a revenue special-case in code — revenue is one config of a generic function.

## The all-fields blink probe (separate, read-only — scopes WHERE to apply; does NOT block build)

After revenue lands, re-run the 5×-identical probe scoring **every** field → per-field blink-rate map;
apply always-N to high-blink + recoverable fields. **Costs API + credits** → separate explicit go (a
sustained "rate limit" there usually means *out of credits* — check billing).

## Test plan (red→green, fake injected client — no real API, no spend)

1. Always runs exactly **N** passes regardless of pass-1 result (success AND absent cases).
2. Union concatenates **all** real passes' text, labeled, order preserved.
3. Union preserves **conflicting** figures (both $115.9M and $150M present).
4. A `SEARCH_FAILED_MARKER` pass contributes nothing but does not abort others; if **all** fail, the
   marker is returned (so `is_search_failure()` holds).
5. `presence_check` is observability-only: its result changes provenance, **never** pass count or
   union content.
6. Revenue presence-check **prompt shape** is correct (includes the union, instructs to exclude
   funding/valuation/list-price, treats implied-from-pricing as present, no web search) and its
   **parsing** maps PRESENT→True / ABSENT→False. *(The LLM's actual funding-vs-revenue separation is
   an LLM judgment validated by live spot-check, not a unit test — Rule 8 honesty.)*
7. Revenue retry prompt is **lead-not-filter**: names the five aggregators AND carries the non-
   aggregator clause (press release / crowdfunding / founder interview / "do not restrict"),
   interpolates the query, and is issued with web search ON.
8. Provenance records `field`, `n_passes`, `figure_present`.
9. (Step 4, after sign-off) synthesis surfaces **all** figures incl. weak/single-source; empty only
   if none found.

## Build sequence (small commits; each reviewed; nothing self-merged)

1. **This spec** — committed with the audit docs (first commit on the branch).
2. Generic `search_with_recovery` (always-N + union + provenance + presence-check seam) + tests
   1–5,8. No wiring.
3. Revenue config (source-directed retry prompt + observability presence check) + tests 6–7.
4. **(After joint sign-off on wording)** synthesis multi-figure surface-all (carry-and-rate) — **own
   commit** + test 9.
5. Wire revenue into the batch research path behind the wrapper; integration test; confirm
   resume/idempotency unchanged.
6. (Separate go) all-fields blink probe → scope next fields.
7. Add growth-rate config when the probe justifies it (config, not a rewrite).

## Confirmed redlines (locked)

- **Union = preserve all figures ✓**
- **Provenance = log only (no master column now) ✓**
- **Implied-from-pricing = present ✓** (applies to the observability presence check)
- Gate-1 boundary line ✓ · Gate-2 non-aggregator hardening ✓

## Future (not in this build)

- **Part-C numeric size-calibration MUST handle multiple figures** in `revenue_or_arr` (hard
  requirement so the §Multi-figure gap can't resurface silently).
- **One search, several fields:** later fields sharing `search_commercial_scale` run the N passes once
  and check each field independently — don't re-run per field.
