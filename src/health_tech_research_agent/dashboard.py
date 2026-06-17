import re

import pandas as pd

from health_tech_research_agent.priority import (
    apply_priority_fields,
    extract_priority_code,
    priority_code,
    recompute_calibration_flags,
    safe_text,
)
from health_tech_research_agent.taxonomy import (
    allowed_codes,
    classify_dataframe,
    code_label_maps,
    load_taxonomy_tables,
    normalize_code,
    normalize_key,
)


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


# ===========================================================================
# Dashboard rebuild: frame construction, workbook sheets, and validation
# ===========================================================================

MASTER_DASHBOARD_COLUMNS = [
    "company",
    "final_priority_level",
    "final_priority_code",
    "final_priority_rank",
    "priority_source",
    "priority_level",
    "reviewed_priority_level",
    "primary_market_segment_code",
    "primary_market_segment",
    "market_segment",
    "subsegment_tags",
    "product_model_tags",
    "distribution_model_tags",
    "data_input_tags",
    "taxonomy_assignment_method",
    "taxonomy_assignment_basis",
    "calibration_flag",
    "operator_timing_calibration_flag",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "business_model_classification",
    "commercial_scale_finding",
    "commercial_scale_assessment",
]

# Columns the read-back validator needs to re-derive expectations.
REQUIRED_MASTER_DASHBOARD_COLUMNS = [
    "company",
    "final_priority_level",
    "final_priority_code",
    "primary_market_segment_code",
    "calibration_flag",
]

EXPECTED_SHEETS = [
    "Master Dashboard",
    "Priority Summary",
    "Segment Summary",
    "Calibration Review",
]

_TEXT_COLUMNS = [
    "company",
    "final_priority_level",
    "final_priority_code",
    "priority_source",
    "primary_market_segment_code",
    "primary_market_segment",
    "market_segment",
    "calibration_flag",
    "operator_timing_calibration_flag",
]


def build_dashboard_frame(master_df, *, taxonomy_dir=None, hard_stop=True):
    """Build the per-company dashboard frame from the verified master.

    Applies final priority fields, reclassifies with the override-first taxonomy
    classifier, then recomputes calibration flags from the final priority. Pure
    transform; writes nothing.
    """
    frame = apply_priority_fields(master_df)
    frame = classify_dataframe(frame, taxonomy_dir=taxonomy_dir, hard_stop=hard_stop)
    frame = recompute_calibration_flags(frame)
    return frame


def build_workbook_sheets(dashboard_df):
    """Build the {sheet_name: DataFrame} mapping for the dashboard workbook."""
    master_view = dashboard_df[existing_cols(dashboard_df, MASTER_DASHBOARD_COLUMNS)].copy()
    master_view = safe_sort(master_view, ["final_priority_rank", "company"], ascending=[True, True])

    if "final_priority_code" in dashboard_df.columns:
        priority_summary = (
            dashboard_df.groupby("final_priority_code", dropna=False)["company"]
            .nunique()
            .reset_index(name="company_count")
            .sort_values("final_priority_code")
        )
    else:
        priority_summary = pd.DataFrame(columns=["final_priority_code", "company_count"])

    if "primary_market_segment" in dashboard_df.columns:
        segment_summary = (
            dashboard_df.groupby("primary_market_segment", dropna=False)["company"]
            .nunique()
            .reset_index(name="company_count")
            .sort_values(["company_count", "primary_market_segment"], ascending=[False, True])
        )
    else:
        segment_summary = pd.DataFrame(columns=["primary_market_segment", "company_count"])

    flagged = master_view
    if "calibration_flag" in flagged.columns:
        flagged = flagged[flagged["calibration_flag"].map(safe_text) != ""]
    calibration_review = flagged[
        existing_cols(flagged, ["company", "final_priority_code", "calibration_flag"])
    ].copy()

    return {
        "Master Dashboard": master_view,
        "Priority Summary": priority_summary,
        "Segment Summary": segment_summary,
        "Calibration Review": calibration_review,
    }


def _normalize_text_columns(frame):
    out = frame.copy()
    for col in _TEXT_COLUMNS:
        if col in out.columns:
            out[col] = out[col].map(safe_text)
    return out


def find_stale_calibration_flags(master_dashboard):
    """Return rows whose stored calibration_flag != the value recomputed from
    their final priority. A non-empty result means stale flags survived."""
    md = master_dashboard.copy()
    if "calibration_flag" in md.columns:
        md["calibration_flag"] = md["calibration_flag"].map(safe_text)

    recomputed = recompute_calibration_flags(md)["calibration_flag"].tolist()
    stored = md["calibration_flag"].tolist() if "calibration_flag" in md.columns else [""] * len(md)
    companies = md["company"].tolist() if "company" in md.columns else [""] * len(md)

    stale = []
    for company, expected, actual in zip(companies, recomputed, stored):
        if safe_text(expected) != safe_text(actual):
            stale.append(
                {
                    "company": safe_text(company),
                    "expected_flag": safe_text(expected),
                    "stored_flag": safe_text(actual),
                }
            )
    return stale


def reconcile_override_segments(frame, *, taxonomy_dir=None):
    """Compare each override company's segment in `frame` to its override.

    Returns {checked, matched, mismatches}. Human taxonomy overrides are
    authoritative (CLAUDE.md rule 6), so any mismatch is a defect.
    """
    tables = load_taxonomy_tables(taxonomy_dir)
    code_to_label, label_to_code = code_label_maps(tables)
    allowed_primary = allowed_codes(tables.get("market_segments", pd.DataFrame()), "segment_code")
    overrides = tables.get("company_overrides", pd.DataFrame())

    override_codes = {}
    if not overrides.empty and "company" in overrides.columns:
        for _, row in overrides.iterrows():
            key = normalize_key(row.get("company"))
            code = normalize_code(row.get("primary_market_segment", ""), allowed_primary, label_to_code)
            if key and code:
                override_codes[key] = code

    companies = frame["company"].tolist() if "company" in frame.columns else []
    actual_codes = (
        frame["primary_market_segment_code"].tolist()
        if "primary_market_segment_code" in frame.columns
        else [""] * len(companies)
    )

    checked = 0
    matched = 0
    mismatches = []
    for company, actual in zip(companies, actual_codes):
        expected = override_codes.get(normalize_key(company))
        if not expected:
            continue
        checked += 1
        if safe_text(actual) == expected:
            matched += 1
        else:
            mismatches.append(
                {
                    "company": safe_text(company),
                    "expected_segment": expected,
                    "actual_segment": safe_text(actual),
                }
            )

    return {"checked": checked, "matched": matched, "mismatches": mismatches}


def summarize_calibration_changes(master_df, dashboard_df):
    """Count how the recompute changed flags vs the master's stored flags."""
    if "calibration_flag" in master_df.columns:
        stored = {
            safe_text(c): safe_text(f)
            for c, f in zip(master_df["company"], master_df["calibration_flag"])
        }
    else:
        stored = {}

    cleared = 0
    newly_fired = 0
    changed = 0
    for company, new_flag in zip(dashboard_df["company"], dashboard_df["calibration_flag"]):
        old = stored.get(safe_text(company), "")
        new = safe_text(new_flag)
        if old != new:
            changed += 1
        if old and not new:
            cleared += 1
        if not old and new:
            newly_fired += 1

    return {"flags_cleared": cleared, "flags_newly_fired": newly_fired, "flags_changed": changed}


def validate_dashboard_workbook(readback, *, master_df, taxonomy_dir=None):
    """Validate a read-back workbook. Returns a list of issue dicts; empty = pass.

    Blocking field-level checks:
    - no stale calibration flags survive (every flag matches the final priority)
    - every override company's segment matches its human override
    """
    issues = []

    for sheet in EXPECTED_SHEETS:
        if sheet not in readback:
            issues.append({"check": "missing_sheet", "sheet": sheet})

    if "Master Dashboard" not in readback:
        return issues

    md = _normalize_text_columns(readback["Master Dashboard"])

    if len(md) == 0:
        issues.append({"check": "empty_master_dashboard"})
        return issues

    missing_cols = [c for c in REQUIRED_MASTER_DASHBOARD_COLUMNS if c not in md.columns]
    if missing_cols:
        issues.append({"check": "missing_columns", "columns": missing_cols})
        return issues

    master_companies = {safe_text(c) for c in master_df["company"].tolist()}
    workbook_companies = [safe_text(c) for c in md["company"].tolist()]
    workbook_company_set = set(workbook_companies)

    if workbook_company_set != master_companies:
        issues.append(
            {
                "check": "company_set_mismatch",
                "missing_from_workbook": sorted(master_companies - workbook_company_set),
                "unexpected_in_workbook": sorted(workbook_company_set - master_companies),
            }
        )

    duplicates = sorted({c for c in workbook_companies if workbook_companies.count(c) > 1})
    if duplicates:
        issues.append({"check": "duplicate_companies", "companies": duplicates})

    for stale in find_stale_calibration_flags(md):
        issues.append({"check": "stale_calibration_flag", **stale})

    reconciliation = reconcile_override_segments(md, taxonomy_dir=taxonomy_dir)
    for mismatch in reconciliation["mismatches"]:
        issues.append({"check": "override_segment_mismatch", **mismatch})

    return issues
