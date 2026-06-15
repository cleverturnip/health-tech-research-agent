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

