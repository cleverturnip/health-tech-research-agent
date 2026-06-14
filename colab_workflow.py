"""
Health Tech Research Agent - Colab Workflow

This file mirrors the active Google Colab workflow.

Current execution environment:

* Google Colab
* Google Drive for persistent storage
* OpenAI API for fit synthesis
* CSV/XLSX exports for dashboard outputs

Important:

* This file is currently a source-of-truth reference for copy/paste Colab cells.
* It is not yet a fully modular script.
* As the workflow stabilizes, cells should be converted into functions and eventually into a runnable pipeline.
  """

# =============================================================================

# STEP 1 - Environment / imports / setup

# =============================================================================

# TODO: Paste current Step 1 Colab code here.

# =============================================================================

# STEP 2 - Company/source config

# =============================================================================

# TODO: Paste current Step 2 Colab code here.

# =============================================================================

# STEP 3 - Search / research helpers

# =============================================================================

# TODO: Paste current Step 3 Colab code here.

# =============================================================================

# STEP 4 - Raw research functions

# =============================================================================

# Purpose:

# - Funding research

# - Payer / institutional distribution research

# - Outcomes research

# - Commercial scale / revenue-quality research

# TODO: Paste current Step 4 Colab code here.

# =============================================================================

# STEP 5 - Company fit synthesis prompt

# =============================================================================

# Purpose:

# - Convert raw research findings into structured JSON

# - Score thesis fit, PMF/scale, evidence confidence, role fit, timing

# - Output scale signal fields

# - Use priority gate logic

# TODO: Paste current Step 5 Colab code here.

# =============================================================================

# STEP 6 - Batch config / paths / company list

# =============================================================================

# TODO: Paste current Step 6 Colab code here.

# =============================================================================

# STEP 6B - Standard cross-batch checkpoint recovery

# =============================================================================

# TODO: Paste current Step 6B Colab code here.

# =============================================================================

# STEP 7 - Run research + fit briefs

# =============================================================================

# TODO: Paste current Step 7 Colab code here.

# =============================================================================

# STEP 8 - Save current batch checkpoint

# =============================================================================

# TODO: Paste current Step 8 Colab code here.

# =============================================================================

# STEP 8A - Save raw research archive

# =============================================================================

# TODO: Paste current Step 8A Colab code here.

# =============================================================================

# STEP 9 - Print raw batch results

# =============================================================================

# TODO: Paste current Step 9 Colab code here.

# =============================================================================

# STEP 10 - Parse fit brief JSON into score/summary table

# =============================================================================

# TODO: Paste current Step 10 Colab code here.

# =============================================================================

# STEP 10A - Deterministic priority adjudication

# =============================================================================

# Purpose:

# - Enforce hard priority rules after LLM scoring

# - Prevent role fit / thesis interest from incorrectly promoting weak-scale companies

# - Update fit_brief_json, checkpoint, and archive rows in place

# TODO: Paste current Step 10A Colab code here.

# =============================================================================

# STEP 10B - Batch QA checks before export/master update

# =============================================================================

# TODO: Paste current Step 10B Colab code here.

# =============================================================================

# STEP 11 - Export current batch only

# =============================================================================

# TODO: Paste current Step 11 Colab code here.

# =============================================================================

# STEP 11A - Final raw archive QA

# =============================================================================

# TODO: Paste current Step 11A Colab code here.

# =============================================================================

# STEP 12 - Add/update current batch in master

# =============================================================================

# TODO: Paste current Step 12 Colab code here.

# =============================================================================

# =============================================================================
# STEP 12B - Priority field helper
# =============================================================================
# =============================================================================
# STEP 12B - Priority field helper
# =============================================================================
# Purpose:
# - Normalize old priority labels and new priority labels into clean P0-P4 dashboard priority
# - Keep priority_level as the automated/adjudicated system priority
# - Keep reviewed_priority_level as optional human override
# - Create final_priority_level for dashboard use
# - Create priority_source for transparency
# - Create final_priority_code / final_priority_rank for clean sorting
#
# New dashboard priority model:
# - P0 = highest-priority target / active pursuit
# - P1 = near-priority target / former P1-border
# - P2 = worth deeper diligence
# - P3 = watch list
# - P4 = low priority / likely reject

import pandas as pd
import re

# -----------------------------
# Basic helpers
# -----------------------------

def is_blank_value(value):
    return pd.isna(value) or str(value).strip() == ""

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def extract_priority_code(value):
    """
    Extract P0, P1, P2, P3, or P4 from a normalized or raw priority value.
    Handles new P0-P4 and older P1-P4 labels.
    """
    text = safe_text(value).upper()
    match = re.search(r"\bP[0-4]\b", text)
    return match.group(0) if match else ""

# -----------------------------
# Priority normalization
# -----------------------------

def normalize_priority_level(value):
    """
    Converts old and new priority labels into clean dashboard labels.

    Old model:
    - P1: High-priority target              -> P0
    - Strong P2 / P1-border                -> P1
    - P2: Worth deeper diligence           -> P2
    - P3: Watch list                       -> P3
    - P4: Low priority / likely reject     -> P4

    New model:
    - P0: Highest-priority target          -> P0
    - P1: Near-priority target             -> P1
    - P2: Worth deeper diligence           -> P2
    - P3: Watch list                       -> P3
    - P4: Low priority / likely reject     -> P4
    """
    text = safe_text(value)

    if text == "":
        return ""

    lower = text.lower()

    # New P0 or old top-priority P1.
    # Keep this before the P1-border logic so old "P1: High-priority" maps up to P0.
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

    # New P1 / old P1-border.
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

    # Clean P2
    if (
        lower.startswith("p2")
        or lower.startswith("review p2")
        or "review p2" in lower
        or "worth deeper diligence" in lower
        or "diligence target" in lower
        or "deeper diligence" in lower
    ):
        return "P2: Worth deeper diligence"

    # Clean P3.
    if (
        lower.startswith("p3")
        or "watch list" in lower
        or "watchlist" in lower
    ):
        return "P3: Watch list"

    # Clean P4.
    if (
        lower.startswith("p4")
        or "low priority" in lower
        or "likely reject" in lower
        or "weak fit" in lower
        or "reject" in lower
    ):
        return "P4: Low priority / likely reject"

    # Ambiguous bare P1:
    # In the new system, P1 means near-priority.
    # Historical old P1 should ideally include "High-priority target" and maps to P0 above.
    if lower == "p1":
        return "P1: Near-priority target"

    # Ambiguous / unmapped. Preserve text rather than destroying source context.
    return text

def priority_code(value):
    normalized = normalize_priority_level(value)
    return extract_priority_code(normalized)

def priority_rank(value):
    """
    Lower rank sorts earlier.
    P0 is the highest-priority bucket.
    """
    code = priority_code(value)

    return {
        "P0": 0,
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4
    }.get(code, 99)

# -----------------------------
# Apply priority fields
# -----------------------------

def apply_priority_fields(input_df):
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
        axis=1
    )

    def determine_priority_source(row):
        auto_priority = normalize_priority_level(row.get("priority_level", ""))
        reviewed_priority = normalize_priority_level(row.get("reviewed_priority_level", ""))
        review_note = safe_text(row.get("priority_review_note", ""))

        if reviewed_priority == "":
            return "Auto Adjudicated"

        if reviewed_priority != auto_priority:
            return "Human Reviewed"

        if review_note != "":
            return "Human Reviewed"

        return "Auto Adjudicated"

    output_df["priority_source"] = output_df.apply(determine_priority_source, axis=1)

    output_df["final_priority_code"] = output_df["final_priority_level"].apply(priority_code)
    output_df["final_priority_rank"] = output_df["final_priority_level"].apply(priority_rank)

    output_df["decision_priority"] = output_df["final_priority_level"]
    output_df["decision_priority_sort"] = output_df["final_priority_rank"]

    return output_df

print("PASS: Step 12B priority helper loaded.")
print("Priority model:")
print("- P0 = Highest-priority target / old P1")
print("- P1 = Near-priority target / old P1-border")
print("- P2 = Worth deeper diligence")
print("- P3 = Watch list")
print("- P4 = Low priority / likely reject")



# =============================================================================

# Purpose:

# - Normalize priority labels into P0-P4 dashboard priority

# - Create final_priority_level, priority_source, final_priority_code, final_priority_rank

# - Preserve priority_level and reviewed_priority_level for traceability

# TODO: Paste current Step 12B Colab code here.

# =============================================================================

# STEP 13 - Load master dashboard using final priority

# =============================================================================

# 13 - Load master dashboard using final priority
# Purpose:
# - Load active master
# - Apply priority helper from Step 12B
# - Create final_priority_level using reviewed_priority_level first, then priority_level
# - Create priority_source for Auto Adjudicated vs Human Reviewed
# - Preserve decision_priority / decision_priority_sort as backward-compatible aliases for older dashboard steps
# - Does not modify or save the master

import pandas as pd
import shutil
from pathlib import Path
from google.colab import drive

drive.mount("/content/drive")

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_master_path = drive_folder / "health_tech_market_research_summary_MASTER.csv"
local_master_path = Path("health_tech_market_research_summary_MASTER.csv")

if not drive_master_path.exists():
    raise FileNotFoundError(f"Master not found: {drive_master_path}")

# Step 13 now depends on Step 12B.
# This prevents multiple cells from maintaining conflicting priority logic.
if "apply_priority_fields" not in globals():
    raise NameError(
        "STOP: apply_priority_fields is not defined. "
        "Run Step 12B - Priority field helper before Step 13."
    )

if "priority_rank" not in globals():
    raise NameError(
        "STOP: priority_rank is not defined. "
        "Run Step 12B - Priority field helper before Step 13."
    )

shutil.copy(drive_master_path, local_master_path)

master_df = pd.read_csv(local_master_path)

# -----------------------------
# Required baseline columns
# -----------------------------

if "company" not in master_df.columns:
    raise ValueError("STOP: Master is missing required column: company")

if "priority_level" not in master_df.columns:
    master_df["priority_level"] = ""

if "reviewed_priority_level" not in master_df.columns:
    master_df["reviewed_priority_level"] = ""

if "priority_review_note" not in master_df.columns:
    master_df["priority_review_note"] = ""

# -----------------------------
# Apply final priority logic from Step 12B
# -----------------------------

master_df = apply_priority_fields(master_df)

# Backward-compatible aliases for steps that still reference old names.
# These should eventually be replaced downstream with final_priority_level / final_priority_rank.
master_df["decision_priority"] = master_df["final_priority_level"]
master_df["decision_priority_sort"] = master_df["final_priority_rank"]

# -----------------------------
# Sort dashboard-ready master
# -----------------------------

sort_cols = []
ascending = []

if "final_priority_rank" in master_df.columns:
    sort_cols.append("final_priority_rank")
    ascending.append(True)

for col in [
    "pmf_scale_score",
    "thesis_fit_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "evidence_confidence_score"
]:
    if col in master_df.columns:
        sort_cols.append(col)
        ascending.append(False)

if sort_cols:
    master_df = master_df.sort_values(
        by=sort_cols,
        ascending=ascending
    ).reset_index(drop=True)

# -----------------------------
# Output summary
# -----------------------------

print("Master loaded for dashboard use.")
print("Master shape:", master_df.shape)
print("Company count:", master_df["company"].nunique())

print("\nFinal priority summary:")
priority_summary = (
    master_df
    .groupby(["final_priority_level", "priority_source"], dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
)

priority_summary["priority_sort"] = priority_summary["final_priority_level"].apply(priority_rank)

priority_summary = priority_summary.sort_values(
    by=["priority_sort", "priority_source"],
    ascending=[True, True]
).drop(columns=["priority_sort"])

display(priority_summary)

print("\nPriority source summary:")
display(
    master_df
    .groupby("priority_source", dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
    .sort_values("priority_source")
)

human_reviewed_df = master_df[
    master_df["priority_source"].astype(str).str.lower().eq("human reviewed")
].copy()

if not human_reviewed_df.empty:
    print("\nHuman-reviewed priority overrides:")
    override_cols = [
        "company",
        "priority_level",
        "reviewed_priority_level",
        "final_priority_level",
        "priority_review_note"
    ]
    override_cols = [col for col in override_cols if col in human_reviewed_df.columns]

    display(
        human_reviewed_df[override_cols]
        .sort_values("final_priority_level")
        .reset_index(drop=True)
    )
else:
    print("\nNo human-reviewed priority overrides found.")

print("\nDashboard priority fields available:")
print("- priority_level = auto/adjudicated system priority")
print("- reviewed_priority_level = optional human override")
print("- final_priority_level = dashboard priority")
print("- priority_source = Auto Adjudicated or Human Reviewed")
print("- final_priority_rank = hidden/helper sort field")

# =============================================================================

# STEP 14 - Build market map view

# =============================================================================

# TODO: Paste current Step 14 Colab code here.

# =============================================================================

# STEP 15 - Segment-level summary

# =============================================================================

# TODO: Paste current Step 15 Colab code here.

# =============================================================================

# STEP 16 - Segment priority summary

# =============================================================================

# TODO: Paste current Step 16 Colab code here.

# =============================================================================

# STEP 17 - Company data depth audit

# =============================================================================

# TODO: Paste current Step 17 Colab code here.

# =============================================================================

# STEP 18 - Segment coverage audit

# =============================================================================

# TODO: Paste current Step 18 Colab code here.

# =============================================================================

# STEP 19 - Export dashboard workbook

# =============================================================================

# Purpose:

# - Export focused dashboard workbook

# - Keep Master Dashboard clean

# - Move priority traceability to Priority Logic Audit

# 19 - Export dashboard workbook
# Purpose:
# - Create a clean Excel workbook from the final-priority dashboard
# - Use final_priority_level as the dashboard priority source of truth
# - Keep Master Dashboard decision-ready
# - Move priority traceability fields to Priority Logic Audit
# - Save to Google Drive
# - Define dashboard_workbook_path for Step 19A formatting
#
# After this, run Step 19A to format and download the workbook.

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from google.colab import drive
import shutil
import re

drive.mount("/content/drive")

# -----------------------------
# Choose dashboard dataframe
# -----------------------------

if "market_map_df" in globals() and isinstance(market_map_df, pd.DataFrame) and not market_map_df.empty:
    dashboard_df = market_map_df.copy()
elif "master_df" in globals() and isinstance(master_df, pd.DataFrame) and not master_df.empty:
    dashboard_df = master_df.copy()
elif "master_summary_df" in globals() and isinstance(master_summary_df, pd.DataFrame) and not master_summary_df.empty:
    dashboard_df = master_summary_df.copy()
else:
    raise NameError("STOP: No dashboard dataframe found. Run Steps 13–14 first.")

# -----------------------------
# Paths
# -----------------------------

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_folder.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

local_export_path = Path(f"health_tech_dashboard_export_{timestamp}.xlsx")
drive_export_path = drive_folder / f"health_tech_dashboard_export_{timestamp}.xlsx"

# Step 19A uses these variables.
dashboard_workbook_path = local_export_path
output_workbook_path = local_export_path

# -----------------------------
# Helpers
# -----------------------------

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def existing_cols(df, cols):
    return [col for col in cols if col in df.columns]

def extract_priority_code(value):
    text = safe_text(value).upper()
    match = re.search(r"\bP[1-4]\b", text)
    return match.group(0) if match else ""

def local_priority_rank(value):
    code = extract_priority_code(value)
    rank_map = {
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4
    }
    return rank_map.get(code, 99)

def safe_sort(df, sort_cols, ascending=None):
    usable_cols = existing_cols(df, sort_cols)

    if not usable_cols:
        return df.copy()

    if ascending is None:
        usable_ascending = [True] * len(usable_cols)
    else:
        usable_ascending = ascending[:len(usable_cols)]

    return df.sort_values(
        by=usable_cols,
        ascending=usable_ascending
    ).copy()

def contains_priority(value, codes):
    code = extract_priority_code(value)
    return code in codes

# -----------------------------
# Ensure final priority fields exist
# -----------------------------

if "apply_priority_fields" in globals():
    dashboard_df = apply_priority_fields(dashboard_df)
else:
    if "priority_level" not in dashboard_df.columns:
        dashboard_df["priority_level"] = ""

    if "reviewed_priority_level" not in dashboard_df.columns:
        dashboard_df["reviewed_priority_level"] = ""

    if "priority_review_note" not in dashboard_df.columns:
        dashboard_df["priority_review_note"] = ""

    dashboard_df["final_priority_level"] = dashboard_df.apply(
        lambda row: row["reviewed_priority_level"]
        if safe_text(row.get("reviewed_priority_level", "")) != ""
        else row.get("priority_level", ""),
        axis=1
    )

    dashboard_df["priority_source"] = dashboard_df["reviewed_priority_level"].apply(
        lambda value: "Human Reviewed" if safe_text(value) != "" else "Auto Adjudicated"
    )

    dashboard_df["final_priority_code"] = dashboard_df["final_priority_level"].apply(extract_priority_code)
    dashboard_df["final_priority_rank"] = dashboard_df["final_priority_level"].apply(local_priority_rank)

# Backward-compatible aliases. These are not used as main dashboard fields.
dashboard_df["decision_priority"] = dashboard_df["final_priority_level"]
dashboard_df["decision_priority_sort"] = dashboard_df["final_priority_rank"]

# -----------------------------
# Ensure required support fields exist
# -----------------------------

default_columns = {
    "company": "",
    "market_segment": "Unmapped",
    "strategic_bucket": "Unmapped",
    "calibration_flag": "",
    "review_status": "",
    "review_notes": "",
    "priority_review_note": "",
    "priority_level": "",
    "reviewed_priority_level": "",
    "priority_source": "Auto Adjudicated",
    "final_priority_level": "",
    "final_priority_code": "",
    "final_priority_rank": 99,
    "final_recommendation": "",
    "business_model_classification": "",
    "commercial_scale_assessment": "",
    "pmf_scale_assessment": "",
    "commercial_scale_finding": "",
    "payer_institutional_finding": "",
    "outcomes_finding": "",
    "funding_finding": "",
    "final_takeaway": "",
    "thesis_fit_score": np.nan,
    "pmf_scale_score": np.nan,
    "evidence_confidence_score": np.nan,
    "katelynd_role_fit_score": np.nan,
    "operator_timing_score": np.nan
}

for col_name, default_value in default_columns.items():
    if col_name not in dashboard_df.columns:
        dashboard_df[col_name] = default_value

dashboard_df["final_priority_rank"] = pd.to_numeric(
    dashboard_df["final_priority_rank"],
    errors="coerce"
).fillna(99).astype(int)

for score_col in [
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score"
]:
    dashboard_df[score_col] = pd.to_numeric(
        dashboard_df[score_col],
        errors="coerce"
    )

# -----------------------------
# Master Dashboard
# -----------------------------
# Clean decision view. Priority plumbing lives in Priority Logic Audit.

master_cols = existing_cols(dashboard_df, [
    "company",
    "final_priority_level",
    "priority_source",
    "market_segment",
    "strategic_bucket",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_recommendation",
    "business_model_classification",
    "commercial_scale_assessment",
    "pmf_scale_assessment",
    "calibration_flag",
    "final_takeaway"
])

master_view = safe_sort(
    dashboard_df,
    [
        "final_priority_rank",
        "thesis_fit_score",
        "pmf_scale_score",
        "katelynd_role_fit_score",
        "operator_timing_score",
        "evidence_confidence_score"
    ],
    [True, False, False, False, False, False]
)[master_cols]

# -----------------------------
# Priority Focus
# -----------------------------
# P1/P2 companies plus companies with calibration flags.

priority_focus_source = dashboard_df[
    dashboard_df["final_priority_level"].apply(lambda value: contains_priority(value, ["P1", "P2"]))
    | dashboard_df["calibration_flag"].astype(str).str.strip().ne("")
].copy()

priority_focus_cols = existing_cols(dashboard_df, [
    "company",
    "final_priority_level",
    "priority_source",
    "market_segment",
    "strategic_bucket",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_recommendation",
    "business_model_classification",
    "commercial_scale_assessment",
    "calibration_flag",
    "final_takeaway"
])

priority_focus = safe_sort(
    priority_focus_source,
    [
        "final_priority_rank",
        "thesis_fit_score",
        "pmf_scale_score",
        "katelynd_role_fit_score",
        "operator_timing_score"
    ],
    [True, False, False, False, False]
)[priority_focus_cols]

# -----------------------------
# Segment Summary
# -----------------------------

if "segment_summary" in globals() and isinstance(segment_summary, pd.DataFrame) and not segment_summary.empty:
    segment_summary_export = segment_summary.copy()
else:
    segment_summary_export = (
        dashboard_df
        .groupby("market_segment", dropna=False)
        .agg(
            company_count=("company", "nunique"),
            p1_count=("final_priority_level", lambda x: x.astype(str).str.contains("P1", case=False, na=False).sum()),
            p2_count=("final_priority_level", lambda x: x.astype(str).str.contains("P2", case=False, na=False).sum()),
            p3_count=("final_priority_level", lambda x: x.astype(str).str.contains("P3", case=False, na=False).sum()),
            p4_count=("final_priority_level", lambda x: x.astype(str).str.contains("P4", case=False, na=False).sum()),
            avg_thesis_fit=("thesis_fit_score", "mean"),
            avg_pmf_scale=("pmf_scale_score", "mean"),
            avg_evidence_confidence=("evidence_confidence_score", "mean"),
            avg_katelynd_role_fit=("katelynd_role_fit_score", "mean"),
            avg_operator_timing=("operator_timing_score", "mean"),
            best_final_priority_rank=("final_priority_rank", "min")
        )
        .reset_index()
    )

    for avg_col in [
        "avg_thesis_fit",
        "avg_pmf_scale",
        "avg_evidence_confidence",
        "avg_katelynd_role_fit",
        "avg_operator_timing"
    ]:
        if avg_col in segment_summary_export.columns:
            segment_summary_export[avg_col] = segment_summary_export[avg_col].round(1)

    segment_summary_export = safe_sort(
        segment_summary_export,
        ["best_final_priority_rank", "p1_count", "p2_count", "avg_thesis_fit"],
        [True, False, False, False]
    )

# -----------------------------
# Companies by Segment
# -----------------------------

company_by_segment_cols = existing_cols(dashboard_df, [
    "market_segment",
    "company",
    "strategic_bucket",
    "final_priority_level",
    "priority_source",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_takeaway"
])

company_by_segment_export = safe_sort(
    dashboard_df[company_by_segment_cols],
    [
        "market_segment",
        "final_priority_rank",
        "thesis_fit_score",
        "operator_timing_score",
        "pmf_scale_score"
    ],
    [True, True, False, False, False]
)

# -----------------------------
# Commercial Scale Review
# -----------------------------

commercial_cols = existing_cols(dashboard_df, [
    "company",
    "final_priority_level",
    "priority_source",
    "market_segment",
    "strategic_bucket",
    "pmf_scale_score",
    "evidence_confidence_score",
    "business_model_classification",
    "commercial_scale_assessment",
    "commercial_scale_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "calibration_flag",
    "final_takeaway"
])

commercial_review = safe_sort(
    dashboard_df[commercial_cols],
    ["final_priority_rank", "pmf_scale_score", "company"],
    [True, False, True]
)

# -----------------------------
# Data Depth Audit
# -----------------------------

if "data_depth_audit" in globals() and isinstance(data_depth_audit, pd.DataFrame) and not data_depth_audit.empty:
    data_depth_audit_export = data_depth_audit.copy()
else:
    audit_rows = []

    for _, row in dashboard_df.iterrows():
        audit_rows.append({
            "company": row.get("company", ""),
            "final_priority_level": row.get("final_priority_level", ""),
            "priority_source": row.get("priority_source", ""),
            "market_segment": row.get("market_segment", ""),
            "strategic_bucket": row.get("strategic_bucket", ""),
            "has_commercial_scale_assessment": safe_text(row.get("commercial_scale_assessment", "")) != "",
            "has_commercial_scale_finding": safe_text(row.get("commercial_scale_finding", "")) != "",
            "has_payer_institutional_finding": safe_text(row.get("payer_institutional_finding", "")) != "",
            "has_outcomes_finding": safe_text(row.get("outcomes_finding", "")) != "",
            "has_funding_finding": safe_text(row.get("funding_finding", "")) != "",
            "has_business_model_classification": safe_text(row.get("business_model_classification", "")) != "",
            "has_calibration_flag": safe_text(row.get("calibration_flag", "")) != ""
        })

    data_depth_audit_export = pd.DataFrame(audit_rows)

# -----------------------------
# Segment Coverage Audit
# -----------------------------

if "segment_coverage_audit" in globals() and isinstance(segment_coverage_audit, pd.DataFrame) and not segment_coverage_audit.empty:
    segment_coverage_audit_export = segment_coverage_audit.copy()
else:
    segment_coverage_audit_export = pd.DataFrame()

# -----------------------------
# Priority Logic Audit
# -----------------------------

priority_logic_cols = existing_cols(dashboard_df, [
    "company",
    "final_priority_level",
    "priority_source",
    "priority_review_note",
    "priority_level",
    "reviewed_priority_level",
    "final_priority_code",
    "final_priority_rank",
    "review_status",
    "review_notes",
    "calibration_flag",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "market_segment",
    "strategic_bucket",
    "final_recommendation",
    "final_takeaway"
])

priority_logic_audit = safe_sort(
    dashboard_df[priority_logic_cols],
    ["final_priority_rank", "company"],
    [True, True]
)

# -----------------------------
# Read Me
# -----------------------------

read_me = pd.DataFrame([
    {
        "sheet": "Master Dashboard",
        "description": "Main decision dashboard. Uses Final Priority Level as the source of truth. Internal priority plumbing is intentionally excluded."
    },
    {
        "sheet": "Priority Focus",
        "description": "P1/P2 companies plus any company with calibration flags."
    },
    {
        "sheet": "Segment Summary",
        "description": "Segment-level scoring and priority roll-up."
    },
    {
        "sheet": "Companies by Segment",
        "description": "Company-level segment view sorted by final priority and fit scores."
    },
    {
        "sheet": "Commercial Scale Review",
        "description": "Commercial-scale and monetization evidence for revenue-quality review."
    },
    {
        "sheet": "Data Depth Audit",
        "description": "QA view showing whether key research evidence and fit-brief fields are populated."
    },
    {
        "sheet": "Segment Coverage Audit",
        "description": "Segment mapping sufficiency audit, included when Step 18 output is available."
    },
    {
        "sheet": "Priority Logic Audit",
        "description": "Traceability view showing automated priority, reviewed priority, final priority, source, and review notes."
    }
])

# -----------------------------
# Export workbook
# -----------------------------

with pd.ExcelWriter(local_export_path, engine="openpyxl") as writer:
    read_me.to_excel(writer, sheet_name="Read Me", index=False)
    master_view.to_excel(writer, sheet_name="Master Dashboard", index=False)
    priority_focus.to_excel(writer, sheet_name="Priority Focus", index=False)
    segment_summary_export.to_excel(writer, sheet_name="Segment Summary", index=False)
    company_by_segment_export.to_excel(writer, sheet_name="Companies by Segment", index=False)
    commercial_review.to_excel(writer, sheet_name="Commercial Scale Review", index=False)
    data_depth_audit_export.to_excel(writer, sheet_name="Data Depth Audit", index=False)

    if not segment_coverage_audit_export.empty:
        segment_coverage_audit_export.to_excel(writer, sheet_name="Segment Coverage Audit", index=False)

    priority_logic_audit.to_excel(writer, sheet_name="Priority Logic Audit", index=False)

shutil.copy(local_export_path, drive_export_path)

print("Dashboard export complete.")
print("Local file:", local_export_path)
print("Drive file:", drive_export_path)

print("\nWorkbook variable for Step 19A:")
print("dashboard_workbook_path =", dashboard_workbook_path)

print("\nExported sheets:")
exported_sheets = [
    "Read Me",
    "Master Dashboard",
    "Priority Focus",
    "Segment Summary",
    "Companies by Segment",
    "Commercial Scale Review",
    "Data Depth Audit"
]

if not segment_coverage_audit_export.empty:
    exported_sheets.append("Segment Coverage Audit")

exported_sheets.append("Priority Logic Audit")

for sheet in exported_sheets:
    print("-", sheet)

# =============================================================================

# STEP 19A - Format exported dashboard workbook

# =============================================================================

# Purpose:

# - Convert headers to readable labels

# - Apply filters

# - Freeze header row

# - Set column widths

# - Wrap text

# - Save/copy/download formatted workbook

# 19A - Format exported dashboard workbook
# Purpose:
# - Convert snake_case headers to readable labels in the workbook only
# - Apply filters
# - Freeze header row
# - Set readable column widths
# - Wrap text for long cells
# - Save formatted workbook locally
# - Copy formatted workbook to Google Drive
# - Download formatted workbook

from pathlib import Path
import re
import shutil
from google.colab import files
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# -----------------------------
# Locate workbook
# -----------------------------

if "dashboard_workbook_path" in globals():
    workbook_path = Path(dashboard_workbook_path)
elif "market_map_workbook_path" in globals():
    workbook_path = Path(market_map_workbook_path)
elif "output_workbook_path" in globals():
    workbook_path = Path(output_workbook_path)
elif "local_export_path" in globals():
    workbook_path = Path(local_export_path)
else:
    raise NameError(
        "STOP: Could not find dashboard_workbook_path, market_map_workbook_path, "
        "output_workbook_path, or local_export_path."
    )

if not workbook_path.exists():
    raise FileNotFoundError(f"STOP: Workbook not found: {workbook_path}")

if "drive_export_path" in globals():
    formatted_drive_path = Path(drive_export_path)
else:
    drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
    drive_folder.mkdir(parents=True, exist_ok=True)
    formatted_drive_path = drive_folder / workbook_path.name

# -----------------------------
# Header formatting helpers
# -----------------------------

def friendly_header(header):
    if header is None:
        return ""

    text = str(header).strip()

    explicit_map = {
        "company": "Company",
        "priority_level": "Priority Level",
        "reviewed_priority_level": "Reviewed Priority Level",
        "final_priority_level": "Final Priority Level",
        "priority_source": "Priority Source",
        "priority_review_note": "Priority Review Note",
        "final_priority_code": "Final Priority Code",
        "final_priority_rank": "Final Priority Rank",
        "decision_priority": "Decision Priority",
        "decision_priority_sort": "Decision Priority Sort",
        "review_status": "Review Status",
        "review_notes": "Review Notes",
        "thesis_fit_score": "Thesis Fit Score",
        "pmf_scale_score": "PMF / Scale Score",
        "evidence_confidence_score": "Evidence Confidence Score",
        "katelynd_role_fit_score": "Katelynd Role Fit Score",
        "operator_timing_score": "Operator Timing Score",
        "final_recommendation": "Final Recommendation",
        "business_model_classification": "Business Model Classification",
        "commercial_scale_assessment": "Commercial Scale Assessment",
        "pmf_scale_assessment": "PMF / Scale Assessment",
        "scale_signal_assessment": "Scale Signal Assessment",
        "calibration_flag": "Calibration Flag",
        "final_takeaway": "Final Takeaway",
        "date_researched": "Date Researched",
        "funding_finding": "Funding Finding",
        "payer_institutional_finding": "Payer / Institutional Finding",
        "outcomes_finding": "Outcomes Finding",
        "commercial_scale_finding": "Commercial Scale Finding",
        "fit_brief_json": "Fit Brief JSON",
        "segment": "Segment",
        "market_segment": "Market Segment",
        "strategic_bucket": "Strategic Bucket",
        "company_stage": "Company Stage",
        "funding_stage": "Funding Stage",
        "revenue_estimate": "Revenue Estimate",
        "employee_count": "Employee Count",
        "source_urls": "Source URLs",
        "notes": "Notes",
        "company_count": "Company Count",
        "p1_count": "P1 Count",
        "p2_count": "P2 Count",
        "p3_count": "P3 Count",
        "p4_count": "P4 Count",
        "human_reviewed_count": "Human Reviewed Count",
        "avg_thesis_fit": "Avg. Thesis Fit",
        "avg_pmf_scale": "Avg. PMF / Scale",
        "avg_evidence_confidence": "Avg. Evidence Confidence",
        "avg_katelynd_role_fit": "Avg. Katelynd Role Fit",
        "avg_operator_timing": "Avg. Operator Timing",
        "best_final_priority_level": "Best Final Priority Level",
        "best_final_priority_rank": "Best Final Priority Rank",
        "best_companies": "Best Companies",
        "current_best_companies": "Current Best Companies",
        "coverage_status": "Coverage Status",
        "companies_needed_for_directional_read": "Companies Needed for Directional Read",
        "companies_needed_for_stronger_read": "Companies Needed for Stronger Read",
        "data_depth_status": "Data Depth Status",
        "raw_record_count": "Raw Record Count",
        "raw_completeness_score": "Raw Completeness Score",
        "has_funding_raw": "Has Funding Raw",
        "has_payer_raw": "Has Payer Raw",
        "has_outcomes_raw": "Has Outcomes Raw",
        "has_commercial_scale_raw": "Has Commercial Scale Raw",
        "has_fit_brief_raw": "Has Fit Brief Raw",
        "fit_brief_json_parseable": "Fit Brief JSON Parseable",
        "raw_source_files": "Raw Source Files",
        "raw_batch_names": "Raw Batch Names"
    }

    if text in explicit_map:
        return explicit_map[text]

    text = text.replace("_", " ").strip()
    text = re.sub(r"\s+", " ", text)

    small_words = {"and", "or", "to", "of", "in", "for", "with", "by"}

    words = []
    for i, word in enumerate(text.split(" ")):
        lower = word.lower()

        if i > 0 and lower in small_words:
            words.append(lower)
        elif lower == "pmf":
            words.append("PMF")
        elif lower == "d2c":
            words.append("D2C")
        elif lower == "b2b2c":
            words.append("B2B2C")
        elif lower == "arr":
            words.append("ARR")
        elif lower == "cac":
            words.append("CAC")
        elif lower == "api":
            words.append("API")
        elif lower == "json":
            words.append("JSON")
        elif lower == "qa":
            words.append("QA")
        else:
            words.append(word.capitalize())

    return " ".join(words)

def width_for_header(header):
    header_lower = str(header).lower()

    very_long_text_terms = [
        "assessment",
        "finding",
        "takeaway",
        "rationale",
        "notes",
        "claim",
        "source",
        "json",
        "description",
        "summary",
        "commercial",
        "outcomes",
        "institutional",
        "companies needed",
        "current best companies",
        "best companies",
        "raw source files",
        "raw batch names"
    ]

    medium_text_terms = [
        "classification",
        "recommendation",
        "priority",
        "business model",
        "segment",
        "flag",
        "status",
        "bucket",
        "source"
    ]

    if any(term in header_lower for term in very_long_text_terms):
        return 44

    if any(term in header_lower for term in medium_text_terms):
        return 26

    if "company" in header_lower:
        return 24

    if "score" in header_lower or "rank" in header_lower or "count" in header_lower:
        return 14

    if "date" in header_lower:
        return 16

    return 18

# -----------------------------
# Format workbook
# -----------------------------

wb = load_workbook(workbook_path)

header_fill = PatternFill("solid", fgColor="D9EAF7")
header_font = Font(bold=True, color="000000")
thin_border = Border(
    bottom=Side(style="thin", color="B7B7B7")
)

for ws in wb.worksheets:
    if ws.max_row < 1 or ws.max_column < 1:
        continue

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    for cell in ws[1]:
        original_header = cell.value
        display_header = friendly_header(original_header)

        cell.value = display_header
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )

    ws.row_dimensions[1].height = 36

    for col_idx in range(1, ws.max_column + 1):
        col_letter = get_column_letter(col_idx)
        header_value = ws.cell(row=1, column=col_idx).value

        ws.column_dimensions[col_letter].width = width_for_header(header_value)

        for row_idx in range(2, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.alignment = Alignment(
                vertical="top",
                wrap_text=True
            )

    for row_idx in range(2, ws.max_row + 1):
        ws.row_dimensions[row_idx].height = 45

    for col_idx in range(1, ws.max_column + 1):
        header_value = str(ws.cell(row=1, column=col_idx).value or "").strip().lower()

        if header_value in [
            "final priority rank",
            "final priority code",
            "decision priority sort",
            "data depth status rank",
            "coverage status rank"
        ]:
            ws.column_dimensions[get_column_letter(col_idx)].hidden = True

# -----------------------------
# Save, sync, download
# -----------------------------

wb.save(workbook_path)
shutil.copy(workbook_path, formatted_drive_path)

print("PASS: Dashboard workbook formatted.")
print("Formatted local workbook:", workbook_path)
print("Formatted Drive workbook:", formatted_drive_path)

files.download(str(workbook_path))

