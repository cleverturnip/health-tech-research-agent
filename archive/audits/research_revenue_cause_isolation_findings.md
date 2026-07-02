# Findings — Missing-Revenue Cause Isolation (search_commercial_scale)

**Date:** 2026-06-25
**Type:** Read-only diagnostic. No prompt/code/data edits. No master/checkpoint writes.
**Status:** H1 and H2 FALSIFIED; H3 leading explanation, pending a repeat-A variance confirmation.
**Repo home (suggested):** `audits/research_revenue_cause_isolation_findings.md`
(this sharpens, and should be cross-linked from, `audits/research_prompt_audit.md`).

---

## 1. The question
Why did the v4.2 research run leave `revenue_or_arr` empty for ~42% of the roster, when a live
probe showed several of those companies (Midi, Solace, Pelago, ZOE) DO have credible revenue or
revenue-growth figures that PREDATE the run? Distinguish fixable causes from genuine non-disclosure.

## 2. Hypotheses tested
- **H1 — token starvation:** the search found the figure but the 700-token output cap left no room
  to report it.
- **H2 — decoy/disambiguation:** raw `{research_query}` let wrong-entity results ("Zoe Nutrition"
  reseller, "Levels" studio) pollute the search and suppress attribution.
- **H3 — web-search execution variance:** the prompt/cap/entity were all fine; the third-party
  financials page (CB Insights / Sacra / Growjo) simply did or didn't surface that run.

## 3. Method — 4×4 cause-isolation matrix
Ground-truth set (figures predate the June 2026 run): Midi ($150M run-rate, was $60M end-2024),
Pelago (287% '23; 11x since Series B; no $ base), Solace (~$10M run-rate '25), ZOE (~$80M ARR; 88k
paying). Four conditions, one variable changed at a time (D stacks all):

| Cond | Prompt | Token cap | Query |
|---|---|---|---|
| A control | verbatim | 700 | raw |
| B | verbatim | 1800 | raw |
| C | verbatim | 700 | disambiguated |
| D | verbatim + required-growth-rate | 1800 | disambiguated |

16 calls to `search_commercial_scale` only; scratch CSV; no writes.

## 4. Critical methodology note — auto-marks were contaminated
The automated `ARR_found` / `has_$figure` flags were keyword/regex based and gave FALSE POSITIVES:
they matched generic tokens ("revenue", "ARR", "run-rate") and `$`-figures that were actually
FUNDING ROUNDS or PRICING, not revenue. Example: a finding stating "No credible third-party revenue
estimate found" was marked True (contains "revenue"); "$100M Series D" was marked a $-figure.
**Conclusion was therefore drawn from READING THE FULL FINDING TEXT, not the marks.** (Lesson:
keyword presence ≠ figure presence; verify against text.)

## 5. What each condition ACTUALLY recovered (from the text)
| Company | A_control (700) | B_tokens1800 (1800) |
|---|---|---|
| Midi | funding ($100M Series D) + 230k patients; **"no credible third-party revenue estimate found"** ❌ | **$150M / $115.9M revenue** (CB Insights, Growjo) ✅ |
| Solace | **$10M revenue** (CB Insights) ✅ | $130M Series C funding; **"did NOT find disclosed revenue"** ❌ |
| ZOE | 100k+ paying members; **no revenue figure** ❌ | pricing only; **"CB Insights revenue $0"** ❌ |
| Pelago | 287% growth; "no absolute revenue disclosed" (CORRECT — none exists) | 287% growth; funding; still no $ base |

## 6. Verdict — H1 and H2 FALSIFIED; H3 leading
**H1 (token starvation) — FALSIFIED.** Two independent disproofs:
1. Condition-A findings ran ~1,600–2,000 chars vs a ~2,800-char (700-token) budget and ENDED
   NATURALLY with an affirmative "no revenue estimate found" — not truncated mid-figure. The
   starvation mechanism ("found it, no room to print") did not occur; the model had room to spare.
2. **Solace REVERSED:** A(700) found the $10M, B(1800) lost it. More tokens can NEVER lose a figure
   under starvation. Combined with Midi (A miss, B hit), the cap helped one company and hurt
   another — mean effect ≈ zero, high variance: the signature of a non-causal variable.

**H2 (disambiguation) — FALSIFIED.** Every condition resolved the RIGHT entity; C ≈ A on recovery.
These are well-known companies; the raw name was never the failure point.

**H3 (web-search execution variance) — LEADING EXPLANATION.** The revenue figures live on
third-party-estimate pages (CB Insights / Sacra / Growjo) that surface or don't, run to run. The
prompt asked correctly, the budget sufficed, the entity resolved — the financials page just didn't
load that run. The empty field's cause is UPSTREAM of both the prompt and the cap.

**Side effect of the cap (real but not a revenue fix):** raising 700→1800 reliably 3–4×'d output
LENGTH (richer funding/pricing context) but did NOT reliably recover revenue, and sometimes shifted
the search OFF the revenue source (Solace). A cap bump is not a revenue fix.

**Growth-rate instruction (condition D) — INCONCLUSIVE.** Midi and ZOE stayed growth-absent even in
D, but confounded by the same source variance (the rate-bearing source didn't surface). Pelago
reported 287%/11x cleanly in ALL conditions with no addendum. Test cannot yet credit the
required-rate instruction. Keep as cheap hygiene; do not bank on it.

## 7. Implication for the fix (design later, jointly — NOT prescribed here)
The lever is SEARCH ROBUSTNESS, not prompt wording. Candidate direction: extend the existing
empty-output retry guard from "retry on TOTAL blank" to "retry on REVENUE-ABSENT", and UNION figures
across retries — optionally a source-directed follow-up explicitly hitting CB Insights / Sacra /
Growjo / PitchBook. This is an LLM-facing / pipeline change → design wording + behavior jointly in
chat before Claude Code builds. Not specified in this artifact.

## 8. OPEN — confirmation required before building
This matrix is N=1 per cell; the entire conclusion rests on "it's variance." Confirm with a
**repeat-A variance test**: one fixed config (verbatim prompt, 700 cap, raw query) run 5× each on
Midi and Solace.
- If the revenue figure BLINKS IN AND OUT across identical repeats → variance confirmed as dominant
  → build retry-and-union with confidence.
- If recovery is STABLE across repeats → the variance story is wrong; reopen the investigation.
(Cell being produced by Claude Code.)

## 9. Methodological lesson (carry forward)
Absence in our own output is the symptom that H1/H2/H3 (and earlier, Mode A vs Mode C) ALL share.
It is an UPPER BOUND on "genuine non-disclosure," never a measurement, until a live test
discriminates the causes. Two attributions ("78% Mode C"; "weak source-targeting") were overturned
this way. Prefer controlled live probes over reading prompts/outputs when live recovery is possible.

---

## 10. UPDATE — repeat-A variance test: H3 CONFIRMED (2026-06-25)
The N=1 open item in §8 is now closed. Repeat-A (verbatim prompt, 700 cap, raw query) run 5× on
each company:

| Company | repeats 1–5 | rate | reading |
|---|---|---|---|
| Midi | F T T F F | 2/5 | The figure BLINKS. Identical config, ~40% single-pass hit, two DIFFERENT sources on the two hits ($115.9M Latka, $150M CB Insights). |
| Solace | T T T T T | 5/5 | Stable recovery. The matrix's Solace-B miss was the low-amplitude tail of the same variance. |
| Pelago | F F F F F | 0/5 | Stable absence — the control behaves, so the blink is real signal, not generic model noise. |

**Dispositive:** Midi misses a recoverable figure 3 of 5 times with nothing varying but the web
search's result set. That IS the original v4.2 missing-revenue mechanism — search is a coin-flip on
whether it reaches the financials page that run. H1/H2 already falsified (§6); H3 now confirmed.

## 11. The fix — retry-and-union on revenue-absent (now data-justified; design jointly before build)
When `search_commercial_scale` returns NO revenue figure, re-search and UNION figures/sources across
attempts. Extends the existing `call_openai` empty-output guard from "retry on total blank" →
"retry on revenue-absent." Lifts growth-rate recovery for free (more passes → more chances the
trajectory source surfaces).

Recovery math from the Midi 40%/pass worst case: 64% / 78% / 87% at 2 / 3 / 4 bounded passes.
Cost is self-targeting: success-cases and stable recoverers (Solace) hit pass 1 and pay nothing;
only revenue-absent findings retry, stopping on first hit (~2.5 calls avg for the hard case).
Genuinely-absent companies (Pelago) burn the full budget for nothing — unavoidable, since "absent"
and "not-yet-surfaced" are indistinguishable until you try.

**The one real design fork: blind re-roll vs source-directed retry.** CB Insights was the recurring
winner (Solace 5/5; Midi's $150M); Latka/Growjo carried others. A retry that explicitly leads with
"check CB Insights / Latka / Growjo financials for {company}" may have a far higher per-attempt hit
rate than re-rolling the same nondeterministic search — but it hard-codes source assumptions.
Decide together.

**Discipline:** this is a code change to a deterministic tool → plan-before-acting gate. No
`research_runner.py` edits until the spec is designed and approved. Build red→green with tests.

## 12. Open (independent of building the fix)
Roster-wide repeat-A recovery probe across the remaining ~23 missing-revenue companies → how many
are recoverable-via-retry vs genuinely absent. Scopes the #6 re-research + the evidence-confidence
flag. NOT a blocker for building retry-and-union.

## 13. GENERALIZATION — the variance is not revenue-specific (scoping the fix)
The confirmed mechanism (web-search nondeterminism) is CONTENT-AGNOSTIC: it doesn't care which
field's figure it misses. Revenue is merely where we noticed it (external ground truth + glaring
absence). So the fix is designed GENERICALLY and applied per-field where warranted — NOT as a
revenue special-case.

Whether a field is actually hurt (and whether retry helps) turns on two axes:
1. **Concentrated vs diffuse source.** Revenue = one specific page (CB Insights/Latka/Growjo) →
   near-binary → blinks hard. Diffuse fields (org-events, strain, payer, outcomes — many sources) →
   variance-robust. Blink hurts concentrated fields most.
2. **Recoverable vs genuinely-absent.** Retry only helps if data exists and is missed (Midi). Never-
   published data (rate-less growth_signal) → retry burns budget (Pelago).

Per-field expectation: revenue YES/YES (proven). Likely YES/YES: growth-rate (same pages; Midi's
growth blinked WITH revenue), paying-customer count, valuation. Likely NO (diffuse/robust): org-
events, strain, payer, outcomes. Company-fit/capability = MIDDLE (mixed).

**Scoping step (read-only, cheap):** re-run the 5× repeat-A probe but SCORE EVERY FIELD → a per-
field BLINK-RATE map. Apply retry-and-union to high-blink + recoverable fields only. Build the
mechanism field-agnostic so adding a field is config, not a rewrite. Not a blocker for building the
mechanism — it scopes WHERE to apply it.
