# Cell 159 — Verbatim Producer Source (authoritative for formulas)

This is the EXACT source of the producer functions from the notebook (cell 159).
Use these as the authoritative implementation of the formulas — do NOT reconstruct
the agency-entry stacking logic from the spec's prose description; the precedence of
the max()/min() bands is defined here.

IMPORTANT reconciliation notes when porting these into the package:
1. `compute_scale_path_quality` below emits the OLD vocabulary (`strong_single_engine`,
   `credible_single_engine`, `outcomes_plus_path`). These MUST be reconciled per spec §2:
   - `strong_single_engine` → split into `strong_institutional_engine` / `strong_commercial_engine`
     based on which of commercial/institutional == 3.
   - `credible_single_engine` → `credible_path`.
   - `outcomes_plus_path` → `emerging_path`.
2. `compute_target_archetype`'s eligibility list uses the OLD vocabulary too — update it to
   the reconciled names (spec item 5a).
3. `compute_operator_agency_entry_score` has an INLINE reset text-scan. Per spec §9, the
   reset detection should call the shared `reset_signal(row)` function (no behavior change to
   the markers, just no duplication and no hardcoded company names — note cell 159's version
   already has NO hardcoded names; the `{"zoe"}` hardcode was only in the V4.1 gate cell 155,
   which we are NOT porting that part of).
4. `compute_katelynd_capability_fit` is the BRIDGE (returns role_fit_score). Per the deferral
   decision, this bridge is the EXPLICIT INTERIM for capability-fit until the real LLM-scored
   version is built with the research-runner migration. Label it clearly as temporary.

```python
def signal_rank(value):
    text = norm(value)
    if text == "strong":
        return 3
    if text == "moderate":
        return 2
    if text == "weak":
        return 1
    return 0


def compute_operator_agency_entry_score(row):
    """
    Measures whether there is likely a high-agency entry point for Katelynd,
    not whether the company generically needs operations help.
    """
    raw_timing = safe_num(row.get("operator_timing_score"), default=0)
    role_fit = safe_num(row.get("katelynd_role_fit_score"), default=0)
    pmf = safe_num(row.get("pmf_scale_score"), default=0)
    evidence = safe_num(row.get("evidence_confidence_score"), default=0)

    maturity = norm(row.get("company_maturity_read"))
    stage_fit = norm(row.get("stage_timing_fit"))
    agency_level = norm(row.get("likely_agency_level"))

    text_blob = has_any_text(
        row.get("why_now_or_why_not"),
        row.get("review_notes"),
        row.get("priority_review_note"),
        row.get("final_takeaway"),
        row.get("business_model_classification")
    )

    reset_signal = any(
        marker in text_blob
        for marker in [
            "restructure",
            "turnaround",
            "reset",
            "off track",
            "missed target",
            "leadership churn",
            "new business line",
            "operating rebuild",
            "rebuild",
            "integration",
            "pivot"
        ]
    )

    # Start from current timing score.
    score = raw_timing

    # Early-growth companies with credible PMF and capability fit get agency credit.
    if maturity in ["early-growth", "early growth", "series a/b", "series a", "series b"]:
        if role_fit >= 78 and pmf >= 70 and evidence >= 55:
            score = max(score, 82)
        if role_fit >= 82 and pmf >= 74 and evidence >= 60:
            score = max(score, 86)

    # Good stage timing means real potential whitespace.
    if stage_fit == "ideal":
        score = max(score, 85)
    elif stage_fit == "good":
        if role_fit >= 78 and pmf >= 70:
            score = max(score, 80)

    # Borderline can still be useful, but usually role-scope dependent.
    elif stage_fit == "borderline":
        score = min(max(score, 62), 76)

    # Too late caps agency unless there is a real reset.
    elif stage_fit == "too late":
        score = min(score, 62)

    # Mature scale-up can be high-agency only with a reset / transformation signal.
    if maturity in ["scale-up", "late-stage", "public", "near-ipo"]:
        if reset_signal:
            score = max(score, 78)
        elif maturity == "public":
            score = min(score, 58)
        else:
            score = min(score, 70)

    # Explicit agency level guardrails.
    if agency_level == "high":
        score = max(score, 80)
    elif agency_level == "medium":
        score = max(score, min(raw_timing + 5, 78))
    elif agency_level == "low":
        score = min(score, 62)

    return int(round(max(0, min(100, score))))


def compute_scale_path_quality(row):
    # NOTE: emits OLD vocabulary — reconcile per spec §2 when porting.
    commercial = signal_rank(row.get("commercial_scale_signal"))
    institutional = signal_rank(row.get("institutional_distribution_signal"))
    outcomes = signal_rank(row.get("outcomes_signal"))
    pmf = safe_num(row.get("pmf_scale_score"), default=0)
    evidence = safe_num(row.get("evidence_confidence_score"), default=0)

    plausible_raw = norm(row.get("plausible_near_term_scale_path"))
    plausible = plausible_raw in ["true", "yes", "1"]

    if commercial == 3 and institutional == 3:
        return "strong_dual_engine"
    if commercial == 3 or institutional == 3:
        if outcomes >= 2 or pmf >= 78:
            return "strong_single_engine"   # → split into institutional/commercial per §2
        return "credible_single_engine"     # → credible_path per §2
    if plausible and pmf >= 68 and evidence >= 50:
        return "credible_path"
    if outcomes == 3 and (commercial >= 2 or institutional >= 2):
        return "outcomes_plus_path"          # → emerging_path per §2
    if commercial >= 2 or institutional >= 2:
        return "emerging_path"
    return "weak_or_unclear"


def compute_target_archetype(row, capability_fit, agency_entry, scale_path_quality):
    # NOTE: eligibility list uses OLD vocabulary — update to reconciled names (§2 / item 5a).
    pmf = safe_num(row.get("pmf_scale_score"), default=0)
    evidence = safe_num(row.get("evidence_confidence_score"), default=0)
    maturity = norm(row.get("company_maturity_read"))
    stage_fit = norm(row.get("stage_timing_fit"))

    if (
        agency_entry >= 82
        and capability_fit >= 78
        and pmf >= 70
        and evidence >= 55
        and scale_path_quality in [
            "strong_dual_engine",
            "strong_single_engine",
            "credible_single_engine",
            "credible_path",
            "outcomes_plus_path"
        ]
        and maturity not in ["public", "near-ipo"]
    ):
        return "Ideal early-growth / high-agency target"

    if (
        pmf >= 80
        and evidence >= 60
        and (
            maturity in ["scale-up", "late-stage", "public", "near-ipo"]
            or stage_fit in ["borderline", "too late"]
        )
    ):
        return "Strong but mature benchmark"

    if (
        capability_fit >= 74
        and agency_entry >= 65
        and pmf >= 65
        and evidence >= 50
    ):
        return "Role-scope-dependent target"

    if pmf < 65 or evidence < 50:
        return "Interesting but under-proven"

    return "Watch list / weak fit"
```

## Helper functions these depend on (also from the notebook — port or reimplement)
- `safe_text(value)` — None/NaN → "", else str(value).strip()
- `safe_num(value, default)` — robust float parse; ""/None/NaN → default
- `norm(value)` — safe_text(value).lower()
- `has_any_text(*values)` — " ".join of lowercased safe_text of each (for the reset scan)
