from __future__ import annotations

import re
from typing import Iterable, Sequence

import pandas as pd

from health_tech_research_agent.priority import priority_code, safe_text


def existing_cols(df: pd.DataFrame, cols: Sequence[str]) -> list[str]:
    """Return only columns that exist in the dataframe."""
    return [col for col in cols if col in df.columns]


def normalize_name(value) -> str:
    """Normalize company/name text for matching."""
    text = safe_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def join_unique(values: Iterable, max_items: int = 6) -> str:
    """Join unique nonblank values while preserving first-seen order."""
    cleaned = []

    for value in values:
        text = safe_text(value)
        if text and text not in cleaned:
            cleaned.append(text)

    if len(cleaned) > max_items:
        return ", ".join(cleaned[:max_items]) + f" + {len(cleaned) - max_items} more"

    return ", ".join(cleaned)


def safe_sort(
    df: pd.DataFrame,
    sort_cols: Sequence[str],
    ascending: Sequence_items:
        return ", ".join(cleaned[:max_items]) + f" + {len(cleaned) - max_items} more"

    return ", ".[bool] | None = None,
) -> pd.DataFrame:
    """Sort by available columns only, preserving dataframe if no sort columns exist."""
    usable_cols = existing_cols(df, sort_cols)

    if not usable_cols:
        return df.copy()

    if ascending is None:
        usable_ascending = [True] * len(usable_cols)
    else:
        usable_ascending = list(ascending)[: len(usable_cols)]

    return df.sort_values(
        by=usable_cols,
        ascending=usable_ascending,
    ).copy()


def contains_priority(value, codes: Iterable[str]) -> bool:
    """Return whether a priority value resolves to one of the supplied P-codes."""
    return priority_code(value) in set(codes)


def coverage_status_from_counts(company_count, priority_or_diligence_count) -> str:
    """
    Segment coverage logic.

    Strong segment read:
    - At least 3 companies in the segment
    - At least 2 P0/P1/P2 companies

    Directional segment read:
    - At least 2 companies in the segment
    - At least 1 P0/P1/P2 company

    Sparse:
    - Anything below that threshold
    """
    company_count = int(company_count)
    priority_or_diligence_count = int(priority_or_diligence_count)

    if company_count >= 3 and priority_or_diligence_count >= 2:
        return "Strong segment read"

    if company_count >= 2 and priority_or_diligence_count >= 1:
        return "Directional segment read"

    return "Sparse / needs more companies"


def coverage_status_rank(status) -> int:
    """Sort rank for segment coverage status."""
    status_text = safe_text(status).lower()

    if status_text == "strong segment read":
        return 1

    if status_text == "directional segment read":
        return 2

    if status_text == "sparse / needs more companies":
        return 3

    return 99


def companies_needed_for_directional_read(
    company_count,
    priority_or_diligence_count,
) -> int:
    """Companies/priority count needed to reach directional segment coverage."""
    needed_company_count = max(0, 2 - int(company_count))
    needed_priority_count = max(0, 1 - int(priority_or_diligence_count))
    return max(needed_company_count, needed_priority_count)


def companies_needed_for_stronger_read(
    company_count,
    priority_or_diligence_count,
) -> int:
    """Companies/priority count needed to reach strong segment coverage."""
    needed_company_count = max(0, 3 - int(company_count))
    needed_priority_count = max(0, 2 - int(priority_or_diligence_count))
    return max(needed_company_count, needed_priority_count)
