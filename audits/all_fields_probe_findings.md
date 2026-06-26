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
