# Research-Batch Search-Prompt Audit (READ-ONLY diagnosis)

**Date:** 2026-06-25 · **Mode:** read-only investigation; no prompt/code/spec/data changes proposed or applied.
**Inputs:** package prompts in `src/health_tech_research_agent/research_runner.py` (live `run_research_batch` path); evidence = `v42_full_regen_clean_slate_20260622_full56_checkpoint (2).csv` (the 55-row research export; cross-read prompt wording vs. what landed in each `fit_brief_json.commercial_evidence` field vs. the free-text `commercial_scale_finding`).

**Failure modes (kept distinct):** **(A)** prompt-coverage — never asks / asks weakly; **(B)** extraction/synthesis — the value is in raw/free-text but the synthesis didn't lift it into the structured field; **(C)** source/recency — asked correctly but the data doesn't exist / postdates the run.

---

## ⚠️ CORRECTION (2026-06-25 live calibration probe) — the "~78% Mode C" headline in §4 is SUPERSEDED

A follow-up **live disambiguated search** on companies this audit marked "genuine non-disclosure (Mode C)" **falsified the headline.** This audit attributed Mode C from **absence** ("no figure in our free-text → genuine non-disclosure") — but absence-from-our-prose is the symptom Mode A (search under-recovery) and Mode C (genuine absence) **share**, and is not distinguishable from the batch output alone. The probe ran the disambiguating test this read-only audit could not.

**Probe result — 4/4 audit-"Mode C" companies had disclosed revenue that PREDATES the run:**

| Company | Model | Probe finding | Source quality |
|---|---|---|---|
| Midi Health | B2B2C payer | $150M run-rate (up from $60M end-2024); $115.9M rev Sep'25; 20k pts/wk | CEO-disclosed + Latka + TIME — multi-source, **predates run** |
| Solace Health | B2B2C payer | ~$10M run-rate by 2025; 20k pts/mo | trade press — single-source on the $10M |
| Pelago | B2B2C payer | 287% rev growth 2023; 11x since Series B; 3.4M eligible lives | CEO-disclosed (BusinessWire/TechCrunch); growth-rate, not $ base |
| ZOE (ref) | B2C | $80M ARR; 88k paying | Crowdcube (company-disclosed, **~Oct 2025 — ~8 mo BEFORE the June 2026 run**) + Latka |

**Corrected conclusions:**
- **The ZOE row in §3 is wrong.** Its Crowdcube disclosure **predates** the run (~Oct 2025), so it is a **search-miss (Mode A)**, not a timing/postdates case (Mode C). That timing error propagated the C attribution (and the §4 logic that "re-research helps only where data has since appeared").
- **"~78% Mode C" was an upper bound on figure-absent-from-our-prose, not a measurement of non-disclosure.** A meaningful fraction is **recoverable Mode A (search under-recovery)** — the data exists and predates the run; the SEARCH step didn't surface it (trade-press / CEO-interview disclosures: Femtech Insider, MobiHealthNews, TechCrunch), and `{research_query}` carries no disambiguation guard against decoy entities.
- **What still holds (now the leading cause):** the per-prompt findings in §2/§5 are unchanged and *vindicated* — the synthesis **does** lift revenue when it is in the free-text (the success cases), so the failure is **upstream, in search recovery** (Mode A: no disambiguation, weak source-targeting, no required growth-RATE). The missing-revenue gap is therefore **substantially Mode A (cheap — a search-PROMPT fix), not predominantly genuine non-disclosure.**
- **Not yet measured:** the true roster-wide recovery rate (probe n=3 + 1 ref, deliberately drawn from the payer set to test the audit's strongest claim, not to estimate the global rate). It proves "78% genuine" is wrong; it does **not** prove "0% genuine" — **Affect** remains the likely genuine-absent example. The real Mode-C count needs the probe run across the remaining ~23 (~1 search each) **before** committing research spend.

*The fix is an LLM-facing search-prompt change (disambiguation + trade-press/CEO source-targeting + mandatory growth-RATE) — to be designed jointly in chat, then handed to Claude Code. Not designed or applied here.*

## ⚠️ UPDATE 2 (2026-06-25 cause-isolation test) — H1/H2 rejected; H3 (web-search execution variance) is the cause

UPDATE 1 established the gap is **Mode A (search under-recovery), not genuine non-disclosure**, and proposed a search-PROMPT fix (disambiguation + source-targeting + mandatory growth-RATE). A controlled **cause-isolation test** then probed *which* mechanism drives Mode A — and **rejects the prompt-wording hypotheses, isolating run-to-run search variance.**

**Design — 4×4 matrix, 16 live calls to `search_commercial_scale` only** (read-only; scratch CSV; no master/checkpoint/Drive writes). One variable changed per condition vs. the live control:
- **A (control):** verbatim prompt · 700 tokens · raw `{research_query}` = the exact live config (the function hardcodes 700). H3 baseline.
- **B:** verbatim · **1800 tokens** · raw. (H1 token starvation.)
- **C:** verbatim · 700 · **disambiguated query** (name + founder + HQ + category + domain). (H2 decoy/entity.)
- **D:** verbatim **+ required growth-RATE line** · 1800 · disambiguated. (Full proposed fix.)
- Companies (revenue exists; figures predate the run): Midi Health, Pelago, Solace Health, ZOE. **N=1 per cell** (the limitation — see repeat-A below).

**Result — reading the findings (the keyword/`$` auto-pivots were contaminated by funding & pricing `$`, and read as "all recovered"; the text does not):**

| Company | A_control (700, raw) actually recovered | B (1800, raw) actually recovered |
|---|---|---|
| Midi | $100M Series D + 230k patients; **"no third-party revenue estimate found"** — ❌ revenue | **$150M / $115.9M revenue** (CB Insights, Growjo) — ✅ |
| Pelago | 287% growth; "no absolute revenue disclosed" (correct — none exists) | 287% growth; + $58M/$151M **funding** (no revenue $) |
| Solace | **$10M revenue (CB Insights financials)** — ✅ | $130M Series C **funding**; **"did NOT find disclosed revenue"** — ❌ |
| ZOE | 100k+ paying members; "no revenue figure" — ❌ ARR | $99.99 **pricing**; "No strong commercial-scale evidence"; "CB Insights revenue $0" — ❌ ARR |

**Two facts decide it:**
1. **Condition A was never truncated.** Every A finding ran ~1.6–2.0k chars against a 700-token (~2.8k-char) budget and ended *naturally* with an affirmative "no revenue estimate found" — not clipped mid-figure. Token starvation means "found it, no room to report it"; the text shows the opposite (room to spare; the *search* didn't surface it).
2. **Solace reversed: A (700) found the $10M, B (1800) missed it — and Midi reversed the other way** (A miss, B hit). Under token starvation more tokens can never *lose* a figure. Across the two companies where revenue exists and sometimes surfaces, the cap helped one and hurt the other → mean cap-effect ≈ 0, variance high.

**Verdict:**
- **H1 (token starvation): REJECTED.** A wasn't truncated; B/D *lost* a figure A found. The cap reliably changes output **length** (A ~1.6–2k chars vs B/D ~6–8k chars) but **not which figures surface.** → A cap bump is **not** a revenue fix, and can shift the search off the revenue source.
- **H2 (disambiguation): REJECTED.** Right entity in every condition; C ≈ A on recovery. These are well-known companies; the raw name resolved fine. *Refines UPDATE 1: disambiguation and source-targeting were hypotheses — they do not survive the test. The prompt already names CB Insights/Sacra/etc.; the open question is whether a given run **reaches** those pages.*
- **H3 (web-search execution variance): the cause (strongly indicated; N=1 per cell → repeat-A confirmation pending).** Recovery is governed by which third-party-estimate pages (CB Insights, Growjo, Sacra) the web search surfaces on a given run — non-monotonic with tokens, inconsistent across runs. Stable only where the source is easy and the absence is real (Pelago: 287% on a press release, every condition).
- **Growth-RATE addendum (Condition D): UNPROVEN here.** Midi/ZOE stayed rate-absent even in D, but confounded by the same variance (the rate-bearing source didn't surface). Pelago reported 287%/11x in all four conditions with no addendum. Keep the required-rate line as cheap hygiene; this test does not validate it.

**Implication (supersedes UPDATE 1's "search-PROMPT wording" framing):** the lever is **search ROBUSTNESS, not wording** — when a finding returns revenue-absent, **retry the search and UNION figures across attempts** (optionally a source-directed follow-up explicitly hitting CB Insights / Sacra / Growjo / PitchBook). This extends the existing `call_openai` empty-output guard from "retry on *total blank*" to "retry on *revenue-absent*." Design is a joint-in-chat task; not applied here.

**Repeat-A confirmation (2026-06-25 — RESULT): H3 confirmed.** One fixed config (verbatim · 700 · raw) run 5× each, watching the revenue figure across byte-identical calls:

| Company | revenue $ surfaced (repeats 1–5) | rate | reading |
|---|---|---|---|
| **Midi Health** | `F T T F F` | **2/5** | **BLINKS** — same prompt/cap/query, intermittent recovery; the two hits came from *different* sources ($115.9M Latka; $150M CB Insights). Single-pass ≈ 40% → a production "miss" on Midi is expected, not a defect. |
| **Solace Health** | `T T T T T` | 5/5 | Stable recovery ($10M CB Insights every run). The matrix Solace-B miss (1800 tokens) was the low-amplitude tail of the same variance. |
| **Pelago** (control) | `F F F F F` | 0/5 | Stable absence (287% growth, no revenue $ — none exists). Proves the blink is signal, not generic model noise. |

Midi's `F T T F F` across five identical calls is dispositive: nothing varied but the web search's nondeterministic result set, yet a single pass missed a recoverable figure 3/5 times. **This is the mechanism behind the original v4.2 missing-revenue, and it is addressed by retrying and unioning — not by any prompt/cap/entity change.**

**Design parameters this yields for retry-and-union:** worst-case single-pass hit ≈ 40% (Midi) → bounded-retry recovery 1−0.6ⁿ ≈ **64% (2 passes) / 78% (3) / 87% (4)**; retry fires only on a revenue-absent finding and stops on first hit (avg ~2.5 calls to first hit for the hard case; success-cases and stable recoverers like Solace pay nothing; genuinely-absent like Pelago pay the full bounded budget for nothing — the unavoidable cost of not being able to distinguish "absent" from "not-yet-surfaced" without trying). CB Insights is the recurring winner across hits → a **source-directed retry** (lead the retry with CB Insights / Latka / Growjo financials) may beat a blind re-roll per attempt — the key open design choice. Unioning also lifts growth-RATE recovery as a side effect (more passes → more chances the trajectory source surfaces). *Fix design is a joint-in-chat task; not applied here.*

---

## 1. Prompt inventory (every live search prompt + what it owns)

| Function | File:line | Output column | Owns (research columns) | Web search | Recency window |
|---|---|---|---|---|---|
| `search_funding` | research_runner.py:153 | `funding_finding` | funding stage, IPO status, raise/total/valuation, founding year — **explicitly context-only; structurally excluded from the commercial signal** | yes | none |
| `search_payer_signal` | research_runner.py:187 | `payer_institutional_finding` | institutional distribution: payer/employer/provider, named customers, covered lives | yes | none |
| `search_outcomes` | research_runner.py:220 | `outcomes_finding` | clinical/RWE/engagement/retention/utilization evidence | yes | none |
| **`search_commercial_scale`** | **research_runner.py:252** | **`commercial_scale_finding`** | **revenue/ARR/run-rate, paid-users/subscribers, growth, pricing/rev-per-user, business model** (the revenue gatherer — FREE-TEXT) | yes | **none** |
| `search_org_events` | research_runner.py:297 | `org_events_finding` | reset/restructuring events (feeds reset signal) | yes | **"LAST 12–18 MONTHS" (decisive)** |
| `search_operating_characteristics` | research_runner.py:351 | `operating_characteristics_finding` | product-engagement structure + operational strain (also gathers recurring-vs-one-time revenue structure) | yes | none |
| `build_fit_brief_prompt` / `run_company_fit_brief` | research_runner.py:475 / :924 | `fit_brief_json` | **THE SYNTHESIS** — emits structured `commercial_evidence` (`revenue_or_arr`, `paying_customer_count`, `revenue_per_user`, `growth_signal`, `business_model_type`, `q1–q4`) + scores + taxonomy | no (synthesis) | n/a |
| `_build_latest_status_findings` | research_runner.py:1003 | (assembler) | concatenates the 6 findings into the synthesis input | n/a | n/a |

**Ownership note (load-bearing):** the structured revenue fields are **not owned by any single search** — `search_commercial_scale` *gathers* them into free-text, and the **fit-brief synthesis *extracts*** them into `commercial_evidence`. A structured field with no synthesis extraction would silently stay empty. This split is where mode B can hide.

---

## 2. Per-field coverage matrix

### `revenue_or_arr` — owner: `search_commercial_scale` (gather) → fit-brief (extract). Verdict: **STRONG coverage; NOT a mode-A gap.**
`search_commercial_scale` asks explicitly (research_runner.py:259-267), verbatim:
> - company-reported revenue, ARR, run-rate, GMV, sales, transaction volume, or bookings
> - credible third-party estimated revenue or revenue run-rate
> - … - implied annualized revenue from paid customers × pricing, when direct ARR is not disclosed

Output format (research_runner.py:279-284): *"Return a structured list… For EACH figure include: the value, with date… the SOURCE TYPE… the TREND or history… Cover, where available: revenue / ARR / run-rate…"* Fit-brief extract instruction (research_runner.py:566): *"Capture revenue/ARR and PAYING-customer counts with sources."* Schema (research_runner.py:864): `"revenue_or_arr": "figure + source/date, or empty if none found"`.
**Coverage verdict:** asks for company-reported **and** estimated **and** implied-from-pricing — three fallbacks. The field is well-specified. Missing revenue is therefore **not** because the prompt fails to ask.

### `growth_signal` / growth-RATE — owner: `search_commercial_scale` → fit-brief. Verdict: **rate is gathered but NOT required (mode-A on the structured side).**
Search asks (research_runner.py:263, :282): *"year-over-year revenue growth, subscriber growth…"* and *"the TREND or history (e.g. '200k subscribers, up from ~50k in 2023')."* But the structured field accepts qualitative: schema (research_runner.py:867) `"growth_signal": "growing / flat / declining (+ rough rate if available)"` — **rate optional.** In the data **all 55 = "growing"** (often "exact rate unverified"); a quantified rate lands only when one is public (function `~450% YoY`, omada `+53% YoY`). **Verdict:** the YoY rate is *asked for in the search* but the *structured field does not require it*, so it usually degrades to a non-discriminating "growing."

### `paying_customer_count` — owner: `search_commercial_scale` → fit-brief. Verdict: **paying-ONLY by design — no home for non-paying/free-user scale (coverage gap, mode A).**
Search asks (research_runner.py:262) for *"paid users, subscribers, members, customers, covered lives…"* Fit-brief schema (research_runner.py:865): `"paying_customer_count": "PAYING users/subscribers/members/customers only (exclude free/trial/pilot/waitlist) + source, or empty"` and instruction (:566) *"Exclude free users, trials, pilots, and waitlists."* **Verdict:** the field is intentionally paying-only. A company with large **free/engaged** user scale (e.g. Outcomes4Me's 300k patients on a free-to-patient model) has **no structured field** — so prose-only is partly a *schema-coverage* outcome, not (only) a synthesis miss.

### `revenue_per_user` — owner: `search_commercial_scale` → fit-brief. Verdict: **adequate (asked, with derived fallback).**
Search (research_runner.py:265-267): pricing, *"the implied revenue-per-user (state the inputs)."* Schema (research_runner.py:866): `"revenue_per_user": "reported or derived revenue per paying user, or empty"`. Lands when pricing×customers is available (function `~$500`, oura `$500M+ / 5.5M rings`).

---

## 3. Gap-attribution — audited companies × field

Cross-read of structured `commercial_evidence` vs. free-text `commercial_scale_finding`.

| Company | `revenue_or_arr` (structured) | `paying_customer_count` (structured) | Free-text numbers present | Mode attribution |
|---|---|---|---|---|
| **ZOE** | empty | **"More than 100,000 paid customers" (present ✓)** | "120,000+ members", "ARR" (word only, no $ figure) | ~~revenue = C (Crowdcube postdates)~~ **CORRECTED → revenue = A (search-miss):** $80M ARR / 88k paying was disclosed ~Oct 2025, **~8 mo BEFORE** the run — the search didn't surface it. paying = no gap (reached structured). |
| **Levels** | empty | **"100,000+ members" (present ✓)** | "100,000 / 80,000+ members", "ARR/run-rate" (words only) | revenue = **C** (member counts present, no revenue $). paying = **no gap**. |
| **Outcomes4Me** | empty | **empty** | "$21M", "$38M", "342,326 members", "231,803 members", "300,000+ patients"; free-text states *"I did not find any public, company-reported ARR/revenue figure"* | revenue = **C** ($21M/$38M are funding, not revenue — correctly excluded). customer-scale = **A** (counts are **free** patients on a free-to-patient model; `paying_customer_count` is paying-only, correctly empty; **no field exists for non-paying scale**). *Refines the "suspected B": the synthesis did not drop a paying count — there isn't one; the free-user scale has no home.* |
| **Signos** | empty | empty | "ARR/run-rate" (words only); `q4 = unverified-promotional`; free-text: *"did not find credible public evidence of company-reported revenue"* | revenue + customers = **C** (no hard number anywhere; the "10x" signal postdates the run). |
| **Affect** | empty | empty | "ARR" (word only); free-text: *"no public company-reported revenue/ARR/GMV or credible third-party"* | revenue = **C**, likely **unfixable** (genuinely absent publicly). |

**Calibration / success cases (synthesis DID lift revenue when present):**
| Company | `revenue_or_arr` | `paying_customer_count` | growth |
|---|---|---|---|
| function health | `$100M run-rate (Sacra est.)` ✓ | `~200,000 subscribers (Sacra)` ✓ | `~450% YoY` ✓ |
| oura | `2024 revenue over $500M` ✓ | implied ✓ | `revenue doubled` ✓ |
| omada | `$260M FY2025` ✓ | `2,000+ customers; 20M+ covered lives` ✓ | `+53% YoY` ✓ |
| nourish | "Not publicly disclosed" (the $1.75B/$70M in free-text are **funding/valuation**, correctly NOT lifted to revenue) | "Not disclosed" | growing |

These prove the **gather→synthesize handoff works for revenue**: when a company-reported or credible-estimate figure exists, it reaches `revenue_or_arr`, and funding-$ is correctly kept out.

---

## 4. Mode-distribution summary (the headline)

### `revenue_or_arr` across the 55 (programmatic scan + manual calibration)
- **23/55 populated with a real figure.** **32/55 lack a figure** (9 explicit "not disclosed" + 23 blank — the "~42% blank" you flagged).
- Of the **32 missing**: **~25 Mode C** (no revenue-$ anywhere in the free-text — genuine non-disclosure/absence) and **≤7 Mode-B candidates** (a "$X revenue/ARR/run-rate" pattern appears in `commercial_scale_finding` but the structured field is empty): `angle health, visana health, transcarent, insidetracker, allara health, oova, thyme care`. **0 Mode A** (the prompt asks for revenue with estimate + implied fallbacks).
  - ⚠️ The 7 are **candidates, not confirmed** — the scan regex can false-positive on "*no* $X revenue found" phrasing or a funding-$ sitting next to the word "revenue." Each needs a one-row free-text read to confirm B vs C.
- **Headline (⚠️ SUPERSEDED — see CORRECTION at top of file):** ~~the missing-revenue problem is predominantly Mode C (~78% of the gaps)… Re-research helps only where a credible figure/estimate has since appeared.~~ The 2026-06-25 live probe shows "~78% Mode C" was figure-absent-**from-our-prose** (an upper bound on non-disclosure, inferred from absence — the symptom A and C share), **not** a measurement. 4/4 probed "Mode C" companies had revenue disclosed **before** the run → the gap is **substantially Mode A (search under-recovery), cheaply fixable by a search-PROMPT change** before any re-research. The ~25 vs ≤7 split below stands only as "figure-absent-from-our-free-text," **not** as a non-disclosure count.

### `paying_customer_count` across the 55
- **13/55 populated.** **6 are empty while the free-text carries a member/user/patient count:** `equip health, headway, jasper health, outcomes4me, mae health, vivante health`.
- These split **Mode A vs Mode B by whether the count is paying or free/covered-lives** (Outcomes4Me = Mode A, free patients). The paying-vs-free determination per company is the open item (§6).

### growth-RATE
- **Mode A on the structured side:** the search asks for YoY growth, but `growth_signal` accepts qualitative "growing"; the rate is not required and is usually dropped (all 55 = "growing").

---

## 5. Specific questions answered

1. **Does any prompt ask for a quantified revenue/ARR AND a quantified growth RATE?**
   - **Revenue/ARR: YES** — `search_commercial_scale` (research_runner.py:259-267), strong (company-reported + third-party estimate + implied-from-pricing).
   - **Growth RATE: partial** — the *search* asks for YoY growth/trend (research_runner.py:263, :282), but the *structured `growth_signal`* accepts qualitative "growing" with rate optional (research_runner.py:867). So a quantified rate is captured only opportunistically → **mode-A on the structured field**.
2. **Is `revenue_or_arr` owned by a prompt?** Yes — **gathered** by `search_commercial_scale`, **extracted** by the fit-brief synthesis. It is reliably populated **when a figure exists** (23/55). Empty ≈ Mode C.
3. **Why did Outcomes4Me's count land prose-only while ZOE's/Levels' reached the structured field?** ZOE/Levels report **paying** members (100k+ paid) → `paying_customer_count` populated. Outcomes4Me's 300k are **free** patients on a free-to-patient model → the paying-only field is correctly empty and there is **no field for non-paying scale**. **Mode B is therefore NOT systematic** — it's the paying-vs-free distinction plus a paying-only schema. (The 7 revenue + 6 paying candidates still need per-case verification.)
4. **Disambiguation instruction (founder/HQ/funding-stage to avoid name-conflation)?** **NONE.** Every search interpolates `{research_query}` as-is with no entity-disambiguation guard (`search_funding`/`payer`/`outcomes`/`commercial_scale`/`org_events`/`operating_characteristics`). Decoy entities ("Zoe Nutrition" reseller, "Levels" venture studio) can derail searches unchecked → **mode A** (coverage gap).
5. **Recency instruction on the commercial/revenue search + window?** **NONE on `search_commercial_scale`.** Only `search_org_events` is recency-bounded (research_runner.py:312: *"FOCUS ON THE LAST 12–18 MONTHS"*, :336 *"Recency is decisive"*). The commercial search has no window, so it captures whatever existed at run time; ZOE's Crowdcube and Signos's "10x" **postdate the run** → **mode C (timing)**, which a re-run *now* would catch — not a window defect.

**Prompt-interaction note:** the structured commercial fields are **synthesized**, not search-owned; the handoff works for revenue (success cases), so the residual gaps are upstream **data absence (C)** or **schema coverage (A: no non-paying-scale field, no required growth rate)** — with a thin **B** tail (≤7 revenue candidates) to verify.

---

## 6. Open questions / ambiguities (could not resolve read-only)

1. **The 7 revenue Mode-B candidates** (`angle, visana, transcarent, insidetracker, allara, oova, thyme care`) need a per-row free-text read to confirm a real revenue $ was present-but-unlifted (B) vs. the regex catching "no revenue found" / a funding-$ near the word "revenue" (C).
2. **The 6 paying-count candidates** (`equip, headway, jasper, outcomes4me, mae, vivante`): are the free-text counts **paying** (→ mode B, synthesis dropped them) or **free/covered-lives** (→ mode A, no field)? Determines A vs B for the customer-scale gap.
3. **Which Mode-C companies are re-research-fixable** (a figure has since appeared) vs. **genuinely unfixable** (Affect-type) cannot be determined read-only — it requires fresh live searches, which is the re-research cost itself.
4. **Whether a non-paying-scale field is wanted** (to give Outcomes4Me-type 300k-free scale a home) is a schema-design question for the redesign, not a research-coverage defect.

*No fixes proposed — diagnosis only.*
