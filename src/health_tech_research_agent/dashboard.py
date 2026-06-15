import re

import pandas as pd

from health_tech_research_agent.priority import extract_priority_code, priority_code, safe_text


def existing_cols(df, cols):
    """Return only columns that exist in the dataframe."""
    return [col for col in cols if col in df.columns]


def normalize_name(value):
    """Normalize company/name text for matching."""
    text = safe_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def join_unique(values, max_items=6):
    """Join unique nonblank values while preserving first-seen order."""
    cleaned = []

    for value in values:
        text = safe_text(value)
        if text and text not in cleaned:
            cleaned.append(text)

    if len(cleaned) > max_items:
        return ", ".join(cleaned[:max_items]) + f" + {len(cleaned) - max_items} more"

    return ", ".join(cleaned)


def safe_sort(df, sort_cols, ascending=None):
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


def contains_priority(value, codes):
    """Return whether a priority value resolves to one of the supplied P-codes."""
    return priority_code(value) in set(codes)


def coverage_status_from_counts(company_count, priority_or_diligence_count):
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


def coverage_status_rank(status):
    """Sort rank for segment coverage status."""
    status_text = safe_text(status).lower()

    if status_text == "strong segment read":
        return 1

    if status_text == "directional segment read":
        return 2

    if status_text == "sparse / needs more companies":
        return 3

    return 99


def companies_needed_for_directional_read(company_count, priority_or_diligence_count):
    """Companies/priority count needed to reach directional segment coverage."""
    needed_company_count = max(0, 2 - int(company_count))
    needed_priority_count = max(0, 1 - int(priority_or_diligence_count))
    return max(needed_company_count, needed_priority_count)


def companies_needed_for_stronger_read(company_count, priority_or_diligence_count):
    """Companies/priority count needed to reach strong segment coverage."""
    needed_company_count = max(0, 3 - int(company_count))
    needed_priority_count = max(0, 2 - int(priority_or_diligence_count))
    return max(needed_company_count, needed_priority_count)

def map_market_segment(row, segment_map):
    """Map a company row to a market segment, preserving an existing valid segment."""
    existing_segment = safe_text(row.get("market_segment", ""))

    if existing_segment and existing_segment.lower() not in ["unmapped", "unknown", "nan", "none"]:
        return existing_segment

    company_key = normalize_name(row.get("company", ""))

    if company_key in segment_map:
        return segment_map[company_key]

    # Fallback partial matching for names with descriptors.
    for known_name, segment in segment_map.items():
        if known_name in company_key or company_key in known_name:
            return segment

    return "Unmapped"


def map_strategic_bucket(row):
    """Map final priority level and calibration state to a strategic dashboard bucket."""
    code = extract_priority_code(row.get("final_priority_level", ""))

    if code == "P0":
        return "Active pursuit / highest-priority target"

    if code == "P1":
        return "Priority target / near-priority"

    if code == "P2":
        return "Diligence target"

    if code == "P3":
        return "Watch list"

    if code == "P4":
        return "Low priority / likely reject"

    calibration_flag = safe_text(row.get("calibration_flag", ""))

    if calibration_flag:
        return "Needs review"

    return "Unprioritized"
