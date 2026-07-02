"""Candidate Priority engine — deterministic forward-looking recommendation.

Built from archive/specs/candidate_priority_reference_spec.md (design) and
archive/specs/cell159_producer_source.md (authoritative formulas). This is the package
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

from .models import utc_now_iso
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

# P0 scale-path policy (Commit B): a clear path to scale via EITHER a strong
# institutional engine (payer) OR a strong commercial engine (D2C) qualifies for
# active pursuit — there is no standalone institutional>=3 requirement. Only the
# three STRONG engines count; credible_path / emerging_path are not enough for P0.
P0_SCALE_PATHS = frozenset({
    STRONG_DUAL_ENGINE,
    STRONG_INSTITUTIONAL_ENGINE,
    STRONG_COMMERCIAL_ENGINE,
})


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
# §9 — Reset / restructure signal (READ the researched field; text-scan retired)
# ---------------------------------------------------------------------------
# The previous text-scan was unreliable: it false-positived on incidental language
# (e.g. "workflow integration" tripping the "integration" marker — videahealth) and
# could not reproduce the audit's MANUAL reset overrides (e.g. ZOE). We now read the
# researched determination stored in `reset_or_restructure_signal`, which carries
# those manual overrides. Absent / blank / "unclear" -> False (e.g. the older-round
# companies that lack the field). `reset_or_restructure_basis` is preserved as
# supporting evidence on the output, not part of this boolean.
_RESET_TRUE_TOKENS = {"yes", "true", "y", "reset", "restructure", "1"}
_RESET_FALSE_TOKENS = {"", "no", "false", "n", "none", "unclear", "nan", "0"}


def _is_reset_value(value) -> bool:
    text = _norm(value)
    if text in _RESET_TRUE_TOKENS:
        return True
    if text in _RESET_FALSE_TOKENS:
        return False
    number = as_number(value)
    if number is not None and number == number:  # numeric, not NaN
        return number != 0.0
    return False


def reset_signal(row) -> bool:
    """Researched reset/restructure determination (the audit field, incl. manual
    overrides). Blank / absent / "unclear" -> False."""
    return _is_reset_value(row.get("reset_or_restructure_signal"))


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
# §4 — Capability-fit (real LLM-scored A1/A2/A3 average; Slice 4)
# ---------------------------------------------------------------------------
def capability_fit_score(row):
    """Real LLM-scored capability-fit (Slice 4): the stored deterministic average of A1/A2/A3
    (``katelynd_capability_fit_score``). Returns ``None`` when the score is suppressed (an
    attribute was unscorable) or absent, so the orchestrator's suppression guard routes the row
    to human review instead of auto-tiering on a missing/partial capability read. Replaces the
    interim ``katelynd_role_fit_score`` bridge.
    """
    value = as_number(row.get("katelynd_capability_fit_score"))
    return value if (value is not None and value == value) else None


# ---------------------------------------------------------------------------
# §5 — Target archetype (VERBATIM port from cell159; eligibility list reconciled, item 5a)
# ---------------------------------------------------------------------------
# Reconciled from cell159's old eligibility list (item 5a). emerging_path is
# DELIBERATELY EXCLUDED: "Ideal" must track the P0 pool, and emerging_path is
# gate-capped at P1 (it is not in HAS_STRONG_SCALE_PATH), so labeling it "Ideal"
# would contradict the priority. This also matches the snapshot's archetype behavior.
_ARCHETYPE_ELIGIBLE_SCALE_PATHS = frozenset({
    STRONG_DUAL_ENGINE,
    STRONG_INSTITUTIONAL_ENGINE,
    STRONG_COMMERCIAL_ENGINE,
    CREDIBLE_PATH,
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


# ---------------------------------------------------------------------------
# §6 — V4.1 gate + §7 public/near-IPO cap
# ---------------------------------------------------------------------------
_MATURE_BENCHMARK_MATURITIES = {"late-stage", "public", "near-ipo"}
_PUBLIC_MATURITIES = {"public", "near-ipo"}

ARCHETYPE_UNDER_PROVEN = "Interesting but under-proven"
ARCHETYPE_WEAK_FIT = "Watch list / weak fit"
ARCHETYPE_MATURE_BENCHMARK = "Strong but mature benchmark"

# Candidate engine ranks P0-P3 only — never P4 (Q5).
_CANDIDATE_LABELS = {
    "P0": "P0: Active pursuit target",
    "P1": "P1: High-priority diligence",
    "P2": "P2: Worth deeper diligence",
    "P3": "P3: Watch list",
}
_CANDIDATE_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def v41_gate(
    *,
    maturity,
    stage_fit,
    agency_level,
    thesis,
    pmf,
    evidence,
    capability,
    agency,
    scale_path,
    commercial,
    institutional,
    outcomes,
    archetype,
    has_reset,
    capability_reset_adjusted=None,
) -> str:
    """The V4.1 candidate-priority gate (spec §6), ported as-is. Returns P0-P3 only
    (never P4 — Q5). The public/near-IPO cap (§7) is applied separately as an overlay.

    under_proven / weak_fit map to the two archetypes (Q1).
    """
    maturity = _norm(maturity)
    stage_fit = _norm(stage_fit)
    agency_level = _norm(agency_level)
    thesis = _safe_num(thesis)
    pmf = _safe_num(pmf)
    evidence = _safe_num(evidence)
    capability = _safe_num(capability)
    agency = _safe_num(agency)

    # Slice 4 double-count fix: for a reset-LIFTED scale-up, the P1 capability threshold uses the
    # A1/A3 mean only — A2's strain was already consumed by the reset cap-lift / agency floor, so
    # counting it again here would let ONE event clear two gates (reset + capability). Applies to
    # the scale-up reset P1 paths (p1_scaleup_reset AND p1_standard, since a reset-floored
    # scale-up/good can reach P1 either way). Everything else uses the full capability. Falls back
    # to the full capability when no adjusted value is supplied (pre-Slice-4 callers/rows), so
    # behavior is unchanged unless an adjusted value is passed. The stored score is never altered.
    if has_reset and maturity == "scale-up" and capability_reset_adjusted is not None:
        gate_capability_for_p1 = _safe_num(capability_reset_adjusted)
    else:
        gate_capability_for_p1 = capability
    commercial = int(commercial)
    institutional = int(institutional)
    outcomes = int(outcomes)

    early_growth = maturity in _EARLY_GROWTH_MATURITIES
    mature_benchmark = archetype == ARCHETYPE_MATURE_BENCHMARK or maturity in _MATURE_BENCHMARK_MATURITIES
    scaleup_borderline = maturity == "scale-up" and stage_fit == "borderline"
    scaleup_good_with_reset = (
        maturity == "scale-up" and stage_fit in {"good", "borderline"} and has_reset
    )
    weak_noninstitutional_scaleup = (
        not early_growth
        and not has_reset
        and scale_path == EMERGING_PATH
        and institutional < 2
        and commercial < 3
    )
    under_proven = archetype == ARCHETYPE_UNDER_PROVEN
    weak_fit = archetype == ARCHETYPE_WEAK_FIT
    has_path = scale_path in HAS_SCALE_PATH
    stage_ok = stage_fit in {"ideal", "good"}
    agency_not_low = agency_level != "low"

    p0 = (
        early_growth and stage_ok
        and thesis >= 78 and pmf >= 74 and evidence >= 60
        and capability >= 78 and agency >= 82
        # Strong commercial OR strong institutional (OR dual) is a clear scale path;
        # no standalone institutional>=3 requirement (Commit B).
        and scale_path in P0_SCALE_PATHS and outcomes >= 2
        and agency_not_low and not under_proven and not weak_fit
    )

    p1_standard = (
        not p0 and not mature_benchmark and not scaleup_borderline
        and not weak_noninstitutional_scaleup and not under_proven and not weak_fit
        and stage_ok
        and thesis >= 75 and pmf >= 68 and evidence >= 55
        and gate_capability_for_p1 >= 74 and agency >= 78
        and has_path and agency_not_low
    )
    p1_early_growth_emerging = (
        early_growth and scale_path == EMERGING_PATH
        and thesis >= 78 and pmf >= 70 and evidence >= 55
        and capability >= 78 and agency >= 82
        and institutional >= 2 and outcomes >= 2
    )
    p1_scaleup_reset = (
        maturity == "scale-up" and stage_fit in {"good", "borderline"} and has_reset
        and thesis >= 75 and pmf >= 68 and evidence >= 55
        and gate_capability_for_p1 >= 74 and agency >= 78
        and has_path and agency_not_low
    )
    p1 = p1_standard or p1_early_growth_emerging or p1_scaleup_reset

    # Mature cap (in-gate): a mature/scaleup-borderline company without a scale-up
    # reset cannot be P0/P1.
    if (mature_benchmark or scaleup_borderline) and not scaleup_good_with_reset:
        p0 = False
        p1 = False

    if p0:
        return "P0"
    if p1:
        return "P1"
    if (
        not under_proven and not weak_fit
        and pmf >= 60 and evidence >= 45 and capability >= 65 and has_path
    ):
        return "P2"
    return "P3"


def apply_public_near_ipo_cap(priority: str, maturity, has_reset: bool) -> str:
    """§7 overlay: a public/near-IPO company is forced to P3 UNLESS a reset signal
    lifts the cap — reset is the ONLY exception (RESOLVED 7a). Never promotes."""
    if _norm(maturity) in _PUBLIC_MATURITIES and not has_reset:
        return "P3"
    return priority


# ---------------------------------------------------------------------------
# §8 — Outputs + reason text (V4.1 fixed per-tier strings; 8a)
# ---------------------------------------------------------------------------
# Capability-fit is now the real LLM-scored A1/A2/A3 average (Slice 4), so the framework is no
# longer interim — these candidate priorities reflect the production capability scoring model.
CANDIDATE_FRAMEWORK_VERSION = "V4.2"
_CANDIDATE_SOURCE = "deterministic engine (real LLM-scored capability-fit)"
_CANDIDATE_REASONS = {
    "P0": "Active pursuit: clears the V4.2 P0 gate (early-growth, strong fit/timing, real scale channel).",
    "P1": "High-priority diligence: near active-pursuit; one or more P0 conditions unmet.",
    "P2": "Worth deeper diligence: credible, but not yet a clean active-pursuit case.",
    "P3": "Watch list: does not currently justify active pursuit.",
}


def compute_candidate_priority(row, *, now_iso=None) -> dict:
    """Run the full §0 pipeline for one company and emit the candidate fields.

    Order: signals -> scale_path -> agency -> capability -> archetype ->
    gate (§6) -> public/near-IPO cap (§7) -> outputs (§8). Emits P0-P3 only (Q5).
    Read-only: does NOT touch final_priority_level or the master (Commit 5 held).
    """
    signals = infer_signals(row)
    commercial = signals["commercial_scale_signal_inferred"]
    institutional = signals["institutional_distribution_signal_inferred"]
    outcomes = signals["outcomes_signal_inferred"]

    scale_path = scale_path_quality(
        commercial=commercial,
        institutional=institutional,
        outcomes=outcomes,
        pmf=row.get("pmf_scale_score"),
        evidence=row.get("evidence_confidence_score"),
        plausible=parse_plausible(row.get("plausible_near_term_scale_path")),
    )
    agency = operator_agency_entry_score(row)
    capability = capability_fit_score(row)  # real A1/A2/A3 average; None when suppressed/absent
    has_reset = reset_signal(row)
    capability_needs_review = capability is None

    # archetype is informational; compute it safely even when capability is unscorable.
    archetype = target_archetype(row, _safe_num(capability), agency, scale_path)

    if capability_needs_review:
        # Slice 4 suppression guard: no trustworthy capability score (an attribute was unscorable,
        # or the row predates capability scoring) -> cannot auto-tier on capability. Route to P3
        # for human review; the gate and the reset / public overlays cannot promote it.
        level = "P3"
        reason = (
            "P3 (capability-fit unscorable): an attribute could not be assessed, or the row has "
            "no capability score yet -> routed to human review."
        )
    else:
        # Slice 4 gate double-count fix: the reset-lifted scale-up P1 threshold uses the A1/A3
        # mean (A2 excluded — already consumed by the reset lift). Both components are present
        # here (a null one would have suppressed the full score, caught above), so it is defined.
        _a1 = as_number(row.get("capability_a1_score"))
        _a3 = as_number(row.get("capability_a3_score"))
        capability_reset_adjusted = (
            (_a1 + _a3) / 2.0
            if (_a1 is not None and _a1 == _a1 and _a3 is not None and _a3 == _a3)
            else None
        )
        level = v41_gate(
            maturity=row.get("company_maturity_read"),
            stage_fit=row.get("stage_timing_fit"),
            agency_level=row.get("likely_agency_level"),
            thesis=row.get("thesis_fit_score"),
            pmf=row.get("pmf_scale_score"),
            evidence=row.get("evidence_confidence_score"),
            capability=capability,
            agency=agency,
            scale_path=scale_path,
            commercial=commercial,
            institutional=institutional,
            outcomes=outcomes,
            archetype=archetype,
            has_reset=has_reset,
            capability_reset_adjusted=capability_reset_adjusted,
        )
        level = apply_public_near_ipo_cap(level, row.get("company_maturity_read"), has_reset)
        reason = _CANDIDATE_REASONS[level]

    return {
        "candidate_priority_level": _CANDIDATE_LABELS[level],
        "candidate_priority_code": level,
        "candidate_priority_rank": _CANDIDATE_RANK[level],
        "candidate_priority_reason": reason,
        "candidate_priority_framework_version": CANDIDATE_FRAMEWORK_VERSION,
        "candidate_priority_source": _CANDIDATE_SOURCE,
        "candidate_priority_updated_at": now_iso or utc_now_iso(),
        # Producer outputs (for the display contract + audit trail).
        "target_archetype": archetype,
        "scale_path_quality": scale_path,
        "operator_agency_entry_score": agency,
        "katelynd_capability_fit_score": capability,
        "capability_needs_review": capability_needs_review,
        "commercial_scale_signal_inferred": commercial,
        "institutional_distribution_signal_inferred": institutional,
        "outcomes_signal_inferred": outcomes,
        "reset_or_restructure_signal": has_reset,
        "reset_or_restructure_basis": safe_text(row.get("reset_or_restructure_basis")),
    }
