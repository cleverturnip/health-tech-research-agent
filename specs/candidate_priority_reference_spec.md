# Candidate Priority Engine — Reconciled Reference Spec

This is the consolidated, internally-consistent specification for `candidate_priority.py`,
reconciled from four conflicting notebook generations. It resolves the scale-path
vocabulary mismatch, strips hardcoded company values, and integrates the new
LLM-produced capability-fit score. This is the document to hand Claude Code to build from.

Source of each piece:
- Gate logic: V4.1 (notebook cell 155) — newest, strictest gate.
- Public/near-IPO cap: V4.2 (notebook cell 154) — overlay applied after gating.
- Producers (agency-entry, scale-path, archetype, signal-conversion): cell 159, reconciled.
- Capability-fit: NEW — LLM-produced, replaces the cell-159 role_fit bridge.

---

## 0. Pipeline order (resolves R-ORDER)

For each company, in this exact order:

1. Convert text signals → 0–3 numeric (`*_signal_inferred`).
2. Compute `scale_path_quality` (reconciled vocabulary — see §2).
3. Compute `operator_agency_entry_score` (§3).
4. Obtain `katelynd_capability_fit_score` (NEW — LLM-produced, §4).
5. Compute `target_archetype` (§5).
6. Run the V4.1 gate → P0/P1/P2/P3 (§6).
7. Apply the V4.2 public/near-IPO cap as an overlay (§7).
8. Emit outputs + reason text (§8).

---

## 1. Signal conversion (text → 0–3)

Deterministic. From the live LLM text signals.

```
none/blank → 0
weak       → 1
moderate   → 2
strong     → 3
```

Applied to: `commercial_scale_signal`, `institutional_distribution_signal`,
`outcomes_signal` → produces `commercial_scale_signal_inferred`,
`institutional_distribution_signal_inferred`, `outcomes_signal_inferred`.

---

## 2. Scale-path quality (RECONCILED — the critical fix)

**The bug being fixed:** cell 159 emitted `strong_single_engine`, but the V4.1 gate
only recognizes `strong_institutional_engine` / `strong_commercial_engine`. Single-engine
companies would silently fail the gate. The reconciled producer below SPLITS the single
engine by which signal is strong, so the gate's vocabulary matches.

Inputs: `commercial` (0–3), `institutional` (0–3), `outcomes` (0–3), `pmf`, `evidence`,
and `plausible_near_term_scale_path` (bool-ish text).

```
if commercial == 3 and institutional == 3:
    return "strong_dual_engine"

# RECONCILED: split the old strong_single_engine by which engine is strong
if institutional == 3 and commercial < 3:
    if outcomes >= 2 or pmf >= 78:
        return "strong_institutional_engine"
    return "credible_path"          # was credible_single_engine — see note
if commercial == 3 and institutional < 3:
    if outcomes >= 2 or pmf >= 78:
        return "strong_commercial_engine"
    return "credible_path"          # was credible_single_engine — see note

if plausible and pmf >= 68 and evidence >= 50:
    return "credible_path"
if outcomes == 3 and (commercial >= 2 or institutional >= 2):
    return "emerging_path"          # was outcomes_plus_path — see note
if commercial >= 2 or institutional >= 2:
    return "emerging_path"
return "weak_or_unclear"
```

**Vocabulary mapping (old → reconciled), for review:**
- `strong_single_engine` → split into `strong_institutional_engine` OR `strong_commercial_engine` (by which signal == 3).
- `credible_single_engine` → mapped to `credible_path` (the gate accepts `credible_path`; it does NOT recognize `credible_single_engine`, so the old term would have failed).
- `outcomes_plus_path` → mapped to `emerging_path` (gate doesn't recognize `outcomes_plus_path`).
- `credible_dual_path` → the gate accepts this, but the producer never emits it. Left unused unless we decide a dual-but-not-both-strong case needs it. FLAG for review.

**The gate's accepted lists (from V4.1, unchanged):**
```
has_strong_scale_path = {strong_dual_engine, strong_institutional_engine,
                         strong_commercial_engine, credible_dual_path, credible_path}
has_scale_path        = the above + {emerging_path}
```

RESOLVED review decisions in §2:
- (2a) `credible_single_engine` → `credible_path`: CONFIRMED. Keeps single-engine credible
  companies eligible for P1 via `has_strong_scale_path`.
- (2b) `outcomes_plus_path` → `emerging_path`: CONFIRMED. Outcomes-led companies (strong
  outcomes, no strong commercial/institutional channel) cap at P1, never P0. P0 requires a
  real scale channel (institutional ≥ 3). This is intentional per write-up §4: "outcomes do
  not substitute for a scalable channel." Strong studies prove the product works; they don't
  prove the company can scale distribution — which is what active-pursuit (P0) requires.
- (2c) `credible_dual_path`: accepted by the gate but never emitted by the producer. Leave
  UNUSED for this build (no case currently routes to it). Revisit only if a dual-but-not-
  both-strong case proves it's needed.

---

## 3. Operator agency-entry score (PORT from cell 159, de-hardcoded)

Deterministic formula. Starts from `operator_timing_score`, adjusts by maturity / stage /
agency-level / reset. Ported as-is from cell 159 EXCEPT: the reset detection must use the
productionized reset signal (§9 of the original spec), not an inline text scan, and NO
hardcoded company names.

Behavior (preserved from cell 159):
- Base = `operator_timing_score`.
- Early-growth + role_fit≥78 + pmf≥70 + evidence≥55 → at least 82; if ≥82/74/60 → at least 86.
- stage ideal → ≥85; good (with role_fit≥78, pmf≥70) → ≥80; borderline → clamped 62–76; too late → ≤62.
- scale-up/late-stage/public/near-IPO: with reset → ≥78; public → ≤58; else → ≤70.
- agency_level high → ≥80; medium → ≤ min(timing+5, 78); low → ≤62.
- Clamp 0–100, round to int.

⚠ REVIEW: this formula references `role_fit_score` and `operator_timing_score` (both live).
It is internally consistent. No changes needed beyond de-hardcoding reset.

---

## 4. Katelynd capability-fit score (NEW — LLM-produced, REPLACES the bridge)

**This replaces cell 159's `return role_fit_score` stopgap entirely.** Capability-fit is
now its own LLM-produced score, added to the fit-brief prompt. Section 3D of the original
write-up is RETIRED; mandate/breadth lives only in agency-entry (no double-count — and see
"Engine integration (Slice 4)" below for how the A2/reset overlap is *enforced* at the gate,
not just asserted).

### Scoring model
- Score = **average of three attributes**, each 0–100, **equal thirds**.
- Each attribute assigned a band with a one-line justification; code averages the three.
- Bands: **Strong 85–100** (clearly, centrally true) / **Moderate 60–84** (present with
  caveats) / **Weak 30–59** (mostly absent/superficial) / **Absent 0–29** (not characteristic).

### Attribute A1 — Product-engagement structure → data-driven by necessity
**Reframed by `specs/slice3_7_search_layer_redesign_spec.md` (source of truth).** A1 is NOT a
"do they have a data culture" inquiry (unverifiable; companies self-describe). It is a
PRODUCT-STRUCTURE question: a product with a daily / high-frequency engagement loop whose
REVENUE DEPENDS on sustained engagement is data-driven BY NECESSITY.
- Score HIGH when habit-dependent AND revenue hangs on retention; LOW when engagement is
  periodic/optional or revenue doesn't depend on it.
- Asymmetry preserved: doing the data loop badly is the value-add, not a disqualifier.
- Evidence (shared with A3): `search_operating_characteristics`, product-engagement lens.

### Attribute A2 — Operational STRAIN (not "complexity exists")
**Reframed by `specs/slice3_7_search_layer_redesign_spec.md` (source of truth).** A2 is NOT
"cross-domain complexity exists" — every competitive company is complex, so it doesn't
discriminate. It is EVIDENCE OF OPERATIONAL STRAIN: scaling outrunning process, things breaking
under growth — the signal the company needs this operator's skillset.
- INTENDED: a healthy, smoothly-scaling company scores LOW on A2 — the strain IS the opportunity,
  so its absence correctly lowers fit (a "better-run" company can legitimately score lower).
- Evidence: `search_operating_characteristics`, operational-strain lens.

### Attribute A3 — Digital consumer habitual-engagement product
A **digital consumer product** where **habit / retention is load-bearing** for the product's
success.
- **False positive (score low):** a consumer *surface* without habit-dependence (one-time
  transaction), or **B2B2C where the real customer is the employer/payer** and habit is
  secondary.
- Shares the product-engagement evidence with reframed A1 (`search_operating_characteristics`).

### Output
`katelynd_capability_fit_score` (0–100, the average) + per-attribute bands and
justifications for the audit trail.

✅ DONE (Slice 4 Commit 1): the fit-brief PROMPT change (the A1/A2/A3 rubric + `capability_evidence`
schema) is implemented.

### Engine integration (Slice 4 — implemented)
- `capability_fit_score` reads the stored `katelynd_capability_fit_score`; the `role_fit` bridge
  is retired. `CANDIDATE_FRAMEWORK_VERSION` = `"V4.2"` (no longer interim).
- **Missing-attribute policy:** any attribute unscorable → the average is SUPPRESSED (`None`) and
  `capability_needs_review` is set; the orchestrator routes the row to **P3** (never P0/P1/P2) for
  human review. `0` is a real Absent value (averages normally); only `null` suppresses.
- **Gate-time A1/A3 recompute (no-double-count ENFORCEMENT).** §4's "no double-count" above was
  asserted, not enforced. The Slice 3.7 A2 reframe makes A2 = operational strain — the SAME
  "scaled-too-fast → restructured" event the reset signal reads (→ agency floor + maturity
  cap-lift). One event could otherwise clear two gates: lift the cap (reset) AND raise capability
  over the threshold (A2). **Enforcement:** in `v41_gate`, when reset is lifting a scale-up (the
  `has_reset` scale-up P1 paths — `p1_scaleup_reset` and `p1_standard`), the capability THRESHOLD
  uses the mean of A1 and A3 only — A2 excluded, since its strain was already consumed by the
  reset lift. The stored `katelynd_capability_fit_score` stays the honest three-attribute average;
  the A1/A3 mean is a gate-local quantity used only for that threshold. Non-reset rows are scored
  on all three. (See `tests/test_candidate_priority.py` gate tests.)

---

## 5. Target archetype (PORT from cell 159, verify against V4.1)

Ported from cell 159's `compute_target_archetype`. Note it references the OLD scale-path
vocabulary in its eligibility list (`strong_single_engine`, `credible_single_engine`,
`outcomes_plus_path`) — these must be updated to the reconciled vocabulary from §2.

Returns one of: `Ideal early-growth / high-agency target`, `Strong but mature benchmark`,
`Role-scope-dependent target`, `Interesting but under-proven`, `Watch list / weak fit`.

⚠ REVIEW (5a): cell 159's archetype eligibility list uses old scale-path names. After §2's
reconciliation, update this list to: `strong_dual_engine, strong_institutional_engine,
strong_commercial_engine, credible_path, emerging_path` (decide which belong).

---

## 6. The V4.1 gate (PORT as-is from cell 155)

The decision tree, preserved exactly. Thresholds confirmed against the spec.

**P0 — Active pursuit target.** ALL of:
early_growth; stage ∈ {ideal, good}; thesis≥78; pmf≥74; evidence≥60; capability≥78;
agency≥82; `has_strong_scale_path`; institutional≥3; outcomes≥2; agency_level≠low;
not under_proven; not weak_fit.

**P1 — High-priority diligence.** (not P0) AND not mature_benchmark, not scaleup_borderline,
not weak_noninstitutional_scaleup, not under_proven, not weak_fit; stage ∈ {ideal, good};
thesis≥75; pmf≥68; evidence≥55; capability≥74; agency≥78; `has_scale_path`; agency_level≠low.

**P1 special cases** (also yield P1):
- Early-growth with `emerging_path`: thesis≥78, pmf≥70, evidence≥55, capability≥78,
  agency≥82, institutional≥2, outcomes≥2.
- Scale-up + good/borderline + reset: thesis≥75, pmf≥68, evidence≥55, capability≥74,
  agency≥78, `has_scale_path`, agency_level≠low.

**Mature cap (in-gate):** if (mature_benchmark OR scaleup_borderline) AND not
scaleup_good_with_reset → P0=P1=False.

**P2 — Worth deeper diligence.** (if not under_proven/weak_fit): not P0, not P1, pmf≥60,
evidence≥45, capability≥65, `has_scale_path`.

**P3 — Watch list.** Everything else (incl. under_proven / weak_fit).

Definitions:
- early_growth = maturity ∈ {early-growth, early growth, series a, series b, series a/b}
- mature_benchmark = archetype=="Strong but mature benchmark" OR maturity ∈ {late-stage, public, near-ipo}
- scaleup_borderline = maturity=="scale-up" AND stage=="borderline"
- scaleup_good_with_reset = maturity=="scale-up" AND stage ∈ {good, borderline} AND reset_signal
- weak_noninstitutional_scaleup = not early_growth AND not reset_signal AND scale_path=="emerging_path" AND institutional<2 AND commercial<3

---

## 7. Public / near-IPO cap (PORT from V4.2 cell 154, as overlay)

Applied AFTER §6. Forces public/near-IPO companies to P3 unless an exception holds.

```
IF maturity ∈ {public, near-ipo}
   AND NOT reset_signal
THEN candidate_priority = P3
```

RESOLVED (7a): Dropped `specific_high_agency_role` and `manual_override`. The reset signal
is the ONLY exception that lifts the cap. This keeps the engine fully deterministic with no
hand-set fields. If a manual escape hatch is needed later for a specific public company, add
a `manual_override` boolean as a follow-up — start stricter, loosen later if needed.

RESOLVED (7b): Rely on the LLM `company_maturity_read` emitting "public" or "near-ipo"
directly. No separate near-IPO boundary computation; the maturity read is the source of truth.

---

## 8. Outputs + reason text

Must satisfy the existing display-layer contract (repo cells 6837–7084):
- `candidate_priority_level` (P0–P3 label), `candidate_priority_reason`,
  `candidate_priority_framework_version` (= "V4.2"), `candidate_priority_source`,
  `candidate_priority_updated_at`, `candidate_priority_code`, `candidate_priority_rank`.
- Producer outputs: `target_archetype`, `scale_path_quality`, `operator_agency_entry_score`,
  `katelynd_capability_fit_score`, the three `*_signal_inferred`,
  `reset_or_restructure_signal` / `_basis`.

RESOLVED (8a): Keep V4.1's fixed per-tier reason strings for this build (simplest, can't
affect correctness). Enrich later with reason text that cites the specific gating factor per
company (e.g. "capped at P2: evidence 59, one below P0 threshold of 60"). Deferred — pure
explanation, not the priority decision.

---

## 9. Reset/restructure signal (PRODUCTIONIZE)

Remove the hardcoded `manual_reset_companies = {"zoe"}`. Replace with a real researched
field: `reset_or_restructure_signal` (yes/no/unclear) + `reset_or_restructure_basis`
(evidence + source). The text-scan fallback may remain as a secondary heuristic, but no
company names hardwired.

RESOLVED (9a): Keep the text-scan heuristic for THIS build (scan research notes / takeaways
for reset terms: restructure, layoff, turnaround, reset, off-track, leadership churn, pivot,
etc.). No new LLM field this build — capability-fit (§4) is the only prompt change. Promote
reset to a real LLM-researched field (`reset_or_restructure_signal` yes/no/unclear +
`_basis`) in a LATER pass. NO hardcoded company names — the `{"zoe"}` override is removed.

---

## 10. Integration with final priority (from earlier decisions)

- Candidate priority becomes AUTHORITATIVE for `final_priority_level` unless a genuine human
  override exists.
- `priority_source` = "Human Reviewed" ONLY when a human genuinely changed the priority —
  never on mere approval, never on a seeded-value mismatch (fixes the false-label bug).
- Fix the sticky auto-seed of `reviewed_priority_level`.

⚠ This is a SEPARATE piece from building the engine — sequence it after the engine works
and produces correct candidate priorities. (The master remediation of already-contaminated
rows is separate again.)

---

## Build sequencing (recommended commits, each red→green)

1. Signal conversion + reconciled scale-path (§1, §2) — the vocabulary fix, with tests
   asserting institutional/commercial split feeds the gate's accepted lists.
2. Agency-entry + archetype producers (§3, §5) — de-hardcoded, vocab-updated.
3. Capability-fit LLM scoring + fit-brief prompt change (§4) — the one prompt change, isolated.
4. The gate + cap consuming all producers (§6, §7) — testable only after 1–3 exist.
5. Wire candidate→final authority + fix false "Human Reviewed" + auto-seed (§10).
6. (Separate) master remediation of already-contaminated rows.

## Open review items — ALL RESOLVED
2a ✓ (credible_single_engine→credible_path) · 2b ✓ (outcomes caps at P1) · 2c ✓ (credible_dual_path
unused) · 5a (archetype vocab — mechanical, update to reconciled names during build) · 7a ✓
(reset-only exception) · 7b ✓ (maturity_read is source of truth) · 8a ✓ (keep V4.1 reason
strings) · 9a ✓ (text-scan reset, no hardcodes)

Note 5a is the one remaining mechanical item: cell 159's archetype eligibility list uses the
OLD scale-path names and must be updated to the reconciled vocabulary (§2) during the build —
not a decision, just a find-and-replace to keep consistent. Flagged so it isn't missed.
