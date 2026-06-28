# Findings — All-Fields Blink Probe (6-company sample, N=5, source-directed where owned)

**Date:** 2026-06-26 · **Branch:** research-search-recovery · **Type:** live, read-only probe
(`scripts/all_fields_blink_probe.py`; no master/checkpoint/Drive writes). Completed 6/6 before a
Colab disconnect; results below are the full report.
**Purpose:** scope which fields beyond revenue need retry-and-union; fold in B1 (source-directed
hit rate) + B2 (entity carry-and-flag) live-validation.

---

## 1. Per-field BLINK-RATE map — READ PER-COMPANY (the worst-case marks over-flag)

`1.0` = found on all 5 samples, `0.0` = never. **Read across the row**, not the worst cell.

| field | Midi | Solace | Pelago | ZOE | Function | Omada | how measured |
|---|---|---|---|---|---|---|---|
| revenue | 80% | 100% | 80% | 100% | 100% | 100% | **source-directed (own prompt)** |
| growth_signal | 60% | 40% | 100% | 100% | 80% | 100% | commercial passes ¹ |
| growth_rate_quantified | 60% | 20% | 100% | 100% | 80% | 100% | commercial passes ¹ |
| paying_customer_count | 0% | 0% | 20% | 20% | 80% | 20% | commercial passes ¹ |
| revenue_per_user | 0% | 40% | 0% | 20% | 80% | 0% | commercial passes ¹ |
| valuation | 100% | 100% | 0% | 60% | 100% | 40% | BLIND (funding search) |
| payer_institutional | 100% | 80% | 100% | 0% | 0% | 100% | BLIND |
| outcomes | 60% | 80% | 100% | 100% | 0% | 100% | BLIND |
| org_events | 0% | 0% | 80% | 60% | 80% | 60% | BLIND |
| operational_strain | 0% | 0% | 20% | 40% | 20% | 20% | BLIND |
| capability_fit | 100% | 100% | 100% | 100% | 100% | 100% | BLIND |

¹ **CAUTION — these four were scored on the COMMERCIAL passes (1 general + 4 *revenue*-source-directed),
NOT their own field-specific source-directed prompts.** The revenue retry prompt asks for *revenue*, so
growth / paying-count / rev-per-user are **under-measured** here (incidental mentions only). The probe's
own `measured-as` column labeled them "BLIND" for simplicity; this footnote is the precise read.

## 2. INTERPRETATION CAUTIONS (read these WITH the numbers above)

1. **The concentrated retry-candidate N suggestions are UNDER-MEASUREMENT ARTIFACTS.** e.g. the probe
   printed growth-rate "N≈11" — that comes from scoring growth on *revenue*-targeted passes. A
   field-specific source-directed prompt will raise per-pass hit and drop N. **Do not take these N
   literally; real N comes from the per-field re-measure.** (Function hitting 80% on paying-count /
   rev-per-user proves they ARE recoverable when a search actually targets them.)
2. **Diffuse-field "robust" verdicts from BLIND measurement are PROVISIONAL.** Blind can confirm
   "robust → no retry needed"; it CANNOT conclude "sparse → no retry possible" (the Pelago lesson —
   blind under-measures recoverability). Any diffuse 0%/low is "unresolved," not closed.

## 3. B1 — source-directed targeting + alias handling: VALIDATED (clear win)

Per-pass revenue hit rate, this run vs prior:
- **Pelago 4/5 (80%)** — was **0/5 blind** originally / ~2/4 in the matrix. The "Quit Genius → Pelago"
  alias + URL targeting did the work.
- **Midi 4/5 (80%)** — was ~40% single-pass blind.
- Solace / ZOE / Function / Omada: 5/5.
- **Evidence-QUALITY bonus:** Midi's `revenue_or_arr` now carries **company-reported CEO quotes**
  ($150M run-rate via interview + a JPMorgan feature quoting Strober), not just third-party estimates
  — so source-directed raised both recall AND evidence quality.

## 4. B2 — entity carry-and-flag: recovery fixed; flag-on-doubt path UNTESTED (do not smooth)

- ZOE's `revenue_or_arr` now carries **`$80.4M (GetLatka)`** — the prior silent-drop is **gone**; the
  ~$80M ground-truth figure is recovered.
- `entity_review_needed='none'` is **CORRECT** here: the figure surfaced from **GetLatka's clean ZOE
  page**, not the **Growjo "Join ZOE"** page that caused the prior doubt (B1's URL targeting likely
  steered to the cleaner source). No ambiguity arose → no flag.
- **HONEST STATUS:** the carry-and-flag-**on-DOUBT** path was therefore **NOT exercised live** — the
  plumbing is verified additive and the field is queryable, but the safety-net behavior remains
  **UNTESTED until an ambiguous source recurs.** Do not record this as "B2 works"; record as
  recovery-fixed + flag-path-untested.
- (Aside: the ZOE search surfaced many "Zoe" **decoy entities** — ZOE is a name-conflation minefield,
  reinforcing why the entity-handling safety net matters even though it didn't fire this run.)

## 5. VERIFIED zeros correction (live-web checked — Rule 8; don't accept an absence read unverified)

- **ZOE payer 0% → GENUINELY structural.** ZOE is D2C membership, no payer channel. ✅
- **Function outcomes 0% → GENUINELY structural.** Biomarker lab-testing, not a trial-running
  intervention; no published clinical studies to surface. ✅
- **Function payer 0% → NOT a clean structural absence. ⚠️ FIELD-SCOPE GAP (route to PATH-gate work).**
  The payer/insurance zero is technically right (Function is explicitly "100% insurance-free"), BUT
  Function HAS a real institutional channel — **"Function for Work": employers fully/partially fund
  memberships, with population-health reporting** — i.e. **employer-direct B2B2C, not payer-reimbursed.**
  The field is named `payer_institutional`, but the PATH gate actually needs "**is there a REAL
  institutional / B2B2C channel**," of which payer-reimbursement is only ONE kind. A payer-only field
  scores Function as "no institutional channel" when it has one → could **mis-gate it at PATH Test B**.
  This is a **field-scope / definition gap in the SCORING MODEL, not a research-layer/recovery problem**
  (retry will not fix it). **PARKED for the PATH-gate build; not actioned in the probe/retry layer.**

## 6. Growth coverage gap is MILDER than assumed

`growth_signal` vs `growth_rate_quantified` **track together for 5 of 6** (60/60, 100/100, 80/80,
100/100, 100/100); only **Solace** shows the gap (40% vs 20%). So when growth is found, a quantified
rate usually comes with it. **Growth's real problem is VARIANCE (→ retry), not the
qualitative-"growing" coverage gap.** The required-rate wording fix is **low-urgency** — fold it into
growth-rate's source-directed prompt rather than treating it as a separate effort.

## 7. Scoping verdict

- **revenue** — retry ENABLED (N=5 kept; see §8).
- **Concentrated retry candidates** — `growth_rate` (leads; ~60% of PMF), `paying_customer_count`,
  `valuation`, `revenue_per_user` — **pending field-specific source-directed prompts + a targeted
  re-measure** to confirm recoverability and set the REAL per-field N (not the §2 artifacts). Designed
  in groups of 2: **Group 1 = growth-rate + paying-count; Group 2 = valuation + rev-per-user.**
- **capability_fit** — single-pass (robust 100% everywhere).
- **Diffuse (payer / outcomes / org-events / strain)** — single-pass, but the "robust" reads are
  **provisional per §2 caution 2**; the verified zeros (§5) resolve ZOE-payer and Function-outcomes as
  genuine, Function-payer as a PATH-gate field-scope issue. `operational_strain` stays low /
  under-measured / lowest-stakes (capped modifier) — known gap, deprioritized.

## 8. Revenue N — KEEP N=5 (decision)

Do NOT drop revenue to N=3 yet: (1) the one-time **regen wants maximum corroboration** (more
figure-bearing passes → richer union → better evidence_confidence), and N=5 is a one-time cost there;
(2) keeping N=5 through the upcoming group-of-2 re-measures gives a **larger sample to set the permanent
N empirically** rather than guessing from this probe. N stays **per-field config**, and possibly
**per-context** later (e.g. 5 for the run-once regen, lower for cheap ongoing group-of-5 runs).
Revisit AFTER the re-measures.

## 9. Method note (carry forward)

The probe's mechanical worst-case verdicts OVER-FLAG diffuse fields; the per-company map + a live-web
check of the zeros (§5) is what produced the correct read. Same discipline as every prior step: read
the data, verify the absence, don't trust the mark.

## 10. Growth-rate re-measure (post refine-to-derive) — N=5 sized to the recoverable case

Built against FRAMEWORK_VERSION v1.1. The refine-to-derive trio (search compute-from-endpoints +
`growth_signal` carry + presence (a)/(b) split) shipped, then Midi / Solace / ZOE were re-measured
(`scripts/growth_rate_remeasure.py`, N=5, on the explicit credit-spend go):

| company | pre-derive | post-derive | read |
|---------|-----------|-------------|------|
| Midi   | 20% | **60%** (3/5)  | derive WORKING — passes computed ~1.93x / ~2.5x / ~5x from dated $ endpoints, inputs shown; the two misses were the general pass + a correctly-rejected $0-base, not failures |
| ZOE    | 40% | **100%** (5/5) | reliably DERIVED +227.8% from £1.8m (2021) → £5.9m (2022) Companies House points |
| Solace | 40% | 20% (1/5)      | **genuine-absent for growth** — one dated revenue point ($10M, 2025) exists; no second point to derive from (4/5 correctly "not computable"); the qualitative floor catches it |

**[1]/[2] fired live** — rates were COMPUTED from dated endpoints with the inputs shown, and a $0-base
was correctly rejected as not-a-usable-%. Derive lifted the genuinely-recoverable cases hard (Midi
20→60, ZOE 40→100).

**N decision = 5** (always-run-N, never stop-on-hit). Sized to the worst **RECOVERABLE** case, Midi 60%
→ ~99% at N=5; matches revenue / paying-count. **Solace was EXCLUDED from sizing** — it is genuine-absent
(a structurally consistent one-point absence across passes), NOT a recoverable blinker, so more passes
cannot manufacture a second data point that doesn't exist (the inverse of Rule 8). This is distinct from
**Pelago**, whose revenue absence was RECOVERABLE (B1 raised it 0/5 → 4/5). Genuine-absent cases do not
drive N. NOT the reflexive worst-case-20% → N≈11.

**Employee-growth false positive (motivates SOT B6.1 routing).** Solace's lone "hit" (pass 4) was
"~304% EMPLOYEE growth" (Growjo), and Midi surfaced "0→435 employees" as a candidate — headcount growth
counted as a growth RATE, because the presence-check (a)-clause had no kind-of-growth filter. The fix is
ROUTING, not discard (these are real secondary signals): a precision FENCE keeps headcount / non-paying
user / download / MAU / partner-count / funding growth OUT of growth_rate, and those signals are
captured + carried elsewhere — the reserved **SOT B6.1** slot, locked in the routing task.

**Capture-path WATCH-ITEM (regen live output).** `user_scale_signal` is populated by the synthesis from
the commercial union (`search_commercial_scale` already surfaces scale figures). We did NOT add a directed
non-paid-scale search — no evidence it's needed; don't pre-build. WATCH the regen's live output: if
`user_scale_signal` comes back thin WHERE scale is known to exist, that is the trigger to add a directed
`search_commercial_scale` capture for non-paid scale — its own decision, then.

## 11. Funding-stage / IPO variance (2c) — gate input mostly robust; ONE real C/D-boundary flip

Built against FRAMEWORK_VERSION v1.2. Ran 2c live via the NOTEBOOK path (= the package `search_funding` the
regen uses, not a standalone harness), 5 boundary companies × N=5, billing-checked. The RAW per-pass marks
show `funding_stage` "blinking" on 4/5 — but the GATE-RELEVANT read (does the stage land in the same AGENCY
bucket: A/B/C = PASS vs D+/public = FAIL) is the real story:

| company | stage reads (×5) | ipo_status | AGENCY bucket across 5 | gate-flip? |
|---|---|---|---|---|
| Hinge Health | d-plus×2, public×3 | public ×5 | FAIL all 5 (d-plus AND public both FAIL; ipo=public confirms) | NO — blink within FAIL |
| Omada Health | d-plus×1, public×3, unknown×1 | public ×5 | FAIL all 5 (stable ipo=public floors it even when stage=unknown) | NO — ipo is the robust floor |
| Sword Health | **series-c×1, d-plus×4** | private ×5 | **4 FAIL / 1 PASS** | **YES — 1/5 reads C (pass) vs D+ (fail)** |
| Transcarent | series-d×1, d-plus×4 | private ×5 | FAIL all 5 (d and d-plus both FAIL) | NO — blink within FAIL |
| Allara (control) | series-b ×5 | private ×5 | PASS all 5 | NO — perfectly stable |

**Read the gate, not the label** (same discipline as the growth re-measure). The mechanical "BLINK(2/3)"
marks over-state the risk: 3 of the 4 stage-blinks stay WITHIN one gate bucket (Hinge/Transcarent blink
between two FAIL labels; Omada is floored by a rock-stable ipo=public). **`ipo_status` is rock-stable**
(public/private 5/5 on EVERY company) — so for IPO'd/public companies it is the robust gate signal and the
stage-label noise is cosmetic. Valuation blinks as expected (Hinge $6.2B↔none; Omada $1B↔none↔"just above
$1B") — confirming the search IS noisy — while the gate inputs are steadier than valuation (the reassuring
pattern).

**The one real finding — the C-vs-D boundary flips.** Sword reads `series-c` 1/5 and `series-d-plus` 4/5,
and C **passes** AGENCY while D+ **fails** — so at the C/D boundary funding_stage can blink across the
pass/fail line (~20% here), wrongly PASSING a too-late company into scoring. (Transcarent's d↔d-plus did
NOT flip — both FAIL.) Cause: the search sometimes surfaces an OLDER round (C) instead of the latest (D+).
SOT B4 already defines funding_stage as the MOST RECENT priced round, so the fix is to make the search
reliably surface + pick the latest round.

**Implication for funding's N (feeds the N-table):** funding is NOT a clean single-pass. `ipo_status` →
single-pass robust. `funding_stage` → needs a C/D-boundary mitigation: a LIGHT recovery (small N + take-the-
most-recent-round per SOT B4 — the union surfaces the latest round, deterministically resolving C-vs-D) OR
single-pass + a near-C/D boundary flag to human review. Recommend the recovery (directly implements B4 +
robust); ratified in the N-table.

(2a capability right-data + 2b reset recall were READ-confirmed clean against the regen doc earlier this
thread; 2c is the only check that needed a live measure, and it surfaced the C/D flip above.)

## 12. Funding dating-fix re-check — RESIDUAL is a MEASUREMENT CONFOUND, not an N problem (read the control)

Re-ran the single-pass re-check after the dating-wording build (`4ede0a6`), 5 cos × N=5, package path.
Mechanical verdict printed: "RESIDUAL BLINK → funding = N=2." **That verdict is WRONG — read the control.**

| company | expected | got (×5) | vs 2c |
|---|---|---|---|
| Sword | series-d-plus | d-plus×2, b×1, d×1, c×1 | more spread |
| Hinge | public | public×1, a×1, unknown×1, b×2 | far WORSE |
| Omada | public | public×4, a×1 | ~same |
| Transcarent | series-d-plus | d-plus×3, a×1, public×1 | worse |
| **Allara (control)** | series-b | **a×1, b×4** | **was 5/5 PERFECT in 2c** |

**The tell — the Allara CONTROL got WORSE** (5/5 series-b in 2c → blinks series-a here). A dating fix
CANNOT make a clean control less reliable, so the change is in the MEASUREMENT, not the company. What
changed: the dating-wording makes `search_funding` surface the FULL dated round SEQUENCE (Seed/A/B/C/D…),
and the re-check's GENERIC LLM extraction now picks `funding_stage` by reading that multi-round list —
blinking toward EARLIER rounds (series-a/b now appear on every company, even public Hinge). Pre-fix the
search stated ONE stage; post-fix it lists every round, so an LLM picker has more to blink across. **The
blink is in the SELECTION, not the evidence.**

**Real diagnosis (Rule 7).** The dating-wording correctly makes the LLM GATHER the dated rounds (good
evidence). But `funding_stage` SELECTION (public-outranks / latest-dated priced round) is still an LLM
judgment (the prompt asks the LLM to compute it; the re-check re-does it generically) — and LLM selection
over a multi-round sequence is non-deterministic. **The fix is a DETERMINISTIC mapper**: LLM emits the
dated rounds as STRUCTURED evidence; CODE picks `funding_stage`. Same Rule-7 pattern as who_uses/who_pays
(LLM extracts facts; deterministic mapper emits the label).

**N=2 is NOT the fix** — a union of multi-round findings still leaves an LLM picking the stage; it still
blinks. Determinism fixes the source (as derive fixed growth; as the classifier mapper fixes
business_model). **Funding-N is therefore NOT locked at N=2 — HELD pending the deterministic-mapper design.**
Likely outcome: funding stays SINGLE-PASS (the mapper is code, no extra searches) → cost stays ~1,100,
not 1,155.

**One verify (Rule 8).** The re-check printed only the stage, not raw findings, so it can't tell whether
the search ALSO sometimes MISSES the latest round (a recall gap a small N union would address) vs always
gathers it (mapper alone suffices). The Allara control (simple rounds, blinking only toward an earlier
LISTED round) points to SELECTION, not recall — but confirm with a raw-finding look before finalizing N.

## 13. Funding recall check (post-mapper) — SELECTION fixed; RECALL needs a recovery (N=2 too low)

Ran the raw-rounds recall check after the deterministic mapper (`c3779cc`), Sword (complex) + Allara
(control), N=4 each, reading the RAW gathered rounds (not just the mapped stage):

| company | per-pass gathered rounds | latest-round recall |
|---|---|---|
| Sword | p1 [seed,b,c,d] ✓ · p2 [seed,b,c,d] ✓ · p3 [seed,a,b] ✗ · p4 [seed,a,a,b] ✗ | **2/4 — a single pass MISSED the D round half the time** |
| Allara (control) | [seed,a,b] every pass | **4/4 clean** |

**The mapper (SELECTION) is FIXED** — it deterministically returned `series-d-plus` whenever D was
present and `series-b` whenever the rounds stopped at B; the control was rock-stable. The selection blink
is gone. **The remaining gap is RECALL:** a single generic `search_funding` pass does NOT reliably GATHER
the latest round for a COMPLEX company (Sword 2/4 missed D); simple companies (Allara) are clean. This is
the same web-search execution variance the other fields hit.

**N=2 (the pre-commit) is too low.** At the observed ~50% per-pass recall for Sword-class, an always-run
union recovers the latest round with P = 1 − 0.5^N: N=2 → 75%, N=3 → 87%, N=5 → 97%. A 75% recall on a
GATE input — a missed latest round reads a too-late D+ company as a passing series-b — is not enough.

**Decision (HELD — not locked):** funding joins the recovery fields (it is NOT single-pass and NOT N=2).
Either (a) a SOURCE-DIRECTED funding recovery (a retry that hunts the full/latest round history —
Crunchbase / PitchBook — like the B1 source-direction that fixed revenue/growth recall), sized by a quick
re-measure (source-direction should keep N modest, ~3); or (b) a plain N=5 union of the base gather (no
new prompt, ~97%, conservative). (The high-recall-filter + human P0/P1 review is a partial backstop —
a wrongly-passed Sword gets caught in deep research — but the gate should still eliminate it up front.)

**Cost impact:** funding is no longer ~1,100. (a) source-directed N=3 → +110 → **~1,210**; (b) plain N=5
→ +220 → **~1,320**. Locks once funding's recovery N is decided.

## 14. Funding source-directed re-measure — recall is EXCELLENT; the misses are a MAPPER gap, not N

Source-directed re-measure (`a434cec`), 4 cos × N=5, per-pass = does the mapper hit the expected bucket:

| company | per-pass | read |
|---|---|---|
| Allara (control) | 5/5 (100%) | clean |
| Hinge | 5/5 (100%) | public (IPO outranks), clean |
| Transcarent | 5/5 (100%) | clean |
| Sword | 3/5 (60%) | **both "misses" GATHERED Series D — MAPPER artifacts, not recall misses** |

**Source-direction worked (the B1 win)** — per-pass recall lifted from the generic 50% to 100% on three
companies, and to a TRUE ~100% on Sword: reading the RAW rounds, the latest real round (Series D / F) was
GATHERED in ALL 5 Sword passes. The two scored "misses" are the mapper letting a NON-CANONICAL type win
over the real Series D:
- pass 4: rounds include "Series D" + a vague "Priced equity round" + "Financing / secondary sale" → the
  mapper returned "priced-equity-round" (it normalizes an unrecognized type as-is → garbage).
- pass 5: rounds include "Series D" + two "unknown"-typed rounds → the mapper returned "unknown".

So the source-directed retry gathers RICHER (messier) lists — secondary sales / vague / "unknown" types —
and the mapper lets a non-canonical type win over the real Series D. **This is a MAPPER ROBUSTNESS gap,
not a recall problem. N=4 (the mechanical worst-case) would brute-force past it — the anti-pattern we keep
rejecting.**

**Fix (small, code-only, validated FREE on these exact round-lists):** the mapper selects only rounds whose
type normalizes to a CANONICAL stage (pre-seed / seed / series-a..c / series-d-plus); non-canonical types
(Priced equity round, unknown, secondary sale, financing) are EXCLUDED from the stage selection, and
"series-X extension" normalizes to series-X. Then the latest CANONICAL priced round (Series D) wins →
Sword's two misses resolve. (Selection-half refinement to the c3779cc mapper.)

**N implication:** recall is ~100% with source-direction, so funding N is LOW — **N=2** (1 general + 1
source-directed, a buffer), NOT N=4. **Cost ~1,155 (N=2)**, not ~1,320. Locks after the mapper-robustness
fix (validated offline on the re-measure's raw rounds — no credit re-check needed).
