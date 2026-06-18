"""Candidate Priority engine — deterministic forward-looking recommendation.

Built from specs/candidate_priority_reference_spec.md (design) and
specs/cell159_producer_source.md (authoritative formulas). This is the package
home for candidate-priority logic that previously existed only as a one-time
notebook audit snapshot.

Commit 1 scope: text-signal conversion (spec §1) and the reconciled scale-path
quality classifier (spec §2).

The scale-path vocabulary is defined ONCE here, and the V4.1 gate's accepted
path sets are built from those same constants. A producer value therefore can
never silently fall outside what the gate recognizes — that silent break (the
old `strong_single_engine` vocabulary the gate did not accept) is the bug §2
reconciles, and the closure test in the suite locks it.
"""

from __future__ import annotations

from .priority import as_number, safe_text

# ---------------------------------------------------------------------------
# Shared scale-path vocabulary (single source of truth) — spec §2
# ---------------------------------------------------------------------------
STRONG_DUAL_ENGINE = "strong_dual_engine"
STRONG_INSTITUTIONAL_ENGINE = "strong_institutional_engine"
STRONG_COMMERCIAL_ENGINE = "strong_commercial_engine"
CREDIBLE_DUAL_PATH = "credible_dual_path"  # gate-accepted but never emitted (spec 2c)
CREDIBLE_PATH = "credible_path"
EMERGING_PATH = "emerging_path"
WEAK_OR_UNCLEAR = "weak_or_unclear"

# Every value scale_path_quality() can emit.
PRODUCER_SCALE_PATHS = frozenset({
    STRONG_DUAL_ENGINE,
    STRONG_INSTITUTIONAL_ENGINE,
    STRONG_COMMERCIAL_ENGINE,
    CREDIBLE_PATH,
    EMERGING_PATH,
    WEAK_OR_UNCLEAR,
})

# The V4.1 gate's accepted-path sets (spec §2, lines 89-92), built from the same
# constants so producer and gate cannot drift apart.
HAS_STRONG_SCALE_PATH = frozenset({
    STRONG_DUAL_ENGINE,
    STRONG_INSTITUTIONAL_ENGINE,
    STRONG_COMMERCIAL_ENGINE,
    CREDIBLE_DUAL_PATH,
    CREDIBLE_PATH,
})
HAS_SCALE_PATH = HAS_STRONG_SCALE_PATH | {EMERGING_PATH}

# Names the gate recognizes at all: a real scale path, or the explicit "no path"
# sentinel. Any producer output OUTSIDE this set would silently read to the gate
# as "no scale path" and demote a strong company — the closure test forbids it.
RECOGNIZED_SCALE_PATHS = HAS_SCALE_PATH | {WEAK_OR_UNCLEAR}


# ---------------------------------------------------------------------------
# Small helpers (mirror cell 159 semantics: norm + safe_num)
# ---------------------------------------------------------------------------
def _norm(value) -> str:
    return safe_text(value).lower()


def _safe_num(value, default: float = 0.0) -> float:
    number = as_number(value)
    if number is None or number != number:  # None or NaN
        return default
    return float(number)


# ---------------------------------------------------------------------------
# §1 — Signal conversion (text → 0-3)
# ---------------------------------------------------------------------------
def signal_text_to_score(text) -> int:
    """Map an LLM text signal to the 0-3 scale (spec §1 / cell159 signal_rank)."""
    value = _norm(text)
    if value == "strong":
        return 3
    if value == "moderate":
        return 2
    if value == "weak":
        return 1
    return 0  # none / blank / unrecognized


_SIGNAL_SOURCE_FIELDS = {
    "commercial_scale_signal_inferred": "commercial_scale_signal",
    "institutional_distribution_signal_inferred": "institutional_distribution_signal",
    "outcomes_signal_inferred": "outcomes_signal",
}


def infer_signals(row) -> dict:
    """Produce the three numeric *_signal_inferred from the LLM text signals."""
    return {
        inferred: signal_text_to_score(row.get(source, ""))
        for inferred, source in _SIGNAL_SOURCE_FIELDS.items()
    }


# ---------------------------------------------------------------------------
# §2 — Reconciled scale-path quality
# ---------------------------------------------------------------------------
def parse_plausible(value) -> bool:
    return _norm(value) in {"true", "yes", "1"}


def scale_path_quality(commercial, institutional, outcomes, pmf, evidence, plausible) -> str:
    """Classify the scale path (spec §2, reconciled from cell159 to gate vocab).

    commercial/institutional/outcomes: 0-3 ints; pmf/evidence: numeric;
    plausible: bool. Returns a member of PRODUCER_SCALE_PATHS.
    """
    commercial = int(commercial)
    institutional = int(institutional)
    outcomes = int(outcomes)
    pmf = _safe_num(pmf)
    evidence = _safe_num(evidence)

    if commercial == 3 and institutional == 3:
        return STRONG_DUAL_ENGINE

    # Reconciled: split the old strong_single_engine by which engine is strong,
    # and map the old credible_single_engine -> credible_path (spec §2).
    if institutional == 3 and commercial < 3:
        if outcomes >= 2 or pmf >= 78:
            return STRONG_INSTITUTIONAL_ENGINE
        return CREDIBLE_PATH
    if commercial == 3 and institutional < 3:
        if outcomes >= 2 or pmf >= 78:
            return STRONG_COMMERCIAL_ENGINE
        return CREDIBLE_PATH

    if plausible and pmf >= 68 and evidence >= 50:
        return CREDIBLE_PATH
    # Old outcomes_plus_path -> emerging_path (spec §2).
    if outcomes == 3 and (commercial >= 2 or institutional >= 2):
        return EMERGING_PATH
    if commercial >= 2 or institutional >= 2:
        return EMERGING_PATH
    return WEAK_OR_UNCLEAR


def scale_path_quality_for_row(row) -> str:
    """Row-level convenience: convert text signals, then classify."""
    signals = infer_signals(row)
    return scale_path_quality(
        commercial=signals["commercial_scale_signal_inferred"],
        institutional=signals["institutional_distribution_signal_inferred"],
        outcomes=signals["outcomes_signal_inferred"],
        pmf=row.get("pmf_scale_score"),
        evidence=row.get("evidence_confidence_score"),
        plausible=parse_plausible(row.get("plausible_near_term_scale_path")),
    )


# ---------------------------------------------------------------------------
# §9 — Reset / restructure signal (shared text-scan; NO hardcoded company names)
# ---------------------------------------------------------------------------
_RESET_MARKERS = (
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
    "pivot",
)

_RESET_TEXT_FIELDS = (
    "why_now_or_why_not",
    "review_notes",
    "priority_review_note",
    "final_takeaway",
    "business_model_classification",
)


def reset_signal(row) -> bool:
    """Detect a reset/restructure entry point from researched text (cell159 markers).

    Shared by the agency-entry producer and the V4.1 cap. Pure text-scan over the
    researched fields below — no hardcoded company names (the `{"zoe"}` hardcode
    lived only in the gate cell we are not porting).
    """
    blob = " ".join(_norm(row.get(field, "")) for field in _RESET_TEXT_FIELDS)
    return any(marker in blob for marker in _RESET_MARKERS)


# ---------------------------------------------------------------------------
# §3 — Operator agency-entry score (VERBATIM port from cell159; de-hardcoded reset)
# ---------------------------------------------------------------------------
_EARLY_GROWTH_MATURITIES = {"early-growth", "early growth", "series a/b", "series a", "series b"}
_MATURE_MATURITIES = {"scale-up", "late-stage", "public", "near-ipo"}


def operator_agency_entry_score(row) -> int:
    """Verbatim cell159 formula. The max()/min() band precedence is authoritative
    — do not simplify the stacking."""
    raw_timing = _safe_num(row.get("operator_timing_score"))
    role_fit = _safe_num(row.get("katelynd_role_fit_score"))
    pmf = _safe_num(row.get("pmf_scale_score"))
    evidence = _safe_num(row.get("evidence_confidence_score"))

    maturity = _norm(row.get("company_maturity_read"))
    stage_fit = _norm(row.get("stage_timing_fit"))
    agency_level = _norm(row.get("likely_agency_level"))

    has_reset = reset_signal(row)
    score = raw_timing

    if maturity in _EARLY_GROWTH_MATURITIES:
        if role_fit >= 78 and pmf >= 70 and evidence >= 55:
            score = max(score, 82)
        if role_fit >= 82 and pmf >= 74 and evidence >= 60:
            score = max(score, 86)

    if stage_fit == "ideal":
        score = max(score, 85)
    elif stage_fit == "good":
        if role_fit >= 78 and pmf >= 70:
            score = max(score, 80)
    elif stage_fit == "borderline":
        score = min(max(score, 62), 76)
    elif stage_fit == "too late":
        score = min(score, 62)

    if maturity in _MATURE_MATURITIES:
        if has_reset:
            score = max(score, 78)
        elif maturity == "public":
            score = min(score, 58)
        else:
            score = min(score, 70)

    if agency_level == "high":
        score = max(score, 80)
    elif agency_level == "medium":
        score = max(score, min(raw_timing + 5, 78))
    elif agency_level == "low":
        score = min(score, 62)

    return int(round(max(0, min(100, score))))


# ---------------------------------------------------------------------------
# §4 — Capability-fit (INTERIM BRIDGE; real LLM-scored version deferred)
# ---------------------------------------------------------------------------
def capability_fit_score(row) -> float:
    """INTERIM: capability-fit == katelynd_role_fit_score (cell159 stopgap).

    This is a clearly-labeled placeholder. The real LLM-scored capability-fit
    (spec §4: three attributes A1/A2/A3) is DEFERRED until the research runner
    migrates to the package; this bridge keeps the engine runnable meanwhile, and
    the priorities it yields are interim-quality (not written to master as final).
    """
    return _safe_num(row.get("katelynd_role_fit_score"))


# ---------------------------------------------------------------------------
# §5 — Target archetype (VERBATIM port from cell159; eligibility list reconciled, item 5a)
# ---------------------------------------------------------------------------
# Reconciled from cell159's old eligibility list
# {strong_dual_engine, strong_single_engine, credible_single_engine, credible_path,
#  outcomes_plus_path} -> the names the reconciled producer (§2) actually emits.
_ARCHETYPE_ELIGIBLE_SCALE_PATHS = frozenset({
    STRONG_DUAL_ENGINE,
    STRONG_INSTITUTIONAL_ENGINE,
    STRONG_COMMERCIAL_ENGINE,
    CREDIBLE_PATH,
    EMERGING_PATH,
})


def target_archetype(row, capability_fit, agency_entry, scale_path) -> str:
    """Verbatim cell159 logic with the reconciled scale-path eligibility list."""
    pmf = _safe_num(row.get("pmf_scale_score"))
    evidence = _safe_num(row.get("evidence_confidence_score"))
    maturity = _norm(row.get("company_maturity_read"))
    stage_fit = _norm(row.get("stage_timing_fit"))

    if (
        agency_entry >= 82
        and capability_fit >= 78
        and pmf >= 70
        and evidence >= 55
        and scale_path in _ARCHETYPE_ELIGIBLE_SCALE_PATHS
        and maturity not in {"public", "near-ipo"}
    ):
        return "Ideal early-growth / high-agency target"

    if (
        pmf >= 80
        and evidence >= 60
        and (maturity in _MATURE_MATURITIES or stage_fit in {"borderline", "too late"})
    ):
        return "Strong but mature benchmark"

    if capability_fit >= 74 and agency_entry >= 65 and pmf >= 65 and evidence >= 50:
        return "Role-scope-dependent target"

    if pmf < 65 or evidence < 50:
        return "Interesting but under-proven"

    return "Watch list / weak fit"
