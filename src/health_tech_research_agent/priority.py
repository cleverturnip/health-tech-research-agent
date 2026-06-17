"""
Shared priority utilities for the Health Tech Research Agent.

This module centralizes the P0-P4 priority model so dashboard steps do not
maintain separate, conflicting versions of priority parsing/ranking logic.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


def is_blank_value(value: Any) -> bool:
    """Return True when a value is missing or empty after stripping."""
    return pd.isna(value) or str(value).strip() == ""


def safe_text(value: Any) -> str:
    """Convert a value to clean text, treating pandas/None blanks as empty string."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def extract_priority_code(value: Any) -> str:
    """
    Extract P0, P1, P2, P3, or P4 from a normalized or raw priority value.
    """
    text = safe_text(value).upper()
    match = re.search(r"\bP[0-4]\b", text)
    return match.group(0) if match else ""


def normalize_priority_level(value: Any) -> str:
    """
    Convert old and new priority labels into clean dashboard labels.

    Legacy mapping:
    - P1: High-priority target              -> P0
    - Strong P2 / P1-border                -> P1
    - Review P2                            -> P2

    Native model:
    - P0 = Highest-priority target
    - P1 = Near-priority target
    - P2 = Worth deeper diligence
    - P3 = Watch list
    - P4 = Low priority / likely reject
    """
    text = safe_text(value)

    if text == "":
        return ""

    lower = text.lower()

    # Native P0 or old top-priority P1.
    # Keep this before P1-border logic so old "P1: High-priority" maps up to P0.
    if (
        lower.startswith("p0")
        or "highest-priority" in lower
        or "highest priority" in lower
        or "active pursuit" in lower
        or "top-priority" in lower
        or "top priority" in lower
        or lower.startswith("p1: high-priority")
        or lower.startswith("p1: high priority")
        or lower.startswith("p1 - high-priority")
        or lower.startswith("p1 - high priority")
    ):
        return "P0: Highest-priority target"

    # Native P1 / old P1-border.
    if (
        lower.startswith("p1: near-priority")
        or lower.startswith("p1: near priority")
        or lower.startswith("p1 - near-priority")
        or lower.startswith("p1 - near priority")
        or "p1-border" in lower
        or "p1 border" in lower
        or "near-priority" in lower
        or "near priority" in lower
        or "strong p2" in lower
        or "p0-border" in lower
        or "p0 border" in lower
    ):
        return "P1: Near-priority target"

    if (
        lower.startswith("p2")
        or lower.startswith("review p2")
        or "review p2" in lower
        or "worth deeper diligence" in lower
        or "diligence target" in lower
        or "deeper diligence" in lower
    ):
        return "P2: Worth deeper diligence"

    if (
        lower.startswith("p3")
        or "watch list" in lower
        or "watchlist" in lower
    ):
        return "P3: Watch list"

    if (
        lower.startswith("p4")
        or "low priority" in lower
        or "likely reject" in lower
        or "weak fit" in lower
        or "reject" in lower
    ):
        return "P4: Low priority / likely reject"

    # Ambiguous bare P1:
    # In the native model, P1 means near-priority.
    # Historical old P1 should ideally include "High-priority target" and maps to P0 above.
    if lower == "p1":
        return "P1: Near-priority target"

    # Preserve unmapped text rather than destroying context.
    return text


def priority_code(value: Any) -> str:
    """Return the normalized priority code P0-P4 when present."""
    normalized = normalize_priority_level(value)
    return extract_priority_code(normalized)


def priority_rank(value: Any) -> int:
    """
    Return sort rank for priority level.
    Lower rank sorts earlier.
    """
    code = priority_code(value)

    return {
        "P0": 0,
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4,
    }.get(code, 99)


def determine_priority_source(row):
    """
    Determine whether final priority came from model/adjudication or human review.

    A row is Human Reviewed when:
    - review_status explicitly says reviewed / human reviewed / approved, or
    - reviewed_priority_level differs from priority_level.

    This lets humans affirm the model priority without being incorrectly shown
    as Auto Adjudicated.
    """
    review_status = safe_text(row.get("review_status", "")).lower()

    human_review_markers = [
        "human reviewed",
        "reviewed",
        "approved",
        "manually reviewed",
    ]

    needs_review_markers = [
        "needs review",
        "new batch",
        "existing company",
    ]

    if any(marker in review_status for marker in human_review_markers) and not any(
        marker in review_status for marker in needs_review_markers
    ):
        return "Human Reviewed"

    reviewed = normalize_priority_level(row.get("reviewed_priority_level", ""))
    model = normalize_priority_level(row.get("priority_level", ""))

    if reviewed and model and reviewed != model:
        return "Human Reviewed"

    return "Auto Adjudicated"


def apply_priority_fields(input_df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply final priority fields to a dataframe.

    Creates / updates:
    - final_priority_level
    - priority_source
    - final_priority_code
    - final_priority_rank
    - decision_priority
    - decision_priority_sort
    """
    output_df = input_df.copy()

    if "priority_level" not in output_df.columns:
        output_df["priority_level"] = ""

    if "reviewed_priority_level" not in output_df.columns:
        output_df["reviewed_priority_level"] = ""

    if "priority_review_note" not in output_df.columns:
        output_df["priority_review_note"] = ""

    output_df["final_priority_level"] = output_df.apply(
        lambda row: normalize_priority_level(row.get("reviewed_priority_level", ""))
        if not is_blank_value(row.get("reviewed_priority_level", ""))
        else normalize_priority_level(row.get("priority_level", "")),
        axis=1,
    )

    output_df["priority_source"] = output_df.apply(determine_priority_source, axis=1)

    output_df["final_priority_code"] = output_df["final_priority_level"].apply(priority_code)
    output_df["final_priority_rank"] = output_df["final_priority_level"].apply(priority_rank)

    # Backward-compatible aliases for older dashboard steps.
    output_df["decision_priority"] = output_df["final_priority_level"]
    output_df["decision_priority_sort"] = output_df["final_priority_rank"]

    return output_df


# ---------------------------------------------------------------------------
# Calibration flags
# ---------------------------------------------------------------------------
# Calibration flags are advisory "CHECK:" / "REVIEW:" notes that surface
# priority/evidence calibration concerns (CLAUDE.md rule 8 - incorrect outputs
# are calibration data that should improve the decision logic).
#
# On dashboard rebuild they are recomputed from the FINAL (reviewed) priority,
# so a flag computed against an earlier auto/adjudicated priority does not
# persist after a human review changes the priority. Keying is done on the
# normalized P-code (P0-P4), not exact label strings -- this fixes flags that
# were silently dead because they matched a label string the normalized
# pipeline no longer produces.


def as_number(value: Any):
    """Best-effort float parse; returns None when the value is not numeric."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_d2c_specific_business_model(business_model_text: Any) -> bool:
    """
    Detect true D2C / cash-pay companies without over-flagging hybrid
    payer/employer/provider-enabled consumer platforms.
    """
    business_model = safe_text(business_model_text).lower()

    institutional_terms = [
        "b2b2c",
        "payer",
        "employer",
        "provider",
        "benefits",
        "insurance",
        "health plan",
        "government",
        "pharma",
        "medicaid",
        "medicare",
    ]

    has_institutional_path = any(term in business_model for term in institutional_terms)

    appears_d2c = (
        "d2c" in business_model
        or "cash-pay" in business_model
        or "cash pay" in business_model
        or "primarily d2c" in business_model
        or "primarily cash" in business_model
    )

    # Do not treat generic "consumer health platform" as D2C if the
    # classification is clearly hybrid/B2B2C/payer/employer/provider-enabled.
    return appears_d2c and not (has_institutional_path and "hybrid" in business_model)


def commercial_signal_is_weak(commercial_scale_finding: Any, commercial_scale_assessment: Any) -> bool:
    """Return True when commercial-scale evidence is missing or explicitly weak."""
    text = (
        safe_text(commercial_scale_finding)
        + " "
        + safe_text(commercial_scale_assessment)
    ).lower()

    weak_phrases = [
        "no strong public commercial scale evidence found",
        "weak evidence",
        "commercial scale evidence is weak",
        "weak-to-moderate",
        "not enough hard evidence",
        "not strongly substantiated",
        "not revenue quality",
        "no credible public revenue",
        "no public revenue",
        "no verified current arr",
        "no public arr",
        "no subscriber count",
        "no retention",
        "no renewal",
        "no cac",
        "no margin",
    ]

    if safe_text(commercial_scale_finding) == "":
        return True

    return any(phrase in text for phrase in weak_phrases)


def build_calibration_flag(row, *, priority_field: str = "final_priority_level") -> str:
    """
    Compute the priority/score-driven calibration flag for a single row.

    Keyed off the normalized P-code from ``priority_field`` (default
    ``final_priority_level``) rather than exact label strings, so the flag
    tracks the reviewed priority. Returns a " | "-joined flag string, or ""
    when no condition holds.
    """
    flags = []

    code = priority_code(row.get(priority_field, ""))
    business_model = safe_text(row.get("business_model_classification"))
    commercial_scale_finding = safe_text(row.get("commercial_scale_finding"))
    commercial_scale_assessment = safe_text(row.get("commercial_scale_assessment"))

    thesis = as_number(row.get("thesis_fit_score"))
    pmf = as_number(row.get("pmf_scale_score"))
    evidence = as_number(row.get("evidence_confidence_score"))
    role_fit = as_number(row.get("katelynd_role_fit_score"))
    operator_timing = as_number(row.get("operator_timing_score"))

    # P2 evidence / PMF checks.
    if code == "P2":
        if evidence is not None and evidence < 50:
            flags.append("CHECK: P2 with low evidence")

        if pmf is not None and pmf < 60:
            flags.append("CHECK: P2 with weak PMF/scale")

        if (
            role_fit is not None
            and operator_timing is not None
            and role_fit < 70
            and operator_timing < 70
        ):
            flags.append("CHECK: P2 with weak role/timing fit")

        if (
            evidence is not None
            and pmf is not None
            and (evidence < 65 or pmf < 70)
        ):
            flags.append("REVIEW: P2 with moderate evidence/PMF")

    # Possible under-promotion: strong scores but not already a P0/P1 priority.
    if code not in ("P0", "P1"):
        if (
            thesis is not None
            and pmf is not None
            and evidence is not None
            and role_fit is not None
            and operator_timing is not None
            and thesis >= 90
            and pmf >= 80
            and evidence >= 70
            and role_fit >= 80
            and operator_timing >= 75
        ):
            flags.append("CHECK: possible P1 under-promotion")

    # D2C / commercial-scale checks.
    d2c_specific_review_needed = is_d2c_specific_business_model(business_model)
    weak_commercial_signal = commercial_signal_is_weak(
        commercial_scale_finding,
        commercial_scale_assessment,
    )

    if d2c_specific_review_needed and code in ("P1", "P2") and weak_commercial_signal:
        flags.append("REVIEW: D2C priority with weak commercial-scale evidence")

    if (
        d2c_specific_review_needed
        and pmf is not None
        and evidence is not None
        and pmf >= 75
        and evidence < 60
    ):
        flags.append("REVIEW: D2C scale claim with moderate/weak evidence confidence")

    return " | ".join(flags)


def _append_operator_timing_flag(base: Any, extra: Any) -> str:
    """Append the operator-timing sub-flag to a base flag, de-duplicated."""
    base = safe_text(base)
    extra = safe_text(extra)

    if not extra:
        return base
    if not base:
        return extra
    if extra in base:
        return base
    return base + " | " + extra


def recompute_calibration_flags(
    df: pd.DataFrame,
    *,
    priority_field: str = "final_priority_level",
    operator_timing_field: str = "operator_timing_calibration_flag",
) -> pd.DataFrame:
    """
    Return a COPY of ``df`` whose ``calibration_flag`` column is recomputed from
    the current row state and ``priority_field``.

    This is a read-only, in-memory recompute for dashboard display: it does not
    mutate ``df`` and never writes any file, so the master's stored historical
    flag is left untouched. Stale flags whose triggering condition no longer
    holds are dropped; the operator-timing sub-flag (which is not
    priority-driven) is preserved.
    """
    out = df.copy()

    if len(out) == 0:
        if "calibration_flag" not in out.columns:
            out["calibration_flag"] = pd.Series(dtype="object")
        return out

    recomputed = out.apply(
        lambda row: build_calibration_flag(row, priority_field=priority_field),
        axis=1,
    ).tolist()

    if operator_timing_field in out.columns:
        recomputed = [
            _append_operator_timing_flag(base, extra)
            for base, extra in zip(recomputed, out[operator_timing_field].tolist())
        ]

    out["calibration_flag"] = recomputed
    return out

